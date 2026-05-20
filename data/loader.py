"""Carrega TODOS os JSONs em data/haechanie/ pra estruturas Python prontas pra análise.

Esse módulo substitui o ciclo API->SQLite->DataFrame que o dashboard usava antes.
Agora tudo vem de arquivos locais, baixados uma vez via `python fetch_haechanie.py`.

Expõe:
    load_haechanie() -> HaechanieData

HaechanieData tem:
- profile (dict) — payload cru de /player/haechanie (já tem team_mates, hero_matchups, etc)
- matches_df (DataFrame) — match-history normalizado (mesmo schema do antigo SQLite)
- match_details (dict[match_uid] -> dict) — detalhe completo com 12 players por partida
- heroes_catalog (dict[id] -> {name, role, difficulty, ...})
- maps_catalog (dict[id] -> name)
- hero_stats (dict[id] -> {global stats}) — benchmark global por herói
- hero_info (dict[id] -> {abilities, role, ...})
- hero_leaderboard (dict[id] -> list[top players])
- team_mates_df (DataFrame) — top teammates com WR
- hero_matchups_df (DataFrame) — WR contra cada herói inimigo
- heroes_ranked_df (DataFrame) — stats agregadas por herói jogado em ranked (com accuracy)
- maps_agg_df (DataFrame) — stats agregadas por mapa
- rank (str), level (int), player_uid (int)
- meta_context (dict) — game_versions, balances, patch_notes
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

NICK = "haechanie"  # default histórico
BASE_DIR = Path(__file__).parent


def _read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


@dataclass
class PlayerData:
    profile: dict
    matches_df: pd.DataFrame
    match_details: dict[str, dict]
    heroes_catalog: dict[int, dict]
    maps_catalog: dict[int, str]
    hero_stats: dict[int, dict]
    hero_info: dict[int, dict]
    hero_leaderboard: dict[int, list]
    team_mates_df: pd.DataFrame
    hero_matchups_df: pd.DataFrame
    heroes_ranked_df: pd.DataFrame
    maps_agg_df: pd.DataFrame
    display_name: str = ""
    slug: str = ""
    rank: str = ""
    rank_image: str = ""
    level: int = 0
    player_uid: int = 0
    overall_ranked: dict = field(default_factory=dict)
    meta_context: dict = field(default_factory=dict)
    fetched_at: str = ""


# Alias de compatibilidade: módulos de análise importam HaechanieData como type hint.
HaechanieData = PlayerData


# Fallback pra heróis recentes não listados em /heroes (seasons novas).
HEROES_EXTRA: dict[int, dict] = {
    1059: {"name": "Elsa Bloodstone", "role": "Duelist", "difficulty": "3"},
    1060: {"name": "White Fox", "role": "Strategist", "difficulty": "3"},
    1061: {"name": "Angela", "role": "Duelist", "difficulty": "3"},
    1062: {"name": "Daredevil", "role": "Duelist", "difficulty": "3"},
    1063: {"name": "Blade", "role": "Duelist", "difficulty": "3"},
    1064: {"name": "Gambit", "role": "Duelist", "difficulty": "3"},
    1065: {"name": "Beast", "role": "Vanguard", "difficulty": "3"},
    1066: {"name": "Wonder Man", "role": "Duelist", "difficulty": "3"},
}


def _build_heroes_index(catalog: list[dict], hero_info_dir: dict[int, dict] | None = None) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for h in catalog or []:
        try:
            hid = int(h["id"])
        except (KeyError, TypeError, ValueError):
            continue
        out[hid] = {
            "name": (h.get("name") or "").title(),
            "role": h.get("role") or "Unknown",
            "difficulty": h.get("difficulty"),
            "attack_type": h.get("attack_type"),
            "real_name": h.get("real_name"),
        }
    # Enriquecer com hero_info/ (heróis efetivamente jogados — pega role correto)
    for hid, info in (hero_info_dir or {}).items():
        existing = out.get(hid, {})
        out[hid] = {
            "name": (info.get("name") or existing.get("name") or "").title(),
            "role": info.get("role") or existing.get("role") or "Unknown",
            "difficulty": info.get("difficulty") or existing.get("difficulty"),
            "attack_type": info.get("attack_type") or existing.get("attack_type"),
            "real_name": info.get("real_name") or existing.get("real_name"),
        }
    # Por fim, fallback hardcoded pra IDs que ainda não temos
    for hid, info in HEROES_EXTRA.items():
        out.setdefault(hid, info)
    return out


def _build_maps_index(catalog: list[dict]) -> dict[int, str]:
    out: dict[int, str] = {}
    for m in catalog or []:
        try:
            mid = int(m["id"])
            out[mid] = m.get("name") or m.get("full_name") or f"Map {mid}"
        except (KeyError, TypeError, ValueError):
            continue
    # Fallbacks pros 2 IDs que a API às vezes não retorna
    out.setdefault(1418, "Klyntar")
    out.setdefault(1421, "Warped Battlefield")
    return out


def _normalize_match(raw: dict, heroes_idx: dict[int, dict], maps_idx: dict[int, str]) -> dict | None:
    """Mesma normalização que o api/client.py fazia — produz dict com schema do SQLite antigo."""
    try:
        mp = raw.get("match_player") or {}
        hero_block = mp.get("player_hero") or {}
        hero_id_raw = hero_block.get("hero_id")
        try:
            hero_id = int(hero_id_raw) if hero_id_raw is not None else None
        except (TypeError, ValueError):
            hero_id = None

        hero_info = heroes_idx.get(hero_id or -1, {})
        hero_name = hero_info.get("name") or (hero_block.get("hero_name") or "Unknown").title()
        role = hero_info.get("role", "Unknown")

        map_id_raw = raw.get("match_map_id") or raw.get("map_id")
        try:
            map_id = int(map_id_raw) if map_id_raw is not None else None
        except (TypeError, ValueError):
            map_id = None
        map_name = maps_idx.get(map_id, f"Map {map_id}") if map_id else "Unknown"

        ts = raw.get("match_time_stamp")
        played_at = datetime.fromtimestamp(int(ts)).isoformat() if ts else None

        duration_sec = float(raw.get("match_play_duration") or raw.get("duration") or 0)
        duration_min = int(round(duration_sec / 60))

        is_win = bool(((mp.get("is_win") or {}).get("is_win", False)))
        player_uid = mp.get("player_uid")
        mvp_uid = raw.get("mvp_uid")
        svp_uid = raw.get("svp_uid")
        is_mvp = bool(player_uid and mvp_uid and int(player_uid) == int(mvp_uid))
        is_svp = bool(player_uid and svp_uid and int(player_uid) == int(svp_uid))

        score_info = raw.get("score_info") or {}
        camp = mp.get("camp")
        try:
            score_self = int(score_info.get(str(camp), 0)) if camp is not None else None
            other_side = "1" if str(camp) == "0" else "0"
            score_enemy = int(score_info.get(other_side, 0)) if camp is not None else None
        except (TypeError, ValueError):
            score_self = score_enemy = None

        ms_info = mp.get("score_info") or {}
        score_change = ms_info.get("add_score")
        new_score = ms_info.get("new_score")
        new_level = ms_info.get("new_level")

        return {
            "match_id": str(raw.get("match_uid")),
            "player_name": NICK,
            "player_uid": int(player_uid) if player_uid is not None else None,
            "played_at": played_at,
            "duration_min": duration_min,
            "duration_sec": duration_sec,
            "map": map_name,
            "map_id": map_id,
            "hero": hero_name,
            "hero_id": hero_id,
            "role": role,
            "won": is_win,
            "kills": int(hero_block.get("kills") or mp.get("kills") or 0),
            "deaths": int(hero_block.get("deaths") or mp.get("deaths") or 0),
            "assists": int(hero_block.get("assists") or mp.get("assists") or 0),
            "damage": int(hero_block.get("total_hero_damage") or 0),
            "healing": int(hero_block.get("total_hero_heal") or 0),
            "damage_taken": int(hero_block.get("total_damage_taken") or 0),
            "score_change": float(score_change) if score_change is not None else None,
            "is_mvp": is_mvp,
            "is_svp": is_svp,
            "disconnected": bool(mp.get("disconnected", False)),
            "play_mode_id": raw.get("play_mode_id"),
            "game_mode_id": raw.get("game_mode_id"),
            "winner_side": raw.get("match_winner_side"),
            "camp": camp,
            "score_self": score_self,
            "score_enemy": score_enemy,
            "season": raw.get("match_season") or raw.get("season"),
            "new_score": float(new_score) if new_score is not None else None,
            "new_level": int(new_level) if new_level is not None else None,
        }
    except (KeyError, TypeError, ValueError):
        return None


def _load_match_details(data_dir: Path) -> dict[str, dict]:
    """Carrega todos os match_details/*.json e indexa por match_uid."""
    out: dict[str, dict] = {}
    md_dir = data_dir / "match_details"
    if not md_dir.exists():
        return out
    for f in md_dir.glob("*.json"):
        d = _read_json(f)
        if not d:
            continue
        md = d.get("match_details", d)
        uid = md.get("match_uid") or f.stem
        out[str(uid)] = md
    return out


def _load_hero_dir(data_dir: Path, subdir: str) -> dict[int, Any]:
    """Carrega data/{slug}/{subdir}/*.json indexado por int(filename)."""
    out: dict[int, Any] = {}
    d = data_dir / subdir
    if not d.exists():
        return out
    for f in d.glob("*.json"):
        try:
            hid = int(f.stem)
        except ValueError:
            continue
        payload = _read_json(f)
        if payload is not None:
            out[hid] = payload
    return out


def _build_team_mates_df(profile: dict) -> pd.DataFrame:
    rows = []
    for tm in profile.get("team_mates") or []:
        info = tm.get("player_info") or {}
        rows.append({
            "nick": info.get("nick_name"),
            "uid": info.get("player_uid"),
            "icon": info.get("player_icon"),
            "matches": int(tm.get("matches") or 0),
            "wins": int(tm.get("wins") or 0),
            "win_rate": float(tm.get("win_rate") or 0) / 100.0,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["losses"] = df["matches"] - df["wins"]
    return df


def _resolve_hero(hid, heroes_idx: dict[int, dict]) -> dict:
    """Acha info do hero tentando id direto e variantes (costume/transformation)."""
    if hid is None:
        return {}
    try:
        hid_int = int(hid)
    except (TypeError, ValueError):
        return {}
    if hid_int in heroes_idx:
        return heroes_idx[hid_int]
    # IDs como 10573, 10571 são variantes de 1057 (base id = id // 10)
    if hid_int >= 10000:
        base = hid_int // 10
        if base in heroes_idx:
            return heroes_idx[base]
    return {}


def _build_hero_matchups_df(profile: dict, heroes_idx: dict[int, dict]) -> pd.DataFrame:
    rows = []
    for h in profile.get("hero_matchups") or []:
        hid = h.get("hero_id")
        info = _resolve_hero(hid, heroes_idx)
        api_name = (h.get("hero_name") or "").strip()
        api_class = (h.get("hero_class") or "").strip()
        # API às vezes retorna literal "Unknown" — trata como vazio
        if api_name.lower() == "unknown":
            api_name = ""
        if api_class.lower() == "unknown":
            api_class = ""
        rows.append({
            "hero_id": hid,
            "hero": (api_name or info.get("name") or "Unknown").title(),
            "role": api_class or info.get("role") or "Unknown",
            "matches": int(h.get("matches") or 0),
            "wins": int(h.get("wins") or 0),
            "win_rate": float(h.get("win_rate") or 0) / 100.0,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["losses"] = df["matches"] - df["wins"]
    return df


def _build_heroes_ranked_df(profile: dict, heroes_idx: dict[int, dict]) -> pd.DataFrame:
    rows = []
    for h in profile.get("heroes_ranked") or []:
        hid = h.get("hero_id")
        info = heroes_idx.get(int(hid) if hid else -1, {})
        matches = int(h.get("matches") or 0)
        wins = int(h.get("wins") or 0)
        play_time_sec = float(h.get("play_time") or 0)
        ma = h.get("main_attack") or {}
        ma_hits = int(ma.get("hits") or 0)
        ma_total = int(ma.get("total") or 0)
        rows.append({
            "hero_id": hid,
            "hero": (h.get("hero_name") or info.get("name") or "Unknown").title(),
            "role": info.get("role") or "Unknown",
            "difficulty": info.get("difficulty"),
            "matches": matches,
            "wins": wins,
            "win_rate": wins / matches if matches else 0.0,
            "mvp": int(h.get("mvp") or 0),
            "svp": int(h.get("svp") or 0),
            "kills": int(h.get("kills") or 0),
            "deaths": int(h.get("deaths") or 0),
            "assists": int(h.get("assists") or 0),
            "play_time_sec": play_time_sec,
            "play_time_min": play_time_sec / 60.0,
            "damage": float(h.get("damage") or 0),
            "heal": float(h.get("heal") or 0),
            "damage_taken": float(h.get("damage_taken") or 0),
            "accuracy": (ma_hits / ma_total) if ma_total else None,
            "shots_total": ma_total,
            "shots_hit": ma_hits,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["kda"] = (df["kills"] + df["assists"]) / df["deaths"].replace(0, 1)
        df["damage_per_min"] = df["damage"] / df["play_time_min"].replace(0, 1)
        df["heal_per_min"] = df["heal"] / df["play_time_min"].replace(0, 1)
    return df


def _build_maps_agg_df(profile: dict, maps_idx: dict[int, str]) -> pd.DataFrame:
    rows = []
    for m in profile.get("maps") or []:
        mid = m.get("map_id")
        matches = int(m.get("matches") or 0)
        wins = int(m.get("wins") or 0)
        rows.append({
            "map_id": mid,
            "map": maps_idx.get(int(mid) if mid else -1, f"Map {mid}"),
            "matches": matches,
            "wins": wins,
            "win_rate": wins / matches if matches else 0.0,
            "kills": int(m.get("kills") or 0),
            "deaths": int(m.get("deaths") or 0),
            "assists": int(m.get("assists") or 0),
            "play_time_sec": float(m.get("play_time") or 0),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["kda"] = (df["kills"] + df["assists"]) / df["deaths"].replace(0, 1)
    return df


@lru_cache(maxsize=8)
def load_player(slug: str) -> PlayerData:
    """Carrega todos os dados de data/{slug}/ numa PlayerData. Cacheado por slug."""
    data_dir = BASE_DIR / slug
    profile = _read_json(data_dir / "profile.json", {}) or {}
    matches_raw = _read_json(data_dir / "match_history.json", []) or []
    heroes_catalog_list = _read_json(data_dir / "heroes_catalog.json", []) or []
    maps_catalog_list = _read_json(data_dir / "maps_catalog.json", []) or []

    hero_info_loaded = _load_hero_dir(data_dir, "hero_info")
    heroes_idx = _build_heroes_index(heroes_catalog_list, hero_info_loaded)
    maps_idx = _build_maps_index(maps_catalog_list)

    matches_rows = [_normalize_match(m, heroes_idx, maps_idx) for m in matches_raw]
    matches_rows = [m for m in matches_rows if m is not None]
    matches_df = pd.DataFrame(matches_rows)
    if not matches_df.empty:
        matches_df["played_at"] = pd.to_datetime(matches_df["played_at"])
        matches_df = matches_df.sort_values("played_at").reset_index(drop=True)
        for col in ["won", "is_mvp", "is_svp", "disconnected"]:
            if col in matches_df.columns:
                matches_df[col] = matches_df[col].astype(bool)

    player_block = profile.get("player") or {}
    overall = profile.get("overall_stats") or {}
    ranked = overall.get("ranked") or {}
    rank_block = player_block.get("rank") or {}

    meta = {
        "game_versions": _read_json(data_dir / "game_versions.json"),
        "balances": _read_json(data_dir / "balances.json"),
        "patch_notes": _read_json(data_dir / "patch_notes.json"),
    }
    fetch_meta = _read_json(data_dir / "_meta.json", {}) or {}
    display_name = profile.get("name") or fetch_meta.get("nick") or slug

    return PlayerData(
        profile=profile,
        matches_df=matches_df,
        match_details=_load_match_details(data_dir),
        heroes_catalog=heroes_idx,
        maps_catalog=maps_idx,
        hero_stats=_load_hero_dir(data_dir, "hero_stats"),
        hero_info=hero_info_loaded,
        hero_leaderboard=_load_hero_dir(data_dir, "hero_leaderboard"),
        team_mates_df=_build_team_mates_df(profile),
        hero_matchups_df=_build_hero_matchups_df(profile, heroes_idx),
        heroes_ranked_df=_build_heroes_ranked_df(profile, heroes_idx),
        maps_agg_df=_build_maps_agg_df(profile, maps_idx),
        display_name=display_name,
        slug=slug,
        rank=rank_block.get("rank") or "",
        rank_image=rank_block.get("image") or "",
        level=int(player_block.get("level") or 0),
        player_uid=int(profile.get("uid") or 0),
        overall_ranked=ranked,
        meta_context=meta,
        fetched_at=fetch_meta.get("fetched_at", ""),
    )


def load_haechanie() -> PlayerData:
    """Compat: carrega haechanie. Prefira load_player(slug)."""
    return load_player("haechanie")


__all__ = ["load_player", "load_haechanie", "PlayerData", "HaechanieData", "NICK"]
