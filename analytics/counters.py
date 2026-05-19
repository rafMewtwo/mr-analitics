"""Análise de matchups: quais heróis inimigos você apanha e quais são presa.

Fonte: profile.hero_matchups — já é agregado pela API (WR vs cada herói inimigo,
contabilizando todas as partidas onde esse herói apareceu no time inimigo).

Uso:
- Top counters: heróis que você apanha (WR baixa, amostra >= min_matches)
- Top easy matchups: heróis que você ganha (WR alta, amostra >= min_matches)
- Filtro por role: ver counters específicos por classe
"""

from __future__ import annotations

import pandas as pd

from data import HaechanieData


def _filter_known(df: pd.DataFrame) -> pd.DataFrame:
    """Remove entries com hero ou role 'Unknown' (variantes/transformações da API)."""
    if df.empty:
        return df
    return df[(df["hero"] != "Unknown") & (df["role"] != "Unknown")].copy()


def hardest_matchups(data: HaechanieData, min_matches: int = 3, n: int = 5) -> pd.DataFrame:
    """Heróis inimigos que mais te derrotam (WR mais baixa, com amostra)."""
    df = _filter_known(data.hero_matchups_df)
    if df.empty:
        return df
    eligible = df[df["matches"] >= min_matches]
    return eligible.sort_values("win_rate", ascending=True).head(n)


def easiest_matchups(data: HaechanieData, min_matches: int = 3, n: int = 5) -> pd.DataFrame:
    """Heróis inimigos contra quem você performa melhor."""
    df = _filter_known(data.hero_matchups_df)
    if df.empty:
        return df
    eligible = df[df["matches"] >= min_matches]
    return eligible.sort_values("win_rate", ascending=False).head(n)


def matchup_by_role(data: HaechanieData) -> pd.DataFrame:
    """Agrega WR contra inimigos por role (Vanguard, Duelist, Strategist)."""
    df = _filter_known(data.hero_matchups_df)
    if df.empty:
        return df
    agg = (
        df.groupby("role")
        .agg(
            heroes_faced=("hero", "count"),
            total_matches=("matches", "sum"),
            total_wins=("wins", "sum"),
        )
        .reset_index()
    )
    agg["win_rate"] = agg["total_wins"] / agg["total_matches"].replace(0, 1)
    return agg.sort_values("win_rate", ascending=False)


def matchup_summary(data: HaechanieData, min_matches: int = 3) -> dict:
    df = data.hero_matchups_df
    if df.empty:
        return {"available": False}
    elig = df[df["matches"] >= min_matches]
    if elig.empty:
        return {"available": False, "reason": "sem matchup com amostra mínima"}

    avg = float(elig["win_rate"].mean())
    weak = elig[elig["win_rate"] < 0.35]
    strong = elig[elig["win_rate"] > 0.65]

    return {
        "available": True,
        "avg_wr_vs_eligible": avg,
        "heroes_faced_min_3": int(len(elig)),
        "hard_counter_count": int(len(weak)),
        "easy_count": int(len(strong)),
        "total_enemies_seen": int(df["matches"].sum()),
    }
