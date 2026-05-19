"""Análise de sinergia com teammates — quem realmente ajuda vs quem afunda.

Usa duas fontes:
1. profile.team_mates (já agregado pela API: top 10 mais jogados com WR)
2. match_details (todos os 12 players de cada partida): permite calcular
   qualidade média do time aliado (KDA dos aliados) e do time inimigo, e ver
   se haechanie performa melhor quando o time tá "carregado" ou "fraco".

Insights úteis:
- Top 3 teammates com WR > média
- Bottom 3 com WR < média (sinal de pick/playstyle conflitando)
- Diff de KDA aliados vs inimigos: indica se o matchmaking tá favorável
"""

from __future__ import annotations

import pandas as pd

from data import HaechanieData


def top_teammates(data: HaechanieData, min_matches: int = 3) -> pd.DataFrame:
    df = data.team_mates_df
    if df.empty:
        return df
    out = df[df["matches"] >= min_matches].copy()
    return out.sort_values("win_rate", ascending=False)


def teammate_extremes(data: HaechanieData, min_matches: int = 3) -> dict:
    """Retorna top 3 e bottom 3 teammates por WR. Ignora amostras pequenas."""
    df = top_teammates(data, min_matches=min_matches)
    if df.empty:
        return {"available": False}
    best = df.head(3).to_dict("records")
    worst = df.tail(3).sort_values("win_rate").to_dict("records")
    return {
        "available": True,
        "best": best,
        "worst": worst,
        "min_matches": min_matches,
        "total_eligible": int(len(df)),
    }


def per_match_team_quality(data: HaechanieData) -> pd.DataFrame:
    """Pra cada match_detail, computa KDA médio dos 5 aliados (sem haechanie) e dos 6 inimigos.

    Retorna DataFrame com colunas:
        match_id, won, ally_avg_kda, enemy_avg_kda, kda_gap, ally_total_dmg, enemy_total_dmg
    """
    me_uid = data.player_uid
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

        allies = [p for p in players if p.get("camp") == my_camp and int(p.get("player_uid") or 0) != me_uid]
        enemies = [p for p in players if p.get("camp") != my_camp]

        def kda(p):
            d = max(int(p.get("deaths") or 0), 1)
            return (int(p.get("kills") or 0) + int(p.get("assists") or 0)) / d

        if not allies or not enemies:
            continue
        ally_kda = sum(kda(p) for p in allies) / len(allies)
        enemy_kda = sum(kda(p) for p in enemies) / len(enemies)
        rows.append({
            "match_id": uid,
            "won": my_won,
            "ally_avg_kda": ally_kda,
            "enemy_avg_kda": enemy_kda,
            "kda_gap": ally_kda - enemy_kda,
            "ally_total_dmg": sum(int(p.get("total_hero_damage") or 0) for p in allies),
            "enemy_total_dmg": sum(int(p.get("total_hero_damage") or 0) for p in enemies),
        })
    return pd.DataFrame(rows)


def matchmaking_summary(data: HaechanieData) -> dict:
    """Sumariza: o matchmaking está te dando times melhores ou piores que os inimigos?"""
    df = per_match_team_quality(data)
    if df.empty:
        return {"available": False}

    favorable = df[df["kda_gap"] > 0]
    unfavorable = df[df["kda_gap"] <= 0]

    return {
        "available": True,
        "total": int(len(df)),
        "favorable_matches": int(len(favorable)),
        "unfavorable_matches": int(len(unfavorable)),
        "favorable_share": len(favorable) / len(df) if len(df) else 0,
        "avg_kda_gap": float(df["kda_gap"].mean()),
        "favorable_wr": float(favorable["won"].mean()) if not favorable.empty else None,
        "unfavorable_wr": float(unfavorable["won"].mean()) if not unfavorable.empty else None,
        "ally_kda_mean": float(df["ally_avg_kda"].mean()),
        "enemy_kda_mean": float(df["enemy_avg_kda"].mean()),
    }
