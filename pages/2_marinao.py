"""Dashboard de marinão — rota /marinao.

Carrega data/marinao/*.json e delega a renderização pro módulo compartilhado.
Atualizar dados: python fetch_player.py "marinão" --slug marinao
"""

from __future__ import annotations

import streamlit as st

from data import load_player
from ui.dashboard import render
from ui.theme import apply_theme

st.set_page_config(
    page_title="marinão · MR Analytics",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()


@st.cache_resource(show_spinner=False)
def _data():
    return load_player("marinao")


render(_data())
