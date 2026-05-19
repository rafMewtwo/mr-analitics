"""Dashboard Marvel Rivals Analytics — versão dedicada ao jogador haechanie.

Carrega TUDO de data/haechanie/*.json (baixado uma vez via fetch_haechanie.py).
Sem inputs, sem API calls em tempo de render — só análise.

Rodar com:
    python run.py

Pra atualizar os dados (puxa tudo de novo da API):
    python fetch_haechanie.py
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics import (
    accuracy,
    climb_plan,
    composition,
    counters,
    efficiency,
    hero_pool,
    highlights,
    insights,
    overview,
    patterns,
    ranked,
    synergy,
    temporal,
    whatif,
)
from data import load_haechanie
from ui.labels import plotly_labels, rename_df
from ui.theme import apply_theme, render_hero, style_plotly

st.set_page_config(page_title="haechanie · MR Analytics", page_icon="🎮", layout="wide",
                   initial_sidebar_state="collapsed")
apply_theme()


# =============================================================================
# Versão original com input de nick (multi-jogador). Mantida comentada — esta
# build é focada exclusivamente em haechanie pra esgotar o tier free da API.
# Pra reativar: descomentar este bloco e remover a chamada a load_haechanie().
# =============================================================================
#
# from api.client import get_default_client
# from storage import db
# from analytics import comparative
# from config import USE_MOCK
#
# @st.cache_data(show_spinner=False)
# def fetch_and_store(username: str, refresh: bool = False) -> tuple[pd.DataFrame, dict]:
#     client = get_default_client()
#     data = client.get_player(username, refresh=refresh)
#     db.upsert_player_data(data)
#     df = db.load_matches(data["player"]["name"])
#     return df, data.get("meta", {})
#
# @st.cache_data(show_spinner=False)
# def build_benchmark(player_name: str, df: pd.DataFrame) -> pd.DataFrame:
#     client = get_default_client()
#     return comparative.benchmark_player_heroes(df, client, min_matches=3)
#
# with st.sidebar:
#     st.header("Jogador")
#     username = st.text_input("Nick", key="nick_input", placeholder="ex: Sypeh")
#     analyze = st.button("Analisar", type="primary", use_container_width=True)
#     refresh = st.button("🔄 Refresh da API", use_container_width=True)
# =============================================================================


# ===== Cached loader =====

@st.cache_resource(show_spinner=False)
def get_data():
    return load_haechanie()


# ===== Render helpers =====

def render_header_metrics(data, df: pd.DataFrame) -> None:
    summary = overview.summary(df)
    eff = efficiency.efficiency_summary(df[~df["disconnected"]] if "disconnected" in df.columns else df)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Rank", data.rank or "—")
    c2.metric("Partidas", summary["matches"])
    c3.metric("Win Rate", f"{summary['win_rate']*100:.1f}%")
    c4.metric("KDA", f"{summary['kda']:.2f}")
    c5.metric("Dano/min", f"{eff.get('damage_per_min', 0):,.0f}")
    c6.metric("Heróis usados", summary["unique_heroes"])
    if summary.get("disconnects_excluded", 0):
        st.caption(f"⚠️ {summary['disconnects_excluded']} partida(s) com DC excluída(s) das métricas")


def tab_climb_plan(data) -> None:
    """Plano de climb data-driven com impacto quantificado."""
    plan = climb_plan.actionable_plan(data)
    proj = plan["projection"]
    best = plan["best_pick"]
    drain = plan["worst_drain"]

    st.subheader("🎯 Próximo objetivo")
    if proj:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("MR atual", f"{proj['current_mr']:,.0f}")
        c2.metric("Próxima divisão", f"{proj['next_tier_mr']:,.0f}",
                  delta=f"{proj['gap']:.0f} MR pra ir")
        c3.metric("MR médio/partida (últimas 20)",
                  f"{proj['avg_per_match']:+.1f}",
                  help="Saldo médio de MR ganho/perdido por partida no ritmo atual")
        if proj.get("matches_needed"):
            c4.metric("Partidas até subir", f"~{proj['matches_needed']}",
                      help=f"No ritmo atual de {proj['avg_per_match']:+.1f} MR/partida.")
        else:
            c4.metric("Status", "🚧 Estagnado",
                      help=proj.get("blocked_reason", "MR negativo no ritmo atual"))

    st.divider()

    st.subheader("💡 Recomendações com impacto estimado")

    if best:
        uplift = best["theoretical_uplift_pp"]
        cons = best["conservative_uplift_pp"]
        st.success(
            f"**Foque em {best['hero']}** ({best['role']}) — sua WR com ele é "
            f"**{best['win_rate']*100:.0f}%** sobre {best['matches']} partidas. "
            f"Sua WR overall é **{best['current_overall_wr']*100:.0f}%**.  \n"
            f"Se você jogar mais ranqueada com {best['hero']}, "
            f"o impacto esperado é de **+{cons:.1f}pp a +{uplift:.1f}pp** de win rate."
        )

    if drain and drain["matches"] >= 5 and drain["win_rate"] < 0.45:
        st.warning(
            f"**Reduza {drain['hero']}** ({drain['role']}) — apesar de ter jogado "
            f"{drain['matches']} partidas com ele, sua WR é só **{drain['win_rate']*100:.0f}%**. "
            f"É o herói que mais consome seu tempo sem retorno. Considere treinar em casual antes."
        )

    # =====  best_pick × accuracy ===== #
    acc_summary = accuracy.accuracy_summary(data)
    if acc_summary.get("available"):
        if acc_summary["worst_delta_pp"] < -15:
            st.error(
                f"🎯 **Sua precisão com {acc_summary['worst_hero']} é "
                f"{acc_summary['worst_delta_pp']:+.0f}pp abaixo da média global**. "
                f"Esse é um herói que depende de mira — considere cortar do pool até treinar."
            )
        if acc_summary["best_delta_pp"] > 5:
            st.success(
                f"🎯 Sua precisão com **{acc_summary['best_hero']}** é "
                f"**{acc_summary['best_delta_pp']:+.0f}pp acima da média global**. "
                f"Domínio mecânico forte — explore mais esse herói."
            )

    st.divider()

    # ===== Matchmaking factor ===== #
    st.subheader("🎲 Fator matchmaking")
    mm = synergy.matchmaking_summary(data)
    if mm.get("available"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Partidas com time forte",
                  f"{mm['favorable_matches']}/{mm['total']}",
                  delta=f"WR {(mm['favorable_wr'] or 0)*100:.0f}%" if mm["favorable_wr"] else None)
        c2.metric("Partidas com time fraco",
                  f"{mm['unfavorable_matches']}/{mm['total']}",
                  delta=f"WR {(mm['unfavorable_wr'] or 0)*100:.0f}%" if mm["unfavorable_wr"] else None)
        gap_pp = (mm["favorable_wr"] or 0) * 100 - (mm["unfavorable_wr"] or 0) * 100
        c3.metric("Gap de WR", f"{gap_pp:+.0f}pp",
                  help="Diferença de win rate entre partidas com team forte vs fraco. >50pp = matchmaking pesa muito.")
        if gap_pp > 50:
            st.info(
                f"📊 **O time importa muito**: quando o time aliado tem KDA acima do inimigo, "
                f"você vence **{(mm['favorable_wr'] or 0)*100:.0f}%**; quando está abaixo, só "
                f"**{(mm['unfavorable_wr'] or 0)*100:.0f}%**. "
                f"Não dá pra mudar o matchmaking, mas dá pra: (a) maximizar carry quando time é fraco "
                f"escolhendo Duelist alto-impacto, (b) jogar de pareado pra ter pelo menos 1 player garantido."
            )


def tab_insights(df: pd.DataFrame) -> None:
    result = insights.generate_insights(df)
    col_pos, col_neg = st.columns(2)
    with col_pos:
        st.subheader("✅ Pontos fortes")
        for s in result["strengths"]:
            st.success(s)
    with col_neg:
        st.subheader("⚠️ Pontos a melhorar")
        for w in result["weaknesses"]:
            st.warning(w)
    st.subheader("🎯 Recomendações")
    for r in result["recommendations"]:
        st.info(r)


def tab_synergy(data) -> None:
    st.subheader("🤝 Sinergia com teammates")
    st.caption("Heróis aparecem pouco aqui — esses são *jogadores* (nicks) que entraram no seu time mais de uma vez.")

    ext = synergy.teammate_extremes(data, min_matches=2)
    if not ext.get("available"):
        st.info("Sem teammates com 2+ partidas — amostra ainda pequena.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🟢 Melhores parceiros (WR alta)**")
            for tm in ext["best"]:
                st.success(
                    f"**{tm['nick']}** — {tm['wins']}/{tm['matches']} "
                    f"({tm['win_rate']*100:.0f}% WR)"
                )
        with col2:
            st.markdown("**🔴 Piores parceiros (WR baixa)**")
            for tm in ext["worst"]:
                st.error(
                    f"**{tm['nick']}** — {tm['wins']}/{tm['matches']} "
                    f"({tm['win_rate']*100:.0f}% WR)"
                )

    st.divider()
    st.subheader("📊 Qualidade do time aliado vs inimigo")
    pt = synergy.per_match_team_quality(data)
    if not pt.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pt["ally_avg_kda"], y=pt["enemy_avg_kda"],
            mode="markers",
            marker=dict(
                size=12,
                color=["#00ff9d" if w else "#ff2d5f" for w in pt["won"]],
                line=dict(width=1, color="white"),
            ),
            text=["Vitória" if w else "Derrota" for w in pt["won"]],
            hovertemplate="Aliados KDA: %{x:.2f}<br>Inimigos KDA: %{y:.2f}<br>%{text}<extra></extra>",
        ))
        max_v = max(pt["ally_avg_kda"].max(), pt["enemy_avg_kda"].max()) * 1.1
        fig.add_shape(type="line", x0=0, y0=0, x1=max_v, y1=max_v,
                      line=dict(color="rgba(255,255,255,0.2)", dash="dash"))
        fig.update_xaxes(title="KDA médio dos aliados")
        fig.update_yaxes(title="KDA médio dos inimigos")
        st.plotly_chart(style_plotly(fig).update_layout(height=380), use_container_width=True)
        st.caption(
            "🟢 verde = vitória · 🔴 vermelho = derrota · "
            "linha tracejada = equilíbrio. Pontos acima da linha = time inimigo melhor."
        )


def tab_counters(data) -> None:
    st.subheader("⚔️ Matchups: contra quais heróis você apanha mais")

    hardest = counters.hardest_matchups(data, min_matches=3, n=8)
    easiest = counters.easiest_matchups(data, min_matches=3, n=8)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🔴 Counters (WR mais baixa)**")
        if not hardest.empty:
            display = hardest[["hero", "role", "matches", "win_rate"]].copy()
            display["WR"] = display["win_rate"].apply(lambda v: f"{v*100:.0f}%")
            display = display.rename(columns={"hero": "Herói inimigo", "role": "Role", "matches": "Encontros"})
            st.dataframe(display[["Herói inimigo", "Role", "Encontros", "WR"]],
                         use_container_width=True, hide_index=True)
    with col2:
        st.markdown("**🟢 Easy matchups (WR mais alta)**")
        if not easiest.empty:
            display = easiest[["hero", "role", "matches", "win_rate"]].copy()
            display["WR"] = display["win_rate"].apply(lambda v: f"{v*100:.0f}%")
            display = display.rename(columns={"hero": "Herói inimigo", "role": "Role", "matches": "Encontros"})
            st.dataframe(display[["Herói inimigo", "Role", "Encontros", "WR"]],
                         use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("📊 WR contra cada role inimigo")
    by_role = counters.matchup_by_role(data)
    if not by_role.empty:
        fig = px.bar(by_role, x="role", y="win_rate",
                     hover_data=["heroes_faced", "total_matches"],
                     color="win_rate", color_continuous_scale="RdYlGn", range_color=[0, 1],
                     labels=plotly_labels("role", "win_rate"))
        fig.update_yaxes(tickformat=".0%", range=[0, 1])
        st.plotly_chart(style_plotly(fig), use_container_width=True)


def tab_composition(data) -> None:
    st.subheader("👥 Team comp aliada — o que funciona pra você")
    summary = composition.comp_summary(data)
    if summary.get("available"):
        c1, c2, c3, c4 = st.columns(4)

        def fmt_wr(d):
            if d["wr"] is None:
                return "—"
            return f"{d['wr']*100:.0f}%"

        c1.metric("Standard (2-2-2)",
                  f"{summary['standard_222']['matches']} partidas",
                  delta=fmt_wr(summary["standard_222"]),
                  help="2 Vanguard / 2 Duelist / 2 Strategist")
        c2.metric("Solo tank",
                  f"{summary['solo_tank']['matches']} partidas",
                  delta=fmt_wr(summary["solo_tank"]))
        c3.metric("Sem tank",
                  f"{summary['no_tank']['matches']} partidas",
                  delta=fmt_wr(summary["no_tank"]))
        c4.metric("Sem support",
                  f"{summary['no_support']['matches']} partidas",
                  delta=fmt_wr(summary["no_support"]))

    st.divider()
    st.subheader("🎭 WR por role que VOCÊ jogou")
    wrr = composition.win_rate_by_role_played(data)
    if not wrr.empty:
        fig = px.bar(wrr, x="my_role", y="win_rate",
                     hover_data=["matches"],
                     color="win_rate", color_continuous_scale="RdYlGn", range_color=[0, 1],
                     text="matches",
                     labels={"my_role": "Sua role na partida", "win_rate": "Win Rate", "matches": "Partidas"})
        fig.update_traces(textposition="outside")
        fig.update_yaxes(tickformat=".0%", range=[0, 1])
        st.plotly_chart(style_plotly(fig), use_container_width=True)

    st.divider()
    st.subheader("📋 Detalhe por comp aliada (>=2 partidas)")
    by_comp = composition.win_rate_by_ally_comp(data)
    if not by_comp.empty:
        by_comp = by_comp[by_comp["matches"] >= 2]
        if not by_comp.empty:
            display = by_comp.copy()
            display["WR"] = display["win_rate"].apply(lambda v: f"{v*100:.0f}%")
            display = display.rename(columns={
                "ally_comp": "Composição aliada", "matches": "Partidas", "wins": "Vitórias",
            })
            st.dataframe(display[["Composição aliada", "Partidas", "Vitórias", "WR"]],
                         use_container_width=True, hide_index=True)


def tab_accuracy(data) -> None:
    st.subheader("🎯 Precisão (hit rate) — sua vs média global")
    st.caption(
        "Compara seu hit rate em cada herói com o `session_hit_rate` global da API. "
        "Heróis com mira (Squirrel Girl, Hawkeye, Iron Man) são onde isso impacta mais."
    )

    av = accuracy.accuracy_vs_global(data)
    if av.empty:
        st.info("Sem dados de hit rate.")
        return

    valid = av.dropna(subset=["your_accuracy", "global_accuracy"]).copy()
    if valid.empty:
        st.info("Sem heróis com hit rate registrado e benchmark global.")
        return

    valid["WR_você"] = valid["your_accuracy"].apply(lambda v: f"{v*100:.1f}%")
    valid["WR_global"] = valid["global_accuracy"].apply(lambda v: f"{v*100:.1f}%" if v else "—")
    valid["Δ"] = valid["delta_pp"].apply(lambda v: f"{v:+.1f}pp")

    fig = px.bar(valid.sort_values("delta_pp"), x="hero", y="delta_pp",
                 color="delta_pp", color_continuous_scale="RdYlGn", range_color=[-30, 30],
                 hover_data=["matches", "your_accuracy", "global_accuracy"],
                 labels={"hero": "Herói", "delta_pp": "Δ vs global (pp)"})
    fig.update_layout(showlegend=False)
    st.plotly_chart(style_plotly(fig), use_container_width=True)

    st.dataframe(
        valid[["hero", "role", "matches", "WR_você", "WR_global", "Δ"]]
        .rename(columns={"hero": "Herói", "role": "Role", "matches": "Partidas"}),
        use_container_width=True, hide_index=True,
    )


def tab_climb_mr(df: pd.DataFrame) -> None:
    st.subheader("📈 Trajetória de MR")
    traj = ranked.mr_trajectory(df)
    if traj.empty:
        st.info("Sem dados de MR/score. Pode ser que essas partidas não sejam de ranqueada.")
        return

    fig = px.line(traj, x="played_at", y="new_score", markers=True)
    fig.update_layout(xaxis_title="", yaxis_title="Rank Score")
    st.plotly_chart(style_plotly(fig), use_container_width=True)

    st.subheader("💰 MR ganho/perdido")
    summary = ranked.mr_summary(df)
    if summary.get("available"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("MR médio por vitória", f"{summary['avg_mr_per_win']:+.1f}")
        c2.metric("MR médio por derrota", f"{summary['avg_mr_per_loss']:+.1f}")
        c3.metric("Assimetria", f"{summary['asymmetry']:+.1f}",
                  help=">0 = ganha mais MR do que perde. Saudável.")
        c4.metric("Saldo total", f"{summary['total_mr_change']:+.0f}")

    st.subheader("🦸 MR por herói")
    mh = ranked.mr_by_hero(df)
    if not mh.empty:
        display = rename_df(
            mh[["hero", "role", "matches", "win_rate", "avg_mr", "total_mr", "enough_data"]]
        )
        st.dataframe(
            display.style.format({
                "Win Rate": "{:.1%}", "MR médio": "{:+.1f}", "MR total": "{:+.0f}",
            }),
            use_container_width=True,
        )

    st.subheader("🏅 MVP / SVP rate")
    mvp = highlights.mvp_summary(df)
    if mvp.get("available"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("MVPs", mvp["mvp_count"])
        c2.metric("SVPs", mvp["svp_count"])
        c3.metric("MVP em vitórias", f"{mvp['mvp_rate_in_wins']*100:.0f}%")
        c4.metric("Taxa de pódio", f"{mvp['podium_rate']*100:.0f}%")


def tab_heroes(data, df: pd.DataFrame) -> None:
    hs = hero_pool.hero_stats(df)
    eff_df = efficiency.per_match_efficiency(df[~df["disconnected"]] if "disconnected" in df.columns else df)
    by_hero_eff = (
        eff_df.groupby("hero")
        .agg(
            dmg_min=("damage_per_min", "mean"),
            heal_min=("healing_per_min", "mean"),
            taken_min=("taken_per_min", "mean"),
        )
        .reset_index()
    )

    st.subheader("Performance por herói (suas partidas)")
    merged = hs.merge(by_hero_eff, on="hero", how="left")
    display = rename_df(
        merged[["hero", "role", "matches", "wins", "win_rate", "kda",
                "dmg_min", "heal_min", "taken_min"]]
    )
    st.dataframe(
        display.style.format({
            "Win Rate": "{:.1%}", "KDA": "{:.2f}",
            "Dano/min": "{:,.0f}", "Cura/min": "{:,.0f}", "Dano tomado/min": "{:,.0f}",
        }),
        use_container_width=True,
    )

    col_dist, col_conc = st.columns([2, 1])
    with col_dist:
        st.subheader("Distribuição por role")
        rd = hero_pool.role_distribution(df)
        fig = px.bar(rd, x="role", y="matches", color="win_rate",
                     color_continuous_scale="RdYlGn", range_color=[0, 1],
                     text="matches",
                     labels=plotly_labels("role", "matches", "win_rate"))
        fig.update_traces(textposition="outside")
        styled = style_plotly(fig)
        styled.update_layout(height=260, showlegend=False)
        st.plotly_chart(styled, use_container_width=True)
    with col_conc:
        st.subheader("Concentração")
        conc = hero_pool.concentration_index(df)
        st.metric("Índice do pool", f"{conc:.2f}",
                  help="0 = totalmente disperso, 1 = one-trick. Ideal: 0.20-0.50")
        if conc < 0.10:
            st.caption("🔄 Pool muito disperso")
        elif conc > 0.50:
            st.caption("🎯 Pool focado")
        else:
            st.caption("⚖️ Pool balanceado")


def tab_maps(df: pd.DataFrame) -> None:
    mp = patterns.map_performance(df)
    st.subheader("Win rate por mapa")
    if not mp.empty:
        fig = px.bar(mp, x="map", y="win_rate",
                     hover_data=["matches"],
                     color="win_rate", color_continuous_scale="RdYlGn",
                     range_color=[0, 1],
                     labels=plotly_labels("map", "win_rate", "matches"))
        fig.update_yaxes(tickformat=".0%", range=[0, 1])
        st.plotly_chart(style_plotly(fig), use_container_width=True)

    st.subheader("🗺️ Hero × Map")
    hm = patterns.hero_map_matrix(df)
    if hm.empty:
        st.info("Sem combinações herói×mapa com partidas suficientes ainda.")
    else:
        pivot = hm.pivot(index="hero", columns="map", values="win_rate")
        fig = go.Figure(data=go.Heatmap(
            z=pivot.values, x=pivot.columns, y=pivot.index,
            colorscale="RdYlGn", zmin=0, zmax=1,
            text=pivot.values, texttemplate="%{text:.0%}", hoverongaps=False,
        ))
        fig.update_xaxes(title="Mapa")
        fig.update_yaxes(title="Herói")
        st.plotly_chart(style_plotly(fig).update_layout(height=400), use_container_width=True)

    st.subheader("🥊 Close games vs blowouts")
    cb = patterns.close_vs_blowout(df)
    if cb.get("available"):
        c1, c2 = st.columns(2)
        c1.metric(f"Close games ({cb['close_matches']})", f"{cb['close_win_rate']*100:.0f}% WR",
                  help="Partidas com diferença de até 1 round")
        c2.metric(f"Blowouts ({cb['blowout_matches']})", f"{cb['blowout_win_rate']*100:.0f}% WR",
                  help="Partidas com diferença de 2+ rounds")


def tab_temporal_section(df: pd.DataFrame) -> None:
    sub = df[~df["disconnected"]] if "disconnected" in df.columns else df

    st.subheader("Win rate por horário")
    by_hour = temporal.win_rate_by_hour(sub)
    fig = px.bar(by_hour, x="hour", y="win_rate",
                 hover_data=["matches"],
                 color="win_rate", color_continuous_scale="RdYlGn", range_color=[0, 1],
                 labels=plotly_labels("hour", "win_rate", "matches"))
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    st.plotly_chart(style_plotly(fig), use_container_width=True)

    st.subheader("Win rate por dia da semana")
    by_wd = temporal.win_rate_by_weekday(sub)
    fig = px.bar(by_wd, x="weekday_name", y="win_rate",
                 hover_data=["matches"],
                 color="win_rate", color_continuous_scale="RdYlGn", range_color=[0, 1],
                 labels=plotly_labels("weekday_name", "win_rate", "matches"))
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    st.plotly_chart(style_plotly(fig), use_container_width=True)

    col1, col2, col3 = st.columns(3)
    tilt = temporal.detect_tilt(sub)
    late = temporal.late_night_drop(sub)
    fatigue = temporal.session_fatigue(sub)
    for col, name, result in [
        (col1, "Tilt (pós 2 derrotas)", tilt),
        (col2, "Madrugada (>=23h)", late),
        (col3, "Fadiga em sessão", fatigue),
    ]:
        with col:
            st.markdown(f"**{name}**")
            if result.get("detected"):
                st.error(f"Detectado: {result['delta_pp']:+.1f}pp")
            elif "delta_pp" in result:
                st.success(f"Sem queda: {result['delta_pp']:+.1f}pp")
            else:
                st.caption(result.get("reason", "sem dados"))


def tab_whatif(df: pd.DataFrame) -> None:
    impact = whatif.estimate_impact(df)
    if impact is None:
        st.info("Precisa de pelo menos 6 partidas pra calcular impacto estimado.")
        return
    if not impact.get("available"):
        st.success("✨ Você já não tem partidas em condições 'remediaveis'. Continue assim.")
        return

    st.markdown(
        "**Premissa:** se você seguisse as recomendações geradas (evitar madrugada + "
        "pausar após 2 derrotas), as partidas em condições ruins performariam como as boas."
    )

    st.subheader("📊 Antes vs Depois")
    c1, c2, c3 = st.columns(3)
    c1.metric("Win rate atual", f"{impact['current_wr']*100:.1f}%")
    c2.metric("Win rate projetado", f"{impact['projected_wr']*100:.1f}%",
              delta=f"{impact['wr_uplift_pp']:+.1f}pp")
    low, high = whatif.conservative_range(impact)
    c3.metric("Estimativa conservadora", f"+{low:.1f} a +{high:.1f}pp",
              help="70-100% do uplift teórico — desconto pra confounds e regressão à média.")

    if impact.get("mr"):
        st.subheader("💰 Impacto em MR")
        mr = impact["mr"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Saldo atual de MR", f"{mr['current_total']:+.0f}")
        c2.metric("Saldo projetado", f"{mr['projected_total']:+.0f}",
                  delta=f"{mr['uplift']:+.0f} MR")
        c3.metric("Vitórias 'flipped'", f"{impact['wins_flipped']:+.1f}")
        c4.metric("MR por flip", f"{mr['mr_per_flip']:+.1f}")

        mr_low, mr_high = whatif.conservative_mr_range(impact)
        if mr_high > 0:
            st.success(
                f"💡 Estimativa conservadora: ganho de **{mr_low:+.0f} a {mr_high:+.0f} MR** "
                f"ao longo das próximas {impact['total_matches']} partidas."
            )


def tab_overview_section(df: pd.DataFrame) -> None:
    sub = df[~df["disconnected"]] if "disconnected" in df.columns else df
    st.subheader("Evolução do win rate (média móvel de 10 partidas)")
    df_sorted = sub.sort_values("played_at").reset_index(drop=True)
    df_sorted["rolling_wr"] = df_sorted["won"].rolling(10, min_periods=3).mean()
    fig = px.line(df_sorted, x="played_at", y="rolling_wr",
                  labels=plotly_labels("played_at", "rolling_wr"))
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    st.plotly_chart(style_plotly(fig), use_container_width=True)

    st.subheader("Streaks")
    s = patterns.streaks(df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Maior win streak", s.get("longest_win_streak", 0))
    c2.metric("Maior loss streak", s.get("longest_loss_streak", 0))
    cur = s.get("current_streak", 0)
    c3.metric("Streak atual", f"{abs(cur)} {'V' if cur >= 0 else 'D'}")

    st.subheader("🏆 Melhores partidas (por KDA)")
    bests = highlights.best_matches(df, n=5)
    if not bests.empty:
        st.dataframe(rename_df(bests).style.format({"KDA": "{:.2f}"}),
                     use_container_width=True)

    st.subheader("💀 Piores partidas")
    worsts = highlights.worst_matches(df, n=5)
    if not worsts.empty:
        st.dataframe(rename_df(worsts).style.format({"KDA": "{:.2f}"}),
                     use_container_width=True)


def main() -> None:
    data = get_data()
    df = data.matches_df

    if df.empty:
        st.error(
            "Nenhuma partida carregada de `data/haechanie/`. "
            "Rode `python fetch_haechanie.py` pra baixar os dados da API."
        )
        st.stop()

    render_hero(
        title=f"haechanie · {data.rank}" if data.rank else "haechanie",
        sub=f"Performance Analytics · {len(df)} partidas · level {data.level}",
        badge=f"Snapshot {data.fetched_at[:10] if data.fetched_at else 'local'}",
        compact=True,
    )

    render_header_metrics(data, df)

    tabs = st.tabs([
        "🎯 Plano de Climb",
        "💡 Insights",
        "🤝 Sinergia",
        "⚔️ Counters",
        "👥 Composição",
        "🎯 Precisão",
        "📈 MR",
        "🦸 Heróis",
        "🗺️ Mapas",
        "🕒 Padrões",
        "🔮 What If",
        "📜 Overview",
    ])
    with tabs[0]:
        tab_climb_plan(data)
    with tabs[1]:
        tab_insights(df)
    with tabs[2]:
        tab_synergy(data)
    with tabs[3]:
        tab_counters(data)
    with tabs[4]:
        tab_composition(data)
    with tabs[5]:
        tab_accuracy(data)
    with tabs[6]:
        tab_climb_mr(df)
    with tabs[7]:
        tab_heroes(data, df)
    with tabs[8]:
        tab_maps(df)
    with tabs[9]:
        tab_temporal_section(df)
    with tabs[10]:
        tab_whatif(df)
    with tabs[11]:
        tab_overview_section(df)


if __name__ == "__main__":
    main()
