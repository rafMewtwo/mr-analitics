"""Benchmark contra médias globais via /hero-stats.

Para cada herói único no histórico, busca métricas globais e compara
com a média do jogador. Resultado: 'você joga X% melhor/pior que a média'.

Faz lazy fetch e usa cache do client (lru_cache).
"""

from __future__ import annotations

import pandas as pd

from analytics.efficiency import per_match_efficiency


def _parse_play_time_seconds(text: str | None) -> float:
    """Converte '836h 1m 3s' em segundos."""
    if not text or not isinstance(text, str):
        return 0.0
    total = 0
    for part in text.split():
        if part.endswith("h"):
            total += int(part[:-1]) * 3600
        elif part.endswith("m"):
            total += int(part[:-1]) * 60
        elif part.endswith("s"):
            total += int(part[:-1])
    return float(total)


def global_hero_avg(global_stats: dict) -> dict:
    """Reduz o payload de /hero-stats em médias per-match comparáveis."""
    if not global_stats:
        return {}
    matches = global_stats.get("matches", 0) or 0
    if matches == 0:
        return {}
    play_time_s = _parse_play_time_seconds(global_stats.get("play_time"))
    avg_duration_s = play_time_s / matches if matches else 0
    avg_duration_min = avg_duration_s / 60 if avg_duration_s else 1

    avg_damage = (global_stats.get("total_hero_damage") or 0) / matches
    avg_heal = (global_stats.get("total_hero_heal") or 0) / matches
    avg_taken = (global_stats.get("total_damage_taken") or 0) / matches
    return {
        "matches": matches,
        "win_rate": (global_stats.get("wins") or 0) / matches,
        "k": global_stats.get("k"),
        "d": global_stats.get("d"),
        "a": global_stats.get("a"),
        "kda": (
            ((global_stats.get("k") or 0) + (global_stats.get("a") or 0))
            / max(global_stats.get("d") or 1, 0.01)
        ),
        "avg_damage": avg_damage,
        "avg_heal": avg_heal,
        "avg_taken": avg_taken,
        "damage_per_min": avg_damage / max(avg_duration_min, 1),
        "healing_per_min": avg_heal / max(avg_duration_min, 1),
        "taken_per_min": avg_taken / max(avg_duration_min, 1),
        "session_hit_rate": global_stats.get("session_hit_rate"),
        "solo_kill": global_stats.get("solo_kill"),
    }


def benchmark_player_heroes(df: pd.DataFrame, client, min_matches: int = 3) -> pd.DataFrame:
    """Para cada herói com partidas >= min_matches, busca stats globais e compara.

    Retorna DF com colunas: hero, role, matches, you_kda, global_kda, kda_delta_pct,
    you_dmg_min, global_dmg_min, dmg_delta_pct, etc.
    """
    if df.empty or "hero_id" not in df.columns:
        return pd.DataFrame()

    eff = per_match_efficiency(df)
    rows = []
    for (hero, hero_id), g in eff.groupby(["hero", "hero_id"]):
        if len(g) < min_matches or pd.isna(hero_id):
            continue
        global_stats = client.get_hero_stats(int(hero_id))
        if not global_stats:
            continue
        glob = global_hero_avg(global_stats)
        if not glob:
            continue

        you_k = float(g["kills"].mean())
        you_d = float(g["deaths"].mean())
        you_a = float(g["assists"].mean())
        you_kda = (you_k + you_a) / max(you_d, 0.01)
        you_dmg_min = float(g["damage_per_min"].mean())
        you_heal_min = float(g["healing_per_min"].mean())
        you_taken_min = float(g["taken_per_min"].mean())

        def pct(you, base):
            if not base or base == 0:
                return None
            return (you - base) / base * 100

        rows.append({
            "hero": hero,
            "role": g["role"].iloc[0],
            "matches": int(len(g)),
            "your_win_rate": float(g["won"].mean()),
            "global_win_rate": glob["win_rate"],
            "your_kda": you_kda,
            "global_kda": glob["kda"],
            "kda_delta_pct": pct(you_kda, glob["kda"]),
            "your_dmg_min": you_dmg_min,
            "global_dmg_min": glob["damage_per_min"],
            "dmg_delta_pct": pct(you_dmg_min, glob["damage_per_min"]),
            "your_heal_min": you_heal_min,
            "global_heal_min": glob["healing_per_min"],
            "heal_delta_pct": pct(you_heal_min, glob["healing_per_min"]),
            "your_taken_min": you_taken_min,
            "global_taken_min": glob["taken_per_min"],
        })
    return pd.DataFrame(rows).sort_values("kda_delta_pct", ascending=False, na_position="last")
