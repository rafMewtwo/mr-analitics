"""Análise de team comp: 2-2-2 funciona pra você? Que role distribution vence?

Usa match_details pra calcular a comp de cada time (allied + enemy) cruzando
hero_id de cada player com o role (Vanguard/Duelist/Strategist) do catálogo.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from data import HaechanieData


def _comp_string(role_count: Counter) -> str:
    """Retorna string tipo '2V-2D-2S' a partir do Counter."""
    v = role_count.get("Vanguard", 0)
    d = role_count.get("Duelist", 0)
    s = role_count.get("Strategist", 0)
    return f"{v}V-{d}D-{s}S"


def per_match_composition(data: HaechanieData) -> pd.DataFrame:
    """Pra cada partida, retorna a comp aliada e inimiga (string tipo 2V-2D-2S)."""
    me_uid = data.player_uid
    heroes_idx = data.heroes_catalog
    rows = []
    for uid, md in data.match_details.items():
        players = md.get("match_players") or []
        me = None
        for p in players:
            if int(p.get("player_uid") or 0) == me_uid:
                me = p
                break
        if me is None:
            continue
        my_camp = me.get("camp")
        my_won = bool(me.get("is_win"))

        ally_roles: Counter[str] = Counter()
        enemy_roles: Counter[str] = Counter()
        for p in players:
            hid = p.get("cur_hero_id")
            if hid is None:
                continue
            role = heroes_idx.get(int(hid), {}).get("role", "Unknown")
            if p.get("camp") == my_camp:
                ally_roles[role] += 1
            else:
                enemy_roles[role] += 1

        rows.append({
            "match_id": uid,
            "won": my_won,
            "my_role": heroes_idx.get(int(me.get("cur_hero_id") or 0), {}).get("role", "Unknown"),
            "ally_comp": _comp_string(ally_roles),
            "enemy_comp": _comp_string(enemy_roles),
            "ally_vanguard": ally_roles.get("Vanguard", 0),
            "ally_duelist": ally_roles.get("Duelist", 0),
            "ally_strategist": ally_roles.get("Strategist", 0),
            "enemy_vanguard": enemy_roles.get("Vanguard", 0),
            "enemy_duelist": enemy_roles.get("Duelist", 0),
            "enemy_strategist": enemy_roles.get("Strategist", 0),
        })
    return pd.DataFrame(rows)


def win_rate_by_ally_comp(data: HaechanieData) -> pd.DataFrame:
    df = per_match_composition(data)
    if df.empty:
        return df
    return (
        df.groupby("ally_comp")
        .agg(matches=("won", "count"), wins=("won", "sum"))
        .reset_index()
        .assign(win_rate=lambda x: x["wins"] / x["matches"].replace(0, 1))
        .sort_values("matches", ascending=False)
    )


def win_rate_by_role_played(data: HaechanieData) -> pd.DataFrame:
    """Quando você joga Vanguard vs Duelist vs Strategist, qual sua WR?"""
    df = per_match_composition(data)
    if df.empty:
        return df
    return (
        df.groupby("my_role")
        .agg(matches=("won", "count"), wins=("won", "sum"))
        .reset_index()
        .assign(win_rate=lambda x: x["wins"] / x["matches"].replace(0, 1))
        .sort_values("matches", ascending=False)
    )


def comp_summary(data: HaechanieData) -> dict:
    df = per_match_composition(data)
    if df.empty:
        return {"available": False}

    standard = df[(df["ally_vanguard"] == 2) & (df["ally_duelist"] == 2) & (df["ally_strategist"] == 2)]
    no_tank = df[df["ally_vanguard"] == 0]
    solo_tank = df[df["ally_vanguard"] == 1]
    triple_tank = df[df["ally_vanguard"] >= 3]
    no_support = df[df["ally_strategist"] == 0]

    def wr(sub):
        return float(sub["won"].mean()) if not sub.empty else None

    return {
        "available": True,
        "total_matches": int(len(df)),
        "standard_222": {"matches": int(len(standard)), "wr": wr(standard)},
        "no_tank": {"matches": int(len(no_tank)), "wr": wr(no_tank)},
        "solo_tank": {"matches": int(len(solo_tank)), "wr": wr(solo_tank)},
        "triple_tank": {"matches": int(len(triple_tank)), "wr": wr(triple_tank)},
        "no_support": {"matches": int(len(no_support)), "wr": wr(no_support)},
    }
