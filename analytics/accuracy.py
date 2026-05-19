"""Accuracy analysis: hit rate por herói vs média global.

Fontes:
- profile.heroes_ranked tem `main_attack.hits / total` -> accuracy
- hero_stats.{id}.session_hit_rate -> média global por herói (de TODOS os jogadores)

Comparativo: "sua precisão com Cloak & Dagger é X% — média global é Y%"
"""

from __future__ import annotations

import pandas as pd

from data import HaechanieData


def accuracy_vs_global(data: HaechanieData) -> pd.DataFrame:
    df = data.heroes_ranked_df.copy()
    if df.empty:
        return df

    rows = []
    for _, r in df.iterrows():
        hid = r["hero_id"]
        global_stats = data.hero_stats.get(int(hid) if hid else -1, {})
        global_hit = global_stats.get("session_hit_rate")
        your_hit = r.get("accuracy")
        if your_hit is None and not global_hit:
            continue
        rows.append({
            "hero": r["hero"],
            "role": r["role"],
            "matches": r["matches"],
            "your_accuracy": your_hit,
            "global_accuracy": global_hit,
            "delta_pp": (your_hit - global_hit) * 100 if (your_hit is not None and global_hit) else None,
        })
    return pd.DataFrame(rows)


def accuracy_summary(data: HaechanieData) -> dict:
    df = accuracy_vs_global(data)
    if df.empty:
        return {"available": False}
    # Considera apenas heróis com ambas as métricas e amostra >= 2
    valid = df.dropna(subset=["your_accuracy", "global_accuracy"])
    valid = valid[valid["matches"] >= 2]
    if valid.empty:
        return {"available": False}
    avg_delta = float(valid["delta_pp"].mean())
    best = valid.sort_values("delta_pp", ascending=False).iloc[0]
    worst = valid.sort_values("delta_pp").iloc[0]
    return {
        "available": True,
        "avg_delta_pp": avg_delta,
        "best_hero": best["hero"],
        "best_delta_pp": float(best["delta_pp"]),
        "worst_hero": worst["hero"],
        "worst_delta_pp": float(worst["delta_pp"]),
        "heroes_compared": int(len(valid)),
    }
