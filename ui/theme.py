"""Injeta o tema visual estilo Marvel Rivals e provê helpers de render."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent.parent / "assets"

# Paleta Plotly tematizada (sincronizada com styles.css)
PLOTLY_TEMPLATE = {
    "layout": {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(15, 19, 32, 0.4)",
        "font": {"family": "Inter, sans-serif", "color": "#e8eef9", "size": 12},
        "title": {"text": "", "font": {"family": "Rajdhani, sans-serif", "size": 18, "color": "#e8eef9"}},
        "colorway": ["#00d4ff", "#ff2d5f", "#f9d11c", "#00ff9d", "#b56bff", "#ff8c42"],
        "margin": {"l": 50, "r": 30, "t": 30, "b": 40},
        "height": 320,
        "xaxis": {
            "gridcolor": "rgba(255, 255, 255, 0.05)",
            "linecolor": "rgba(255, 255, 255, 0.1)",
            "zerolinecolor": "rgba(255, 255, 255, 0.1)",
        },
        "yaxis": {
            "gridcolor": "rgba(255, 255, 255, 0.05)",
            "linecolor": "rgba(255, 255, 255, 0.1)",
            "zerolinecolor": "rgba(255, 255, 255, 0.1)",
        },
        "legend": {
            "bgcolor": "rgba(15, 19, 32, 0.8)",
            "bordercolor": "rgba(255, 45, 95, 0.15)",
            "borderwidth": 1,
        },
    }
}


def apply_theme() -> None:
    """Injeta CSS no app. Chame uma vez no início de cada page."""
    css_file = ASSETS / "styles.css"
    if css_file.exists():
        css = css_file.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_hero(title: str = "Marvel Rivals", sub: str = "Performance Analytics",
                badge: str = "Realtime Game Data", compact: bool = False) -> None:
    """Renderiza o header customizado.

    compact=False (default): hero grande, ideal pra landing.
    compact=True: barra fina, ideal pra quando há análise carregada.
    """
    if compact:
        st.markdown(
            f"""
            <div class="mr-hero-compact">
              <span class="mr-hero-compact-title">{title}</span>
              <span class="mr-hero-compact-sub">{sub}</span>
              <span class="mr-hero-badge mr-hero-badge-inline">{badge}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""
        <div class="mr-hero">
          <div class="mr-hero-badge">{badge}</div>
          <h1 class="mr-hero-title">{title}</h1>
          <div class="mr-hero-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def style_plotly(fig):
    """Aplica o template visual ao Plotly figure."""
    fig.update_layout(**PLOTLY_TEMPLATE["layout"])
    return fig
