"""Métricas normalizadas por minuto e por role.

KDA absoluto é enganoso. Damage por minuto, healing por minuto, kills por minuto
permitem comparar partidas de durações diferentes e contra benchmarks globais.
"""

from __future__ import annotations

import pandas as pd


def _per_minute(df: pd.DataFrame, col: str) -> pd.Series:
    minutes = (df["duration_sec"].fillna(df["duration_min"] * 60) / 60).clip(lower=1)
    return df[col].fillna(0) / minutes


def per_match_efficiency(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona colunas *_per_min ao DF (não modifica original)."""
    if df.empty:
        return df.copy()
    out = df.copy()
    out["damage_per_min"] = _per_minute(out, "damage")
    out["healing_per_min"] = _per_minute(out, "healing")
    out["taken_per_min"] = _per_minute(out, "damage_taken")
    out["kills_per_min"] = _per_minute(out, "kills")
    return out


def role_expectation_score(df: pd.DataFrame) -> pd.DataFrame:
    """Score relativo à role: Strategist por heal/min, Vanguard por taken/min, Duelist por damage/min.

    Retorna média por herói de uma 'métrica de role' apropriada.
    """
    if df.empty:
        return pd.DataFrame()
    eff = per_match_efficiency(df)
    rows = []
    for hero, g in eff.groupby("hero"):
        role = g["role"].iloc[0]
        if role == "Strategist":
            metric_name = "healing_per_min"
        elif role == "Vanguard":
            metric_name = "taken_per_min"
        elif role == "Duelist":
            metric_name = "damage_per_min"
        else:
            metric_name = "damage_per_min"
        rows.append({
            "hero": hero,
            "role": role,
            "matches": len(g),
            "role_metric_name": metric_name,
            "role_metric_value": float(g[metric_name].mean()),
            "win_rate": float(g["won"].mean()),
        })
    return pd.DataFrame(rows).sort_values("role_metric_value", ascending=False)


def efficiency_summary(df: pd.DataFrame) -> dict:
    """Médias globais por minuto."""
    if df.empty:
        return {}
    eff = per_match_efficiency(df)
    return {
        "damage_per_min": float(eff["damage_per_min"].mean()),
        "healing_per_min": float(eff["healing_per_min"].mean()),
        "taken_per_min": float(eff["taken_per_min"].mean()),
        "kills_per_min": float(eff["kills_per_min"].mean()),
    }
