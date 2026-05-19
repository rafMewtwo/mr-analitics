"""Tradução centralizada de colunas/métricas técnicas para PT-BR amigável."""

from __future__ import annotations

import pandas as pd

COLUMN_LABELS: dict[str, str] = {
    # ---- Identificação ----
    "hero": "Herói",
    "role": "Role",
    "map": "Mapa",
    "played_at": "Quando",

    # ---- Contagens ----
    "matches": "Partidas",
    "wins": "Vitórias",
    "losses": "Derrotas",

    # ---- KDA ----
    "kills": "Kills",
    "deaths": "Deaths",
    "assists": "Assists",
    "kda": "KDA",
    "won": "Venceu?",

    # ---- MVP/SVP ----
    "is_mvp": "MVP?",
    "is_svp": "SVP?",
    "mvp_count": "MVPs",
    "svp_count": "SVPs",
    "mvp_rate": "Taxa MVP",
    "podium_rate": "Taxa Pódio",

    # ---- MR / Rank Score ----
    "win_rate": "Win Rate",
    "avg_mr": "MR médio",
    "total_mr": "MR total",
    "score_change": "MR ganho/perdido",
    "new_score": "Rank Score",

    # ---- Eficiência por minuto ----
    "dmg_min": "Dano/min",
    "heal_min": "Cura/min",
    "taken_min": "Dano tomado/min",
    "damage_per_min": "Dano/min",
    "healing_per_min": "Cura/min",
    "taken_per_min": "Dano tomado/min",
    "kills_per_min": "Kills/min",

    # ---- Benchmark vs global ----
    "your_kda": "Seu KDA",
    "global_kda": "KDA global",
    "kda_delta_pct": "Δ KDA (%)",
    "your_dmg_min": "Seu Dano/min",
    "global_dmg_min": "Dano/min global",
    "dmg_delta_pct": "Δ Dano (%)",
    "your_heal_min": "Sua Cura/min",
    "global_heal_min": "Cura/min global",
    "heal_delta_pct": "Δ Cura (%)",
    "your_taken_min": "Seu Dano tomado/min",
    "global_taken_min": "Dano tomado/min global",
    "your_win_rate": "Seu WR",
    "global_win_rate": "WR global",

    # ---- Flags / Meta ----
    "enough_data": "Amostra ≥ mín",
    "disconnected": "DC?",
    "duration_min": "Duração (min)",
    "damage": "Dano",
    "healing": "Cura",
    "damage_taken": "Dano tomado",

    # ---- Temporal ----
    "hour": "Hora",
    "weekday": "Dia da semana",
    "weekday_name": "Dia",
    "rolling_wr": "Win Rate (média móvel 10)",
}


def rename_df(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia colunas usando o dicionário PT-BR (não modifica original)."""
    if df.empty:
        return df
    cols = {c: COLUMN_LABELS.get(c, c) for c in df.columns}
    return df.rename(columns=cols)


def label(col: str) -> str:
    """Retorna o label PT-BR de uma coluna (ou ela mesma se não traduzida)."""
    return COLUMN_LABELS.get(col, col)


def plotly_labels(*cols: str) -> dict[str, str]:
    """Retorna dict {col: label_pt} para passar em labels= do Plotly."""
    return {c: COLUMN_LABELS.get(c, c) for c in cols}
