"""MVP/SVP rate, melhores partidas, momentos de carregar.

MVP = Most Valuable Player. SVP = Second VP. Indicador de quando você foi
o standout ou impacto definidor — diferente de só "ganhou".
"""

from __future__ import annotations

import pandas as pd


def mvp_summary(df: pd.DataFrame) -> dict:
    if df.empty or "is_mvp" not in df.columns:
        return {"available": False}
    wins = df[df["won"]]
    mvp_total = int(df["is_mvp"].sum())
    svp_total = int(df["is_svp"].sum())
    mvp_rate_overall = float(df["is_mvp"].mean())
    mvp_rate_in_wins = float(wins["is_mvp"].mean()) if not wins.empty else 0.0
    return {
        "available": True,
        "matches": len(df),
        "mvp_count": mvp_total,
        "svp_count": svp_total,
        "mvp_rate": mvp_rate_overall,
        "mvp_rate_in_wins": mvp_rate_in_wins,
        "podium_rate": float((df["is_mvp"] | df["is_svp"]).mean()),
    }


def mvp_by_hero(df: pd.DataFrame, min_matches: int = 3) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = (
        df.groupby(["hero", "role"])
        .agg(
            matches=("is_mvp", "size"),
            mvp_count=("is_mvp", "sum"),
            svp_count=("is_svp", "sum"),
            mvp_rate=("is_mvp", "mean"),
            podium_rate=("is_mvp", lambda s: ((df.loc[s.index, "is_mvp"]) | (df.loc[s.index, "is_svp"])).mean()),
        )
        .reset_index()
        .sort_values("podium_rate", ascending=False)
    )
    out["enough_data"] = out["matches"] >= min_matches
    return out


def best_matches(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Top N partidas por KDA (com filtro de partidas com tempo decente)."""
    if df.empty:
        return pd.DataFrame()
    sub = df.copy()
    sub["kda"] = (sub["kills"] + sub["assists"]) / sub["deaths"].replace(0, 1)
    return (
        sub.sort_values("kda", ascending=False)
        .head(n)[["played_at", "hero", "role", "map", "won", "kills", "deaths", "assists", "kda", "is_mvp"]]
    )


def worst_matches(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Bottom N partidas (úteis pra drill-down)."""
    if df.empty:
        return pd.DataFrame()
    sub = df.copy()
    sub["kda"] = (sub["kills"] + sub["assists"]) / sub["deaths"].replace(0, 1)
    sub = sub[~sub["disconnected"]]  # tira DCs do worst list
    return (
        sub.sort_values("kda", ascending=True)
        .head(n)[["played_at", "hero", "role", "map", "won", "kills", "deaths", "assists", "kda"]]
    )
