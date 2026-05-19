"""Análise de hero pool: concentração, performance por herói e role."""

from __future__ import annotations

import pandas as pd


def hero_stats(df: pd.DataFrame, min_matches: int = 3) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = (
        df.groupby(["hero", "role"])
        .agg(
            matches=("won", "size"),
            wins=("won", "sum"),
            win_rate=("won", "mean"),
            avg_k=("kills", "mean"),
            avg_d=("deaths", "mean"),
            avg_a=("assists", "mean"),
        )
        .reset_index()
    )
    out["kda"] = (out["avg_k"] + out["avg_a"]) / out["avg_d"].replace(0, 1)
    out = out.sort_values("matches", ascending=False)
    out["enough_data"] = out["matches"] >= min_matches
    return out


def role_distribution(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby("role")
        .agg(matches=("won", "size"), win_rate=("won", "mean"))
        .reset_index()
        .sort_values("matches", ascending=False)
    )


def concentration_index(df: pd.DataFrame) -> float:
    """Índice de Herfindahl normalizado (0 = espalhado, 1 = one-trick)."""
    if df.empty:
        return 0.0
    shares = df["hero"].value_counts(normalize=True)
    hhi = (shares**2).sum()
    n = len(shares)
    if n <= 1:
        return 1.0
    # Normalizado para [0, 1]
    return float((hhi - 1 / n) / (1 - 1 / n))


def anchor_and_sinker(df: pd.DataFrame, min_matches: int = 5) -> dict:
    """Identifica o herói com melhor e pior win rate (com amostra mínima)."""
    stats = hero_stats(df, min_matches=min_matches)
    eligible = stats[stats["matches"] >= min_matches]
    if eligible.empty:
        return {"anchor": None, "sinker": None}

    anchor_row = eligible.loc[eligible["win_rate"].idxmax()]
    sinker_row = eligible.loc[eligible["win_rate"].idxmin()]
    return {
        "anchor": {
            "hero": anchor_row["hero"],
            "win_rate": float(anchor_row["win_rate"]),
            "matches": int(anchor_row["matches"]),
        },
        "sinker": {
            "hero": sinker_row["hero"],
            "win_rate": float(sinker_row["win_rate"]),
            "matches": int(sinker_row["matches"]),
        },
    }
