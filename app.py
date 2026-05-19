"""Landing page — Marvel Rivals Analytics.

Visual hero + CTA pro dashboard em /haechanie.
"""

from __future__ import annotations

import streamlit as st

from data import load_haechanie
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


@st.cache_resource(show_spinner=False)
def _data():
    try:
        return load_haechanie()
    except Exception:
        return None


data = _data()
quick_stats = ""
if data is not None and not data.matches_df.empty:
    df = data.matches_df
    wr = float(df["won"].mean()) * 100
    quick_stats = (
        f"{data.rank} · {len(df)} partidas · {wr:.0f}% WR · "
        f"level {data.level}"
    )

st.markdown(
    f"""
    <div class="landing-wrap">
      <div class="landing-card">
        <div class="landing-badge">● LIVE ANALYTICS</div>
        <h1 class="landing-title">MARVEL<br/>RIVALS</h1>
        <div class="landing-sub">Performance Analytics · Single Player Edition</div>
        <div class="landing-pitch">
          Dashboard data-driven com plano de climb quantificado, análise de counters,
          sinergia com teammates, precisão vs média global, e insights que você não
          enxerga jogando — mas a câmera dos dados sim.
        </div>
        {f'<div class="landing-stats">{quick_stats}</div>' if quick_stats else ''}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("ANALISAR HAECHANIE →", type="primary", use_container_width=True):
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
