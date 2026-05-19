"""Cliente da MarvelRivalsAPI com fallback para mock local.

Em modo real, normaliza o payload cru da API para o formato interno usado
pelo storage e pelas análises:

{
  "player": {"name", "rank", "total_matches", "wins", "losses"},
  "matches": [{
      "match_id", "played_at" (ISO), "duration_min", "map",
      "hero", "role", "won", "kills", "deaths", "assists",
      "damage", "healing", "damage_taken"
  }, ...]
}

A API do tier free só retorna ~11 partidas por chamada e não tem paginação,
então a estratégia é acumular no SQLite local a cada refresh.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from typing import Any

import requests

from config import API_BASE_URL_V1, API_BASE_URL_V2, API_KEY, MAX_MATCHES, MOCK_DIR

# Fallback pra heróis que a API /heroes ainda não cataloga (seasons recentes).
# Mapeia hero_id (string) -> {name, role}.
HEROES_FALLBACK = {
    "1052": {"name": "Gambit", "role": "Duelist"},
    "1053": {"name": "Mr. Fantastic", "role": "Duelist"},
    "1054": {"name": "Invisible Woman", "role": "Strategist"},
    "1055": {"name": "The Thing", "role": "Vanguard"},
    "1056": {"name": "Human Torch", "role": "Duelist"},
    "1057": {"name": "Emma Frost", "role": "Vanguard"},
    "1058": {"name": "Ultron", "role": "Strategist"},
    "1059": {"name": "Phoenix", "role": "Duelist"},
    "1060": {"name": "Blade", "role": "Duelist"},
    "1061": {"name": "Angela", "role": "Duelist"},
    "1062": {"name": "Daredevil", "role": "Duelist"},
    "1063": {"name": "Elsa Bloodstone", "role": "Duelist"},
    "1064": {"name": "White Fox", "role": "Strategist"},
    "1065": {"name": "Beast", "role": "Vanguard"},
    "1066": {"name": "Wonder Man", "role": "Duelist"},
    # Mapeamento por nome (case-insensitive) caso hero_id não case
}

HEROES_BY_NAME_FALLBACK = {
    "white fox": {"role": "Strategist"},
    "elsa bloodstone": {"role": "Duelist"},
    "gambit": {"role": "Duelist"},
    "mr. fantastic": {"role": "Duelist"},
    "the thing": {"role": "Vanguard"},
    "emma frost": {"role": "Vanguard"},
    "ultron": {"role": "Strategist"},
    "phoenix": {"role": "Duelist"},
    "blade": {"role": "Duelist"},
    "angela": {"role": "Duelist"},
    "daredevil": {"role": "Duelist"},
    "beast": {"role": "Vanguard"},
    "wonder man": {"role": "Duelist"},
}

MAPS_FALLBACK: dict[int, str] = {
    1418: "Klyntar",
    1421: "Warped Battlefield",
}


class MarvelRivalsClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else API_KEY
        self.base_url_v1 = API_BASE_URL_V1
        self.base_url_v2 = API_BASE_URL_V2
        self.use_mock = not bool(self.api_key)

    # ----- HTTP helpers -----

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key, "Accept": "application/json"}

    def _get(self, path: str, *, v2: bool = False, **params: Any) -> Any:
        base = self.base_url_v2 if v2 else self.base_url_v1
        url = f"{base}{path}"
        resp = requests.get(url, headers=self._headers(), params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()

    # ----- Reference data (cached) -----

    @lru_cache(maxsize=1)
    def heroes_index(self) -> dict[str, dict[str, str]]:
        """Mapa hero_id (str) -> {name, role}. Aplica fallback pra heróis novos."""
        if self.use_mock:
            return dict(HEROES_FALLBACK)
        heroes = self._get("/heroes") or []
        index = {
            str(h["id"]): {"name": h["name"].title(), "role": h.get("role", "Unknown")}
            for h in heroes
        }
        # Mescla fallback (sem sobrescrever entradas da API)
        for hid, info in HEROES_FALLBACK.items():
            index.setdefault(hid, info)
        return index

    @lru_cache(maxsize=1)
    def maps_index(self) -> dict[int, str]:
        """Mapa map_id (int) -> nome. Pagina até esgotar."""
        if self.use_mock:
            return dict(MAPS_FALLBACK)
        out: dict[int, str] = {}
        for page in range(1, 11):
            try:
                data = self._get("/maps", page=page, limit=100) or {}
            except requests.HTTPError:
                break
            maps = data.get("maps", data) if isinstance(data, dict) else data
            if not maps:
                break
            for m in maps:
                try:
                    out[int(m["id"])] = m.get("name") or m.get("full_name", f"Map {m['id']}")
                except (KeyError, TypeError):
                    continue
        for mid, mname in MAPS_FALLBACK.items():
            out.setdefault(mid, mname)
        return out

    # ----- Player -----

    def find_player(self, username: str) -> dict | None:
        """Resolve nick -> uid. Retorna None se não existir."""
        if self.use_mock:
            return {"name": username, "uid": "mock"}
        try:
            return self._get(f"/find-player/{username}")
        except requests.HTTPError:
            return None

    def trigger_update(self, username: str, timeout: int = 60) -> dict:
        """Pede pra API atualizar os dados do jogador.

        A API limita 1 update a cada 30 min por jogador (429).
        Retorna {status: 'ok'|'rate_limited'|'error', message: str}.
        """
        if self.use_mock:
            return {"status": "ok", "message": "mock"}
        try:
            url = f"{self.base_url_v1}/player/{username}/update"
            r = requests.get(url, headers=self._headers(), timeout=timeout)
            if r.status_code == 429:
                msg = (r.json() or {}).get("message", "rate limited")
                return {"status": "rate_limited", "message": msg}
            r.raise_for_status()
            return {"status": "ok", "message": "update requested"}
        except requests.RequestException as e:
            return {"status": "error", "message": str(e)[:200]}

    def fetch_all_matches(self, username: str, max_matches: int = MAX_MATCHES) -> list[dict]:
        """Pagina /api/v2/player/{nick}/match-history até esgotar ou bater no teto.

        A v2 retorna até 40 partidas por página. Iteramos páginas enquanto houver
        has_more=true e não atingimos max_matches.
        """
        collected: list[dict] = []
        page = 1
        limit = 40
        while len(collected) < max_matches:
            data = self._get(
                f"/player/{username}/match-history",
                v2=True,
                page=page,
                limit=limit,
            )
            matches = data.get("match_history", []) if isinstance(data, dict) else []
            if not matches:
                break
            collected.extend(matches)

            pagination = (data or {}).get("pagination") or {}
            if not pagination.get("has_more"):
                break
            page += 1

        return collected[:max_matches]

    def get_player(self, username: str, refresh: bool = False) -> dict[str, Any]:
        if self.use_mock:
            return self._load_mock(username)

        update_info: dict | None = None
        if refresh:
            update_info = self.trigger_update(username)

        profile = self._get(f"/player/{username}")
        matches_raw = self.fetch_all_matches(username)

        heroes = self.heroes_index()
        maps = self.maps_index()

        player_block = profile.get("player", {})
        overall = profile.get("overall_stats", {}) or {}
        ranked = overall.get("ranked", {}) or {}

        player = {
            "name": profile.get("name") or username,
            "rank": (player_block.get("rank") or {}).get("rank"),
            "total_matches": overall.get("total_matches", 0),
            "wins": overall.get("total_wins", 0),
            "losses": overall.get("total_matches", 0) - overall.get("total_wins", 0),
        }

        matches = [self._normalize_match(m, heroes, maps) for m in matches_raw]
        matches = [m for m in matches if m is not None]
        meta = {
            "uid": profile.get("uid"),
            "is_private": profile.get("isPrivate", False),
            "last_history_update": (profile.get("updates") or {}).get("last_history_update"),
            "update_request": update_info,
        }
        return {"player": player, "matches": matches, "meta": meta}

    # ----- Normalization -----

    @staticmethod
    def _normalize_match(
        raw: dict, heroes: dict[str, dict[str, str]], maps: dict[int, str]
    ) -> dict | None:
        try:
            mp = raw.get("match_player") or {}
            hero_block = mp.get("player_hero") or {}
            hero_id_raw = hero_block.get("hero_id")
            hero_id_str = str(hero_id_raw) if hero_id_raw is not None else ""
            hero_info = heroes.get(hero_id_str, {})
            hero_name = (
                hero_info.get("name")
                or (hero_block.get("hero_name") or "Unknown").title()
            )
            role = hero_info.get("role", "Unknown")
            # Fallback final: lookup por nome lowercase
            if role == "Unknown":
                name_lookup = HEROES_BY_NAME_FALLBACK.get(hero_name.lower())
                if name_lookup:
                    role = name_lookup["role"]

            map_id_raw = raw.get("match_map_id") or raw.get("map_id")
            try:
                map_id = int(map_id_raw) if map_id_raw is not None else None
            except (TypeError, ValueError):
                map_id = None
            map_name = maps.get(map_id, f"Map {map_id}") if map_id else "Unknown"

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

            # score_info: {"0": rounds_side0, "1": rounds_side1}
            score_info = raw.get("score_info") or {}
            camp = mp.get("camp")  # 0 ou 1 (qual lado o jogador estava)
            try:
                score_self = int(score_info.get(str(camp), 0)) if camp is not None else None
                other_side = "1" if str(camp) == "0" else "0"
                score_enemy = int(score_info.get(other_side, 0)) if camp is not None else None
            except (TypeError, ValueError):
                score_self = score_enemy = None

            # score_change e novo rank score
            ms_info = mp.get("score_info") or {}
            score_change = ms_info.get("add_score")
            new_score = ms_info.get("new_score")
            new_level = ms_info.get("new_level")

            return {
                "match_id": str(raw.get("match_uid")),
                "played_at": played_at,
                "duration_min": duration_min,
                "duration_sec": duration_sec,
                "map": map_name,
                "map_id": map_id,
                "hero": hero_name,
                "hero_id": int(hero_id_raw) if hero_id_raw is not None else None,
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
                "player_uid": int(player_uid) if player_uid is not None else None,
            }
        except (KeyError, TypeError, ValueError):
            return None

    # ----- Hero stats (benchmark global) -----

    @lru_cache(maxsize=64)
    def get_hero_stats(self, hero_id: int) -> dict | None:
        """Métricas agregadas globais de um herói (médias K/D/A, total damage, etc).

        Útil pra benchmark: 'sua média vs média global do herói'.
        """
        if self.use_mock or not hero_id:
            return None
        try:
            return self._get(f"/heroes/hero/{hero_id}/stats")
        except requests.HTTPError:
            return None

    # ----- Mock -----

    def _load_mock(self, username: str) -> dict[str, Any]:
        path = MOCK_DIR / "player_MockPlayer.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Mock não encontrado: {path}. Rode 'python mocks/generate.py'."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        data["player"]["name"] = username
        return data


def get_default_client() -> MarvelRivalsClient:
    return MarvelRivalsClient()
