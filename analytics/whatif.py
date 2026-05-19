"""Análise contrafactual: 'e se você seguisse as recomendações?'.

Identifica partidas em condições 'remediaveis' (madrugada, pós-tilt) e estima
quanto win rate e MR você teria se evitasse essas condições.

Modelo simples mas honesto:
- Cenário A (avoid): se você não jogasse nessas condições, sua WR seria igual
  à dos jogos em 'boas condições'.
- Cenário B (shift): se você jogasse essas partidas em estado descansado,
  a WR delas se aproximaria da WR boa. Resultado por construção dá a mesma
  WR projetada que A — diferença é que B preserva o número total de partidas.
"""

from __future__ import annotations

import pandas as pd


def flag_remediable(df: pd.DataFrame, late_start: int = 23) -> pd.DataFrame:
    """Adiciona colunas is_late, is_tilt, is_remediable. Filtra DC."""
    if df.empty:
        return df.copy()

    out = df.copy()
    if "disconnected" in out.columns:
        out = out[~out["disconnected"]]
    out = out.sort_values("played_at").reset_index(drop=True)

    hour = out["played_at"].dt.hour
    out["is_late"] = (hour >= late_start) | (hour < 5)

    losses_in_row = 0
    is_tilt = []
    for won in out["won"]:
        is_tilt.append(losses_in_row >= 2)
        losses_in_row = losses_in_row + 1 if not won else 0
    out["is_tilt"] = is_tilt
    out["is_remediable"] = out["is_late"] | out["is_tilt"]
    return out


def estimate_impact(df: pd.DataFrame, late_start: int = 23) -> dict | None:
    """Calcula impacto contrafactual de evitar madrugada + pausar pós-tilt."""
    flagged = flag_remediable(df, late_start=late_start)
    if flagged.empty or len(flagged) < 6:
        return None

    good = flagged[~flagged["is_remediable"]]
    bad = flagged[flagged["is_remediable"]]

    if good.empty or bad.empty:
        return {"available": False, "reason": "sem variação entre boas e más condições"}

    cur_wr = float(flagged["won"].mean())
    good_wr = float(good["won"].mean())
    bad_wr = float(bad["won"].mean())

    expected_bad_wins = len(bad) * good_wr
    actual_bad_wins = float(bad["won"].sum())
    flipped = expected_bad_wins - actual_bad_wins
    new_wins_total = float(flagged["won"].sum()) + flipped
    projected_wr = new_wins_total / len(flagged)

    # MR / score
    sc = flagged["score_change"].dropna() if "score_change" in flagged.columns else pd.Series(dtype=float)
    mr_impact = None
    if not sc.empty:
        wins_mr = flagged[flagged["won"]]["score_change"].dropna()
        losses_mr = flagged[~flagged["won"]]["score_change"].dropna()
        avg_win = float(wins_mr.mean()) if not wins_mr.empty else 0.0
        avg_loss = float(losses_mr.mean()) if not losses_mr.empty else 0.0
        mr_per_flip = avg_win - avg_loss
        mr_uplift = flipped * mr_per_flip
        cur_total = float(sc.sum())
        new_total = cur_total + mr_uplift
        mr_impact = {
            "avg_win_mr": avg_win,
            "avg_loss_mr": avg_loss,
            "mr_per_flip": mr_per_flip,
            "current_total": cur_total,
            "projected_total": new_total,
            "uplift": mr_uplift,
            "uplift_pct": (mr_uplift / abs(cur_total) * 100) if cur_total else None,
        }

    return {
        "available": True,
        "total_matches": int(len(flagged)),
        "remediable_matches": int(len(bad)),
        "remediable_share": float(len(bad) / len(flagged)),
        "late_count": int(flagged["is_late"].sum()),
        "tilt_count": int(flagged["is_tilt"].sum()),
        "overlap_count": int((flagged["is_late"] & flagged["is_tilt"]).sum()),
        "current_wr": cur_wr,
        "good_wr": good_wr,
        "bad_wr": bad_wr,
        "projected_wr": projected_wr,
        "wr_uplift_pp": (projected_wr - cur_wr) * 100,
        "wins_flipped": flipped,
        "mr": mr_impact,
    }


def conservative_range(impact: dict) -> tuple[float, float]:
    """Retorna intervalo conservador (70-100%) do uplift de WR em pp."""
    full = impact.get("wr_uplift_pp", 0.0)
    return (full * 0.7, full)


def conservative_mr_range(impact: dict) -> tuple[float, float] | None:
    if not impact.get("mr"):
        return None
    full = impact["mr"]["uplift"]
    return (full * 0.7, full)
