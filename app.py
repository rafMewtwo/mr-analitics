"""Landing page — Marvel Rivals Analytics.

Apenas um resumo visual do projeto. Sem nome de jogador e sem botão que leve
a um perfil específico. As páginas de análise vivem em rotas próprias
(ex: /haechanie, /marinao) acessadas por URL direta.
"""

from __future__ import annotations

import streamlit as st

from ui.theme import apply_theme

st.set_page_config(
    page_title="MR Analytics",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()

# Esconde o menu de páginas do sidebar (não queremos expor as rotas de perfil)
st.markdown(
    """
    <style>
        [data-testid="stSidebar"] {display: none;}
        [data-testid="collapsedControl"] {display: none;}
        section[data-testid="stSidebar"] {display: none;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="landing-wrap">
      <div class="landing-card">
        <div class="landing-badge">● PERFORMANCE ANALYTICS</div>
        <h1 class="landing-title">MARVEL<br/>RIVALS</h1>
        <div class="landing-sub">Data Science aplicada a ranqueada</div>
        <div class="landing-pitch">
          Plataforma de análise de desempenho para Marvel Rivals. A partir do
          histórico de partidas, ela cruza dezenas de sinais — economia de MR,
          precisão por herói, sinergia de time, counters, composição e padrões
          temporais — e transforma tudo em um plano de evolução acionável, com
          impacto estimado em pontos de win rate.
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="landing-foot">
      <div class="landing-foot-cols">
        <div>
          <div class="landing-foot-h">🎯 Plano de Climb</div>
          <div class="landing-foot-p">Quantas partidas até a próxima divisão, qual herói focar, qual cortar — com impacto estimado.</div>
        </div>
        <div>
          <div class="landing-foot-h">⚔️ Counters</div>
          <div class="landing-foot-p">Quais heróis inimigos mais derrotam o jogador e quais são presa fácil.</div>
        </div>
        <div>
          <div class="landing-foot-h">🎯 Precisão</div>
          <div class="landing-foot-p">Hit rate por herói comparado com a média global de todos os jogadores.</div>
        </div>
        <div>
          <div class="landing-foot-h">🤝 Sinergia &amp; Composição</div>
          <div class="landing-foot-p">Qualidade do time aliado vs inimigo e que composição (2-2-2, solo tank...) mais vence.</div>
        </div>
      </div>
      <div class="landing-foot-meta">Powered by MarvelRivalsAPI.com · Snapshot atualizado periodicamente</div>
    </div>
    """,
    unsafe_allow_html=True,
)
