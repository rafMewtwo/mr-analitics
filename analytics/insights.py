"""Gera recomendações em linguagem natural a partir das análises.

Combina sinais de: ranked (MR), highlights (MVP), temporal, hero_pool, patterns
(close games, mapas) e disconnect rate.
"""

from __future__ import annotations

import pandas as pd

from analytics import (
    hero_pool,
    highlights,
    patterns,
    ranked,
    temporal,
)


def _no_dc(df: pd.DataFrame) -> pd.DataFrame:
    if "disconnected" in df.columns:
        return df[~df["disconnected"]]
    return df


def generate_insights(df: pd.DataFrame) -> dict[str, list[str]]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str] = []

    if df.empty:
        return {"strengths": [], "weaknesses": [], "recommendations": []}

    sub = _no_dc(df)
    if sub.empty:
        return {"strengths": [], "weaknesses": [], "recommendations": []}

    overall_wr = sub["won"].mean()

    # ===== MR / Climb (Onda 1) =====
    mr_bleed = ranked.detect_mr_bleed(df)
    mr_sum = ranked.mr_summary(df)
    if mr_bleed and mr_bleed.get("bleeding"):
        weaknesses.append(
            f"Você está sangrando MR: ganha {mr_bleed['avg_win']:+.1f} por vitória mas "
            f"perde {mr_bleed['avg_loss']:+.1f} por derrota (assimetria de "
            f"{mr_bleed['asymmetry']:+.1f}). No longo prazo, isso te trava no rank."
        )
        recommendations.append(
            "Dodge ranqueada quando se sentir 'off': em rotas onde voce esta perdendo "
            "mais MR do que ganha, melhor pausar do que continuar acumulando derrotas grandes."
        )
    elif mr_sum.get("available") and mr_sum["asymmetry"] > 3:
        strengths.append(
            f"Climb saudável: você ganha em média {mr_sum['avg_mr_per_win']:+.1f} MR por vitória "
            f"e perde só {mr_sum['avg_mr_per_loss']:+.1f} por derrota."
        )

    # ===== MVP rate =====
    mvp = highlights.mvp_summary(df)
    if mvp.get("available"):
        if mvp["mvp_rate_in_wins"] > 0.35:
            strengths.append(
                f"Você carrega: MVP em {mvp['mvp_rate_in_wins']*100:.0f}% das suas vitórias "
                f"({mvp['mvp_count']} MVP + {mvp['svp_count']} SVP no total)."
            )
        elif mvp["podium_rate"] < 0.10 and mvp["matches"] >= 10:
            weaknesses.append(
                f"Quase nunca pódio (MVP+SVP em só {mvp['podium_rate']*100:.0f}% das partidas). "
                f"Você ganha junto com o time mas não está sendo o diferencial."
            )

    # ===== Tilt =====
    tilt = temporal.detect_tilt(sub)
    if tilt.get("detected"):
        weaknesses.append(
            f"Você entra em tilt: após 2 derrotas seguidas seu win rate cai "
            f"{abs(tilt['delta_pp']):.1f}pp (de {tilt['overall_wr']*100:.0f}% para "
            f"{tilt['post_2L_wr']*100:.0f}%)."
        )
        recommendations.append(
            "Faça uma pausa de 15-20 min após 2 derrotas seguidas — seus dados mostram "
            "que continuar tende a piorar o desempenho."
        )

    # ===== Fadiga em sessão =====
    fatigue = temporal.session_fatigue(sub)
    if fatigue.get("detected"):
        weaknesses.append(
            f"Fadiga em sessões longas: a partir da 4ª partida seguida seu win rate cai "
            f"de {fatigue['early_wr']*100:.0f}% para {fatigue['late_wr']*100:.0f}%."
        )
        recommendations.append(
            "Limite sessões a 3 partidas seguidas; faça uma pausa real antes de continuar."
        )

    # ===== Horário tardio =====
    late = temporal.late_night_drop(sub)
    if late.get("detected"):
        weaknesses.append(
            f"Você joga pior tarde da noite: win rate de {late['late_wr']*100:.0f}% "
            f"depois das 23h vs {late['other_wr']*100:.0f}% no resto do dia."
        )
        recommendations.append(
            "Evite ranqueada depois das 23h. Use esse horário para casual ou treino."
        )

    # ===== Hero pool =====
    hero_summary = hero_pool.anchor_and_sinker(sub)
    if hero_summary["anchor"] and hero_summary["anchor"]["win_rate"] > overall_wr + 0.08:
        a = hero_summary["anchor"]
        strengths.append(
            f"Seu herói âncora é {a['hero']}: {a['win_rate']*100:.0f}% de win rate em "
            f"{a['matches']} partidas (acima da sua média de {overall_wr*100:.0f}%)."
        )
        recommendations.append(
            f"Em partidas decisivas (promoção, série), priorize {a['hero']} quando o "
            f"comp permitir."
        )

    if hero_summary["sinker"] and hero_summary["sinker"]["win_rate"] < overall_wr - 0.10:
        s = hero_summary["sinker"]
        weaknesses.append(
            f"{s['hero']} está te puxando para baixo: {s['win_rate']*100:.0f}% em "
            f"{s['matches']} partidas."
        )
        recommendations.append(
            f"Tire {s['hero']} da rotação de ranqueada até treinar mais em modos casuais."
        )

    # ===== Concentração =====
    conc = hero_pool.concentration_index(sub)
    if conc < 0.10:
        weaknesses.append(
            "Seu pool é muito disperso — você não tem maestria clara em nenhum herói."
        )
        recommendations.append(
            "Escolha 2-3 heróis principais (1 por role) e foque neles por algumas semanas."
        )
    elif conc > 0.50:
        strengths.append("Você tem um pool focado, com clara especialização.")
        recommendations.append(
            "Tenha pelo menos 1 secundário por role para evitar contra-pick / ban."
        )

    # ===== Mapas =====
    map_perf = patterns.map_performance(sub)
    if not map_perf.empty:
        weak_maps = map_perf[(map_perf["enough_data"]) & (map_perf["win_rate"] < overall_wr - 0.15)]
        for _, row in weak_maps.iterrows():
            weaknesses.append(
                f"Mapa {row['map']}: apenas {row['win_rate']*100:.0f}% de win rate em "
                f"{row['matches']} partidas."
            )
            recommendations.append(
                f"Estude {row['map']} — assista VODs, foque em rotação e pontos de engage."
            )

    # ===== Close games =====
    cb = patterns.close_vs_blowout(sub)
    if cb.get("available") and cb["close_matches"] >= 3:
        if cb["close_win_rate"] < 0.40:
            weaknesses.append(
                f"Você perde jogos apertados: só {cb['close_win_rate']*100:.0f}% de WR "
                f"em {cb['close_matches']} partidas com diferença de até 1 round."
            )
            recommendations.append(
                "Foque em comunicação clara nos finais de round. Close games se ganham "
                "no shot call, não no mecânico."
            )
        elif cb["close_win_rate"] > 0.60:
            strengths.append(
                f"Clutch: você vence {cb['close_win_rate']*100:.0f}% dos jogos apertados."
            )

    # ===== Loss profile =====
    loss = patterns.loss_profile(sub)
    if loss.get("available") and loss["damage_drop_pct"] > 30:
        weaknesses.append(
            f"Em derrotas seu damage cai {loss['damage_drop_pct']:.0f}% — sinal de "
            f"desengajamento quando o time está atrás."
        )
        recommendations.append(
            "Quando estiver perdendo, mantenha pressão de farm/dano em vez de recuar."
        )

    # ===== DC =====
    dc = patterns.disconnect_summary(df)
    if dc.get("available") and dc["dc_rate"] > 0.05:
        weaknesses.append(
            f"Taxa de desconexão alta ({dc['dc_rate']*100:.1f}%, "
            f"{dc['disconnects']} partidas). Pode estar mascarando suas estatísticas reais."
        )
        recommendations.append(
            "Verifique conexão/PC. DCs em ranked custam MR e podem causar penalidades."
        )

    if not strengths:
        strengths.append("Continue acumulando partidas para revelar padrões mais claros.")

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
    }
