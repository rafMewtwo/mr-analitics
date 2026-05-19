"""Análise focada em ranqueada: MR/Score gain/loss, trajetória, assimetria.

Filtra partidas com `disconnected=True` por padrão (não devem contar pra skill).
"""

from __future__ import annotations

import pandas as pd


def _filter(df: pd.DataFrame, include_dc: bool = False, ranked_only: bool = True) -> pd.DataFrame:
    out = df.copy()
    if not include_dc and "disconnected" in out.columns:
        out = out[~out["disconnected"]]
    if ranked_only and "score_change" in out.columns:
        # Ranqueada tem score_change != None (None em casual). Filtrar não-null.
        out = out[out["score_change"].notna()]
    return out


def mr_trajectory(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna DF com played_at e new_score por partida (pra plotar)."""
    sub = _filter(df)
    if sub.empty or "new_score" not in sub.columns:
        return pd.DataFrame(columns=["played_at", "new_score", "score_change"])
    return (
        sub[["played_at", "new_score", "score_change"]]
        .dropna(subset=["new_score"])
        .sort_values("played_at")
        .reset_index(drop=True)
    )


def mr_summary(df: pd.DataFrame) -> dict:
    """Estatísticas agregadas de MR ganho/perdido."""
    sub = _filter(df)
    if sub.empty or "score_change" not in sub.columns:
        return {"available": False}

    sc = sub["score_change"].dropna()
    if sc.empty:
        return {"available": False}

    wins = sub[sub["won"]]["score_change"].dropna()
    losses = sub[~sub["won"]]["score_change"].dropna()

    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float(losses.mean()) if not losses.empty else 0.0
    total = float(sc.sum())

    return {
        "available": True,
        "matches_ranked": int(len(sc)),
        "total_mr_change": total,
        "avg_mr_per_win": avg_win,
        "avg_mr_per_loss": avg_loss,  # negativo
        "asymmetry": avg_win + avg_loss,  # >0 = ganha mais que perde
        "biggest_win": float(wins.max()) if not wins.empty else 0.0,
        "biggest_loss": float(losses.min()) if not losses.empty else 0.0,
        "current_score": float(sub.sort_values("played_at")["new_score"].dropna().iloc[-1]) if not sub.empty else None,
    }


def mr_by_hero(df: pd.DataFrame, min_matches: int = 3) -> pd.DataFrame:
    """MR médio ganho/perdido por herói. Identifica heróis que rendem mais MR."""
    sub = _filter(df)
    if sub.empty:
        return pd.DataFrame()
    out = (
        sub.groupby(["hero", "role"])
        .agg(
            matches=("score_change", "size"),
            total_mr=("score_change", "sum"),
            avg_mr=("score_change", "mean"),
            win_rate=("won", "mean"),
        )
        .reset_index()
        .sort_values("total_mr", ascending=False)
    )
    out["enough_data"] = out["matches"] >= min_matches
    return out


def detect_mr_bleed(df: pd.DataFrame) -> dict | None:
    """Detecta 'sangria de MR': perdendo mais MR por derrota do que ganha por vitória."""
    summary = mr_summary(df)
    if not summary.get("available") or summary["matches_ranked"] < 6:
        return None
    bleeding = summary["asymmetry"] < -3  # perde 3+ MR a mais que ganha
    return {
        "bleeding": bleeding,
        "asymmetry": summary["asymmetry"],
        "avg_win": summary["avg_mr_per_win"],
        "avg_loss": summary["avg_mr_per_loss"],
    }
