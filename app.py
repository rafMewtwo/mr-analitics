"""Landing page — Marvel Rivals Analytics.

Visual hero + CTA pro dashboard. Sem referência a nenhum jogador específico:
quem o app analisa fica encapsulado dentro da página /haechanie.
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

# Esconde menu de páginas do sidebar (queremos navegação via botões custom)
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
        <div class="landing-badge">● LIVE ANALYTICS</div>
        <h1 class="landing-title">MARVEL<br/>RIVALS</h1>
        <div class="landing-sub">Performance Analytics</div>
        <div class="landing-pitch">
          Dashboard data-driven com plano de climb quantificado, análise de counters,
          sinergia com teammates, precisão vs média global, e insights que você não
          enxerga jogando — mas a câmera dos dados sim.
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("ENTRAR NO DASHBOARD →", type="primary", use_container_width=True):
        st.switch_page("pages/1_haechanie.py")

st.markdown(
    """
    <div class="landing-foot">
      <div class="landing-foot-cols">
        <div>
          <div class="landing-foot-h">🎯 Plano de Climb</div>
          <div class="landing-foot-p">Quantas partidas até a próxima divisão, qual herói focar, qual cortar.</div>
        </div>
        <div>
          <div class="landing-foot-h">⚔️ Counters</div>
          <div class="landing-foot-p">Heróis inimigos contra os quais você apanha e os que são presa fácil.</div>
        </div>
        <div>
          <div class="landing-foot-h">🎯 Precisão</div>
          <div class="landing-foot-p">Hit rate por herói comparado com a média global de todos os jogadores.</div>
        </div>
        <div>
          <div class="landing-foot-h">🤝 Sinergia</div>
          <div class="landing-foot-p">Quais teammates te carregam, qualidade do time aliado vs inimigo.</div>
        </div>
      </div>
      <div class="landing-foot-meta">Powered by MarvelRivalsAPI.com · Snapshot atualizado periodicamente</div>
    </div>
    """,
    unsafe_allow_html=True,
)
