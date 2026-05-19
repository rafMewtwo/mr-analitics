"""Plano de climb data-driven: dado o estado atual de haechanie, quantifica
o caminho mais eficiente pra próxima rank.

Sistema de rank do Marvel Rivals (ranked score = MR):
- Bronze III/II/I, Silver III/II/I, Gold III/II/I, Platinum III/II/I,
  Diamond III/II/I, Grandmaster, Celestial, Eternity, One Above All.
- Cada divisão = 100 MR (Bronze III = 0-99, Silver III = 300-399, etc).
- Acima de Grandmaster vira pontos absolutos.

Lógica:
1. Calcular MR atual e MR pra próxima divisão.
2. Calcular avg MR/match nas últimas N partidas.
3. Projetar quantas partidas até a próxima rank no ritmo atual.
4. Identificar 'best pick': herói com WR alto + accuracy boa + amostra suficiente.
5. Quantificar uplift estimado se trocar pra esse herói:
   - Se trocar 100% pro best_pick e ele tiver WR X% vs sua WR atual Y%, uplift = X-Y pp.
   - Aplicar 70-80% do uplift teórico (efeito de regressão à média).
"""

from __future__ import annotations

import pandas as pd

from data import HaechanieData

# Tier thresholds aproximados (MR pra entrar em cada tier)
RANK_THRESHOLDS = [
    (0, "Bronze III"),
    (100, "Bronze II"),
    (200, "Bronze I"),
    (300, "Silver III"),
    (400, "Silver II"),
    (500, "Silver I"),
    (600, "Gold III"),
    (700, "Gold II"),
    (800, "Gold I"),
    (900, "Platinum III"),
    (1000, "Platinum II"),
    (1100, "Platinum I"),
    (1200, "Diamond III"),
    (1300, "Diamond II"),
    (1400, "Diamond I"),
    (1500, "Grandmaster"),
]

# OBS: API retorna `new_score` que é a soma cumulativa real (ex: 3563). Esses 100
# de step aqui são pra mapping linear no UI. O importante é o avg_mr_per_match.


def current_mr(data: HaechanieData) -> float | None:
    df = data.matches_df
    if df.empty or "new_score" not in df.columns:
        return None
    s = df["new_score"].dropna()
    return float(s.iloc[-1]) if not s.empty else None


def avg_mr_per_match(data: HaechanieData, last_n: int = 20) -> dict | None:
    df = data.matches_df
    if df.empty or "score_change" not in df.columns:
        return None
    sub = df.tail(last_n)
    sc = sub["score_change"].dropna()
    if sc.empty:
        return None
    return {
        "avg": float(sc.mean()),
        "wins_avg": float(sub[sub["won"]]["score_change"].dropna().mean() or 0),
        "losses_avg": float(sub[~sub["won"]]["score_change"].dropna().mean() or 0),
        "sample": int(len(sub)),
        "actual_wr": float(sub["won"].mean()),
    }


def best_pick_recommendation(data: HaechanieData, min_matches: int = 3) -> dict | None:
    """Identifica o herói mais 'cost-effective': WR alta + amostra suficiente.

    Score = WR * sqrt(matches) — favorece amostras maiores pra evitar fluke.
    """
    df = data.heroes_ranked_df.copy()
    if df.empty:
        return None
    eligible = df[df["matches"] >= min_matches].copy()
    if eligible.empty:
        return None
    eligible["confidence_score"] = eligible["win_rate"] * (eligible["matches"] ** 0.5)
    best = eligible.sort_values("confidence_score", ascending=False).iloc[0]

    overall_wr = float(data.matches_df["won"].mean()) if not data.matches_df.empty else 0
    uplift_pp = (best["win_rate"] - overall_wr) * 100

    return {
        "hero": best["hero"],
        "role": best["role"],
        "matches": int(best["matches"]),
        "win_rate": float(best["win_rate"]),
        "current_overall_wr": overall_wr,
        "theoretical_uplift_pp": uplift_pp,
        "conservative_uplift_pp": uplift_pp * 0.7,
    }


def worst_drain(data: HaechanieData, min_matches: int = 3) -> dict | None:
    """Herói que mais sangra MR — alta amostra, baixa WR."""
    df = data.heroes_ranked_df.copy()
    if df.empty:
        return None
    eligible = df[df["matches"] >= min_matches].copy()
    if eligible.empty:
        return None
    worst = eligible.sort_values("win_rate").iloc[0]
    return {
        "hero": worst["hero"],
        "role": worst["role"],
        "matches": int(worst["matches"]),
        "win_rate": float(worst["win_rate"]),
    }


def project_to_next_tier(data: HaechanieData) -> dict | None:
    """Quantas vitórias/partidas pra subir de divisão no ritmo atual."""
    cur = current_mr(data)
    if cur is None:
        return None
    avg = avg_mr_per_match(data)
    if not avg:
        return None

    # Marvel Rivals MR é absoluto (3563 = Silver I = ~500 pts numa escala 0-1500
    # mas dentro do tier system real). Usamos diff de divisão = ~100 MR.
    next_tier_mr = (int(cur) // 100 + 1) * 100
    gap = next_tier_mr - cur

    if avg["avg"] <= 0:
        return {
            "current_mr": cur,
            "next_tier_mr": next_tier_mr,
            "gap": gap,
            "avg_per_match": avg["avg"],
            "wins_avg": avg["wins_avg"],
            "losses_avg": avg["losses_avg"],
            "matches_needed": None,
            "blocked_reason": "Saldo de MR negativo no ritmo atual — não está subindo",
        }

    matches_needed = int(gap / avg["avg"])
    wins_needed = int(gap / max(avg["wins_avg"], 1))

    return {
        "current_mr": cur,
        "next_tier_mr": next_tier_mr,
        "gap": gap,
        "avg_per_match": avg["avg"],
        "wins_avg": avg["wins_avg"],
        "losses_avg": avg["losses_avg"],
        "matches_needed": matches_needed,
        "wins_needed_pure": wins_needed,
        "actual_wr": avg["actual_wr"],
    }


def actionable_plan(data: HaechanieData) -> dict:
    """Retorna um plano completo, pronto pra renderizar como lista numerada."""
    proj = project_to_next_tier(data)
    best = best_pick_recommendation(data)
    drain = worst_drain(data)

    return {
        "projection": proj,
        "best_pick": best,
        "worst_drain": drain,
        "rank": data.rank,
        "level": data.level,
    }
