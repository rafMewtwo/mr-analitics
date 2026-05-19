"""Padrões de performance: mapas, close games, hero×map, comportamento em derrota."""

from __future__ import annotations

import pandas as pd


def _no_dc(df: pd.DataFrame) -> pd.DataFrame:
    if "disconnected" in df.columns:
        return df[~df["disconnected"]]
    return df


def map_performance(df: pd.DataFrame, min_matches: int = 3) -> pd.DataFrame:
    sub = _no_dc(df)
    if sub.empty:
        return pd.DataFrame()
    out = (
        sub.groupby("map")
        .agg(matches=("won", "size"), win_rate=("won", "mean"))
        .reset_index()
        .sort_values("win_rate")
    )
    out["enough_data"] = out["matches"] >= min_matches
    return out


def hero_map_matrix(df: pd.DataFrame, min_matches: int = 2) -> pd.DataFrame:
    """Matriz win rate por combinação hero × map. Detecta interações."""
    sub = _no_dc(df)
    if sub.empty:
        return pd.DataFrame()
    grouped = (
        sub.groupby(["hero", "map"])
        .agg(matches=("won", "size"), win_rate=("won", "mean"))
        .reset_index()
    )
    return grouped[grouped["matches"] >= min_matches].sort_values("win_rate", ascending=False)


def close_vs_blowout(df: pd.DataFrame) -> dict:
    """Compara performance em jogos apertados vs blowouts.

    Close game = diferença de rounds <= 1 (3-2, 2-1, etc).
    Blowout = diferença >= 2.
    """
    sub = _no_dc(df)
    if sub.empty or "score_self" not in sub.columns:
        return {"available": False}

    valid = sub.dropna(subset=["score_self", "score_enemy"]).copy()
    if valid.empty:
        return {"available": False}

    valid["diff"] = (valid["score_self"] - valid["score_enemy"]).abs()
    close = valid[valid["diff"] <= 1]
    blowout = valid[valid["diff"] >= 2]

    return {
        "available": True,
        "close_matches": int(len(close)),
        "close_win_rate": float(close["won"].mean()) if not close.empty else 0.0,
        "blowout_matches": int(len(blowout)),
        "blowout_win_rate": float(blowout["won"].mean()) if not blowout.empty else 0.0,
        "close_share": float(len(close) / len(valid)) if len(valid) else 0.0,
    }


def loss_profile(df: pd.DataFrame) -> dict:
    sub = _no_dc(df)
    if sub.empty or sub["won"].nunique() < 2:
        return {"available": False}

    wins = sub[sub["won"]]
    losses = sub[~sub["won"]]
    return {
        "available": True,
        "avg_deaths_win": float(wins["deaths"].mean()),
        "avg_deaths_loss": float(losses["deaths"].mean()),
        "avg_damage_win": float(wins["damage"].mean()),
        "avg_damage_loss": float(losses["damage"].mean()),
        "damage_drop_pct": float(
            (wins["damage"].mean() - losses["damage"].mean())
            / wins["damage"].mean()
            * 100
        )
        if wins["damage"].mean() > 0
        else 0.0,
    }


def streaks(df: pd.DataFrame) -> dict:
    sub = _no_dc(df)
    if sub.empty:
        return {}
    sub = sub.sort_values("played_at")
    cur_w = cur_l = max_w = max_l = 0
    for won in sub["won"]:
        if won:
            cur_w += 1
            cur_l = 0
            max_w = max(max_w, cur_w)
        else:
            cur_l += 1
            cur_w = 0
            max_l = max(max_l, cur_l)
    return {
        "longest_win_streak": max_w,
        "longest_loss_streak": max_l,
        "current_streak": cur_w if cur_w > 0 else -cur_l,
    }


def disconnect_summary(df: pd.DataFrame) -> dict:
    if df.empty or "disconnected" not in df.columns:
        return {"available": False}
    total = int(len(df))
    dc = int(df["disconnected"].sum())
    return {
        "available": True,
        "total": total,
        "disconnects": dc,
        "dc_rate": dc / total if total else 0.0,
    }
