"""Métricas agregadas básicas. Filtra disconnects por padrão."""

from __future__ import annotations

import pandas as pd


def _no_dc(df: pd.DataFrame) -> pd.DataFrame:
    if "disconnected" in df.columns:
        return df[~df["disconnected"]]
    return df


def kda(df: pd.DataFrame) -> float:
    sub = _no_dc(df)
    deaths = sub["deaths"].sum()
    if deaths == 0:
        return float(sub["kills"].sum() + sub["assists"].sum())
    return float((sub["kills"].sum() + sub["assists"].sum()) / deaths)


def win_rate(df: pd.DataFrame) -> float:
    sub = _no_dc(df)
    if sub.empty:
        return 0.0
    return float(sub["won"].mean())


def summary(df: pd.DataFrame) -> dict:
    sub = _no_dc(df)
    if sub.empty:
        return {"matches": 0}
    dc_count = int(df["disconnected"].sum()) if "disconnected" in df.columns else 0
    return {
        "matches": len(sub),
        "wins": int(sub["won"].sum()),
        "losses": int((~sub["won"]).sum()),
        "win_rate": win_rate(sub),
        "kda": kda(sub),
        "avg_kills": float(sub["kills"].mean()),
        "avg_deaths": float(sub["deaths"].mean()),
        "avg_assists": float(sub["assists"].mean()),
        "total_hours": float(sub["duration_min"].sum() / 60),
        "unique_heroes": int(sub["hero"].nunique()),
        "disconnects_excluded": dc_count,
    }
