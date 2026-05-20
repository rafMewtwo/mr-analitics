"""One-shot fetcher genérico: puxa TUDO da MarvelRivalsAPI sobre um jogador.

Salva os payloads crus em data/{slug}/ como JSON. Depois disso o dashboard
opera 100% offline carregando esses arquivos — sem queimar API calls.

Endpoints puxados (por jogador):
- /find-player/{nick}
- /player/{nick} (profile)
- /player/{nick}/update (tenta forçar refresh; ignora 429)
- /api/v2/player/{nick}/match-history (paginado, até MAX_MATCHES)
- /match/{match_uid} pra CADA partida (detalhe completo, 12 jogadores)
- /heroes (catálogo)
- /maps (catálogo paginado)
- /heroes/hero/{id} + /stats + /leaderboard pra cada herói jogado
- /game-versions, /balances, /patch-notes (contexto da meta)

Uso:
    python fetch_player.py haechanie
    python fetch_player.py "marinão" --slug marinao
    python fetch_player.py haechanie --skip-match-details   # mais rápido
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import requests

# Windows console encoding fix
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import API_BASE_URL_V1, API_BASE_URL_V2, API_KEY

HEADERS = {"x-api-key": API_KEY, "Accept": "application/json"}


def slugify(name: str) -> str:
    """marinão -> marinao. Remove acentos, espaços, caracteres especiais."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return slug or "player"


class PlayerFetcher:
    def __init__(self, nick: str, slug: str | None = None) -> None:
        self.nick = nick
        self.slug = slug or slugify(nick)
        self.data_dir = Path(__file__).parent / "data" / self.slug
        self.match_details_dir = self.data_dir / "match_details"
        self.hero_stats_dir = self.data_dir / "hero_stats"
        self.hero_info_dir = self.data_dir / "hero_info"
        self.hero_leaderboard_dir = self.data_dir / "hero_leaderboard"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.match_details_dir, self.hero_stats_dir,
                  self.hero_info_dir, self.hero_leaderboard_dir):
            d.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def save_json(path: Path, payload) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def get(url: str, params: dict | None = None, retries: int = 2):
        for attempt in range(retries + 1):
            try:
                r = requests.get(url, headers=HEADERS, params=params or {}, timeout=25)
                if r.status_code == 429:
                    print(f"  ! 429 rate limit em {url} (tentativa {attempt+1})")
                    time.sleep(2 + attempt * 2)
                    continue
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.json()
            except requests.RequestException as e:
                if attempt == retries:
                    print(f"  ! erro {url}: {e}")
                    return None
                time.sleep(1)
        return None

    def fetch_player_basics(self) -> dict:
        print("[*] find-player + profile + tentando trigger update")
        found = self.get(f"{API_BASE_URL_V1}/find-player/{self.nick}")
        self.save_json(self.data_dir / "find_player.json", found)

        update_resp = self.get(f"{API_BASE_URL_V1}/player/{self.nick}/update")
        self.save_json(self.data_dir / "update_request.json", update_resp)

        profile = self.get(f"{API_BASE_URL_V1}/player/{self.nick}")
        self.save_json(self.data_dir / "profile.json", profile)
        return profile or {}

    def fetch_match_history(self, max_matches: int = 200) -> list[dict]:
        """Mescla v2 (paginado) + v1 (até 20, sem paginação) por match_uid.

        Descoberta: pra alguns jogadores o v2 retorna bem menos que o v1
        (ex: marinão tinha 5 no v2 e 20 no v1). Pegamos a UNIÃO dos dois pra
        maximizar cobertura. Histórico além disso depende do scrape assíncrono
        da API (/update) terminar — fora do nosso controle.
        """
        by_uid: dict[str, dict] = {}

        # --- acumula o que já temos salvo localmente (re-fetches durante live
        #     só ADICIONAM partidas, nunca perdem as antigas) ---
        existing_path = self.data_dir / "match_history.json"
        if existing_path.exists():
            try:
                for m in json.loads(existing_path.read_text(encoding="utf-8")):
                    uid = str(m.get("match_uid") or "")
                    if uid:
                        by_uid[uid] = m
                print(f"[*] acumulando {len(by_uid)} partidas ja salvas localmente")
            except (json.JSONDecodeError, OSError):
                pass

        # --- v2 paginado ---
        print(f"[*] match-history v2 (paginado, ate {max_matches})")
        page = 1
        while len(by_uid) < max_matches:
            data = self.get(
                f"{API_BASE_URL_V2}/player/{self.nick}/match-history",
                params={"page": page, "limit": 40},
            )
            if not data:
                break
            matches = data.get("match_history", []) if isinstance(data, dict) else []
            if not matches:
                break
            for m in matches:
                uid = str(m.get("match_uid") or "")
                if uid:
                    by_uid.setdefault(uid, m)
            pagination = (data or {}).get("pagination") or {}
            print(f"  v2 pag {page}: +{len(matches)} (unico {len(by_uid)})")
            if not pagination.get("has_more"):
                break
            page += 1

        # --- v1 (não pagina; retorna ~20) ---
        print("[*] match-history v1 (merge)")
        before = len(by_uid)
        data = self.get(
            f"{API_BASE_URL_V1}/player/{self.nick}/match-history",
            params={"page": 1, "limit": 40},
        )
        matches = data.get("match_history", []) if isinstance(data, dict) else (data or [])
        for m in matches:
            uid = str(m.get("match_uid") or "")
            if uid:
                by_uid.setdefault(uid, m)
        print(f"  v1: +{len(by_uid) - before} novos (total unico {len(by_uid)})")

        # Ordena por timestamp desc (mais recentes primeiro) e corta no teto
        collected = sorted(
            by_uid.values(),
            key=lambda m: int(m.get("match_time_stamp") or 0),
            reverse=True,
        )[:max_matches]
        self.save_json(self.data_dir / "match_history.json", collected)
        return collected

    def fetch_match_details(self, matches: list[dict]) -> None:
        print(f"[*] /match/{{uid}} pra {len(matches)} partidas (uma por vez)")
        for i, m in enumerate(matches, 1):
            uid = str(m.get("match_uid") or "")
            if not uid:
                continue
            out_path = self.match_details_dir / f"{uid}.json"
            if out_path.exists():
                continue
            data = self.get(f"{API_BASE_URL_V1}/match/{uid}")
            if data:
                self.save_json(out_path, data)
                print(f"  [{i}/{len(matches)}] {uid} OK")
            else:
                print(f"  [{i}/{len(matches)}] {uid} sem retorno")
            time.sleep(0.3)

    def fetch_catalogs(self) -> None:
        print("[*] catalogos: heroes + maps")
        heroes = self.get(f"{API_BASE_URL_V1}/heroes")
        self.save_json(self.data_dir / "heroes_catalog.json", heroes)

        all_maps: list[dict] = []
        for page in range(1, 11):
            data = self.get(f"{API_BASE_URL_V1}/maps", params={"page": page, "limit": 100})
            if not data:
                break
            page_maps = data.get("maps", []) if isinstance(data, dict) else []
            if not page_maps:
                break
            all_maps.extend(page_maps)
        self.save_json(self.data_dir / "maps_catalog.json", all_maps)

    def fetch_hero_extras(self, matches: list[dict]) -> None:
        hero_ids: set[int] = set()
        for m in matches:
            hp = (m.get("match_player") or {}).get("player_hero") or {}
            hid = hp.get("hero_id")
            if hid is not None:
                try:
                    hero_ids.add(int(hid))
                except (TypeError, ValueError):
                    pass

        print(f"[*] hero info + stats + leaderboard pra {len(hero_ids)} herois jogados")
        for hid in sorted(hero_ids):
            info = self.get(f"{API_BASE_URL_V1}/heroes/hero/{hid}")
            if info:
                self.save_json(self.hero_info_dir / f"{hid}.json", info)

            stats = self.get(f"{API_BASE_URL_V1}/heroes/hero/{hid}/stats")
            if stats:
                self.save_json(self.hero_stats_dir / f"{hid}.json", stats)

            lb = self.get(f"{API_BASE_URL_V1}/heroes/leaderboard/{hid}", params={"platform": "pc"})
            if lb:
                self.save_json(self.hero_leaderboard_dir / f"{hid}.json", lb)
            time.sleep(0.2)

    def fetch_meta_context(self) -> None:
        print("[*] contexto meta: game-versions, balances, patch-notes")
        for endpoint, fname in [
            ("/game-versions", "game_versions.json"),
            ("/balances", "balances.json"),
            ("/patch-notes", "patch_notes.json"),
        ]:
            data = self.get(f"{API_BASE_URL_V1}{endpoint}")
            if data:
                self.save_json(self.data_dir / fname, data)

    def run(self, max_matches: int = 200, skip_match_details: bool = False) -> int:
        self.ensure_dirs()
        started = datetime.now()
        print(f"=== Fetcher '{self.nick}' (slug={self.slug}) iniciado {started.isoformat(timespec='seconds')} ===")

        profile = self.fetch_player_basics()
        if not profile:
            print(f"ERRO: jogador '{self.nick}' nao encontrado ou perfil vazio.")
            return 2

        matches = self.fetch_match_history(max_matches=max_matches)
        self.fetch_catalogs()
        self.fetch_hero_extras(matches)
        self.fetch_meta_context()

        if not skip_match_details:
            self.fetch_match_details(matches)
        else:
            print("(pulando /match/{uid})")

        elapsed = (datetime.now() - started).total_seconds()
        self.save_json(self.data_dir / "_meta.json", {
            "nick": self.nick,
            "slug": self.slug,
            "fetched_at": started.isoformat(),
            "elapsed_sec": elapsed,
            "matches_collected": len(matches),
            "match_details_skipped": skip_match_details,
        })
        print(f"=== Concluido em {elapsed:.1f}s — {len(matches)} partidas ===")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch all MarvelRivalsAPI data for a player.")
    parser.add_argument("nick", help="Nick do jogador na API (ex: haechanie, marinão)")
    parser.add_argument("--slug", default=None, help="Nome da pasta em data/ (default: slug do nick)")
    parser.add_argument("--skip-match-details", action="store_true")
    parser.add_argument("--max-matches", type=int, default=200)
    args = parser.parse_args()

    if not API_KEY:
        print("ERRO: MARVEL_RIVALS_API_KEY nao definida em .env")
        return 1

    fetcher = PlayerFetcher(args.nick, slug=args.slug)
    return fetcher.run(max_matches=args.max_matches, skip_match_details=args.skip_match_details)


if __name__ == "__main__":
    sys.exit(main())
