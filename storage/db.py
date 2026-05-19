"""Camada de persistência em SQLite.

Schema (v2):
- players(name PK, uid, rank, total_matches, wins, losses, fetched_at)
- matches(match_id, player_name) PK — partidas normalizadas com MR, MVP/SVP,
  modo de jogo, disconnect, placar por round, season, etc.

Há auto-migração: se detectamos schema antigo (sem coluna score_change),
dropamos e recriamos a tabela matches. Como toda partida pode ser re-puxada
da API, perda de dados local é aceitável.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    name TEXT PRIMARY KEY,
    uid INTEGER,
    rank TEXT,
    total_matches INTEGER,
    wins INTEGER,
    losses INTEGER,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    player_uid INTEGER,
    played_at TEXT NOT NULL,
    duration_min INTEGER,
    duration_sec REAL,
    map TEXT,
    map_id INTEGER,
    hero TEXT,
    hero_id INTEGER,
    role TEXT,
    won INTEGER,
    kills INTEGER,
    deaths INTEGER,
    assists INTEGER,
    damage INTEGER,
    healing INTEGER,
    damage_taken INTEGER,
    score_change REAL,
    is_mvp INTEGER,
    is_svp INTEGER,
    disconnected INTEGER,
    play_mode_id INTEGER,
    game_mode_id INTEGER,
    winner_side INTEGER,
    camp INTEGER,
    score_self INTEGER,
    score_enemy INTEGER,
    season TEXT,
    new_score REAL,
    new_level INTEGER,
    PRIMARY KEY (match_id, player_name)
);

CREATE INDEX IF NOT EXISTS idx_matches_player_time
    ON matches(player_name, played_at);
"""

REQUIRED_MATCH_COLUMNS = {
    "match_id", "player_name", "player_uid", "played_at",
    "duration_min", "duration_sec", "map", "map_id", "hero", "hero_id", "role",
    "won", "kills", "deaths", "assists", "damage", "healing", "damage_taken",
    "score_change", "is_mvp", "is_svp", "disconnected",
    "play_mode_id", "game_mode_id", "winner_side", "camp",
    "score_self", "score_enemy", "season", "new_score", "new_level",
}


@contextmanager
def connect(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _matches_schema_outdated(conn: sqlite3.Connection) -> bool:
    cur = conn.execute("PRAGMA table_info(matches)")
    cols = {row[1] for row in cur.fetchall()}
    if not cols:
        return False  # nem existe, nada pra migrar
    return not REQUIRED_MATCH_COLUMNS.issubset(cols)


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        if _matches_schema_outdated(conn):
            conn.execute("DROP TABLE IF EXISTS matches")
        conn.executescript(SCHEMA)


def upsert_player_data(data: dict[str, Any], db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    player = data["player"]
    matches = data.get("matches", [])
    meta = data.get("meta", {}) or {}
    now = datetime.now().isoformat()

    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO players(name, uid, rank, total_matches, wins, losses, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                uid=excluded.uid,
                rank=excluded.rank,
                total_matches=excluded.total_matches,
                wins=excluded.wins,
                losses=excluded.losses,
                fetched_at=excluded.fetched_at
            """,
            (
                player["name"],
                meta.get("uid"),
                player.get("rank"),
                player.get("total_matches"),
                player.get("wins"),
                player.get("losses"),
                now,
            ),
        )

        for m in matches:
            conn.execute(
                """
                INSERT INTO matches(
                    match_id, player_name, player_uid, played_at,
                    duration_min, duration_sec, map, map_id, hero, hero_id, role,
                    won, kills, deaths, assists, damage, healing, damage_taken,
                    score_change, is_mvp, is_svp, disconnected,
                    play_mode_id, game_mode_id, winner_side, camp,
                    score_self, score_enemy, season, new_score, new_level
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(match_id, player_name) DO UPDATE SET
                    player_uid=excluded.player_uid,
                    played_at=excluded.played_at,
                    duration_min=excluded.duration_min,
                    duration_sec=excluded.duration_sec,
                    map=excluded.map,
                    map_id=excluded.map_id,
                    hero=excluded.hero,
                    hero_id=excluded.hero_id,
                    role=excluded.role,
                    won=excluded.won,
                    kills=excluded.kills,
                    deaths=excluded.deaths,
                    assists=excluded.assists,
                    damage=excluded.damage,
                    healing=excluded.healing,
                    damage_taken=excluded.damage_taken,
                    score_change=excluded.score_change,
                    is_mvp=excluded.is_mvp,
                    is_svp=excluded.is_svp,
                    disconnected=excluded.disconnected,
                    play_mode_id=excluded.play_mode_id,
                    game_mode_id=excluded.game_mode_id,
                    winner_side=excluded.winner_side,
                    camp=excluded.camp,
                    score_self=excluded.score_self,
                    score_enemy=excluded.score_enemy,
                    season=excluded.season,
                    new_score=excluded.new_score,
                    new_level=excluded.new_level
                """,
                (
                    m["match_id"],
                    player["name"],
                    m.get("player_uid"),
                    m["played_at"],
                    m.get("duration_min"),
                    m.get("duration_sec"),
                    m.get("map"),
                    m.get("map_id"),
                    m.get("hero"),
                    m.get("hero_id"),
                    m.get("role"),
                    int(m.get("won", False)),
                    m.get("kills"),
                    m.get("deaths"),
                    m.get("assists"),
                    m.get("damage"),
                    m.get("healing"),
                    m.get("damage_taken"),
                    m.get("score_change"),
                    int(m.get("is_mvp", False)),
                    int(m.get("is_svp", False)),
                    int(m.get("disconnected", False)),
                    m.get("play_mode_id"),
                    m.get("game_mode_id"),
                    m.get("winner_side"),
                    m.get("camp"),
                    m.get("score_self"),
                    m.get("score_enemy"),
                    m.get("season"),
                    m.get("new_score"),
                    m.get("new_level"),
                ),
            )


def load_matches(player_name: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    with connect(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM matches WHERE player_name = ? ORDER BY played_at ASC",
            conn,
            params=(player_name,),
            parse_dates=["played_at"],
        )
    if not df.empty:
        for col in ["won", "is_mvp", "is_svp", "disconnected"]:
            if col in df.columns:
                df[col] = df[col].astype(bool)
    return df


def load_player(player_name: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM players WHERE name = ?", (player_name,)
        ).fetchone()
    return dict(row) if row else None
