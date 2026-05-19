"""Padrões temporais: horário, fadiga em sessão, tilt após derrotas."""

from __future__ import annotations

import pandas as pd


def win_rate_by_hour(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["hour", "matches", "win_rate"])
    out = (
        df.assign(hour=df["played_at"].dt.hour)
        .groupby("hour")
        .agg(matches=("won", "size"), win_rate=("won", "mean"))
        .reset_index()
    )
    return out


def win_rate_by_weekday(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["weekday", "matches", "win_rate"])
    names = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    out = (
        df.assign(weekday=df["played_at"].dt.weekday)
        .groupby("weekday")
        .agg(matches=("won", "size"), win_rate=("won", "mean"))
        .reset_index()
    )
    out["weekday_name"] = out["weekday"].map(lambda i: names[i])
    return out


def detect_tilt(df: pd.DataFrame) -> dict:
    """Compara win rate logo após 2+ derrotas seguidas vs win rate geral."""
    if len(df) < 5:
        return {"detected": False, "reason": "amostra insuficiente"}

    df = df.sort_values("played_at").reset_index(drop=True)
    overall = float(df["won"].mean())

    tilt_matches = []
    losses_in_row = 0
    for _, row in df.iterrows():
        if losses_in_row >= 2:
            tilt_matches.append(row["won"])
        losses_in_row = losses_in_row + 1 if not row["won"] else 0

    if not tilt_matches:
        return {"detected": False, "reason": "nenhuma sequência de 2+ derrotas"}

    tilt_wr = sum(tilt_matches) / len(tilt_matches)
    delta = tilt_wr - overall
    return {
        "detected": delta < -0.05,
        "overall_wr": overall,
        "post_2L_wr": tilt_wr,
        "delta_pp": delta * 100,
        "sample": len(tilt_matches),
    }


def session_fatigue(df: pd.DataFrame, gap_minutes: int = 60) -> dict:
    """Detecta queda de performance dentro da mesma sessão.

    Sessão = sequência de partidas com gap < gap_minutes entre elas.
    Compara win rate das primeiras 2 partidas vs a partir da 4ª.
    """
    if len(df) < 6:
        return {"detected": False, "reason": "amostra insuficiente"}

    df = df.sort_values("played_at").reset_index(drop=True).copy()
    gap = df["played_at"].diff().dt.total_seconds().div(60).fillna(9999)
    df["session_id"] = (gap > gap_minutes).cumsum()
    df["pos_in_session"] = df.groupby("session_id").cumcount() + 1

    early = df[df["pos_in_session"] <= 2]
    late = df[df["pos_in_session"] >= 4]

    if early.empty or len(late) < 3:
        return {"detected": False, "reason": "poucas sessões longas"}

    early_wr = float(early["won"].mean())
    late_wr = float(late["won"].mean())
    return {
        "detected": (late_wr - early_wr) < -0.08,
        "early_wr": early_wr,
        "late_wr": late_wr,
        "delta_pp": (late_wr - early_wr) * 100,
        "late_sample": len(late),
    }


def late_night_drop(df: pd.DataFrame, late_start: int = 23) -> dict:
    """Compara win rate em horário tardio (>= late_start ou < 5h) vs resto."""
    if df.empty:
        return {"detected": False}
    hour = df["played_at"].dt.hour
    is_late = (hour >= late_start) | (hour < 5)
    late = df[is_late]
    other = df[~is_late]
    if len(late) < 5 or len(other) < 5:
        return {"detected": False, "reason": "amostra insuficiente"}
    delta = float(late["won"].mean()) - float(other["won"].mean())
    return {
        "detected": delta < -0.05,
        "late_wr": float(late["won"].mean()),
        "other_wr": float(other["won"].mean()),
        "delta_pp": delta * 100,
        "late_sample": len(late),
    }
