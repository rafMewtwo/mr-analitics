"""One-shot fetcher: puxa TUDO que conseguimos da MarvelRivalsAPI sobre haechanie.

Salva os payloads crus em data/haechanie/ como JSON. Depois disso o dashboard
opera 100% offline carregando esses arquivos — sem queimar API calls.

Endpoints puxados:
- /find-player/haechanie
- /player/haechanie (profile)
- /player/haechanie/update (tenta forçar refresh; ignora 429)
- /api/v2/player/haechanie/match-history (paginado, até MAX_MATCHES)
- /match/{match_uid} pra CADA partida (detalhe completo, 12 jogadores)
- /heroes (catálogo)
- /maps (catálogo paginado)
- /heroes/hero/{id} pra cada herói jogado
- /heroes/hero/{id}/stats pra cada herói jogado (benchmark global)
- /heroes/leaderboard/{hero} pra top heróis jogados
- /game-versions, /balances, /patch-notes (contexto da meta)

Uso:
    python fetch_haechanie.py
    python fetch_haechanie.py --skip-match-details  # mais rápido, sem /match/{uid}
"""

from __future__ import annotations

import argparse
import json
import sys
import time
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

NICK = "haechanie"
DATA_DIR = Path(__file__).parent / "data" / NICK
MATCH_DETAILS_DIR = DATA_DIR / "match_details"
HERO_STATS_DIR = DATA_DIR / "hero_stats"
HERO_INFO_DIR = DATA_DIR / "hero_info"
HERO_LEADERBOARD_DIR = DATA_DIR / "hero_leaderboard"

HEADERS = {"x-api-key": API_KEY, "Accept": "application/json"}


def ensure_dirs() -> None:
    for d in (DATA_DIR, MATCH_DETAILS_DIR, HERO_STATS_DIR, HERO_INFO_DIR, HERO_LEADERBOARD_DIR):
        d.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get(url: str, params: dict | None = None, retries: int = 2) -> dict | list | None:
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


def fetch_player_basics() -> dict:
    print("[*] find-player + profile + tentando trigger update")
    found = get(f"{API_BASE_URL_V1}/find-player/{NICK}")
    save_json(DATA_DIR / "find_player.json", found)

    update_resp = get(f"{API_BASE_URL_V1}/player/{NICK}/update")
    save_json(DATA_DIR / "update_request.json", update_resp)

    profile = get(f"{API_BASE_URL_V1}/player/{NICK}")
    save_json(DATA_DIR / "profile.json", profile)
    return profile or {}


def fetch_match_history(max_matches: int = 200) -> list[dict]:
    print(f"[*] match-history v2 (ate {max_matches} partidas)")
    collected: list[dict] = []
    page = 1
    while len(collected) < max_matches:
        data = get(
            f"{API_BASE_URL_V2}/player/{NICK}/match-history",
            params={"page": page, "limit": 40},
        )
        if not data:
            break
        matches = data.get("match_history", []) if isinstance(data, dict) else []
        if not matches:
            break
        collected.extend(matches)
        pagination = (data or {}).get("pagination") or {}
        print(f"  pág {page}: +{len(matches)} (total {len(collected)})")
        if not pagination.get("has_more"):
            break
        page += 1
    collected = collected[:max_matches]
    save_json(DATA_DIR / "match_history.json", collected)
    return collected


def fetch_match_details(matches: list[dict]) -> None:
    print(f"[*] /match/{{uid}} pra {len(matches)} partidas (uma por vez)")
    for i, m in enumerate(matches, 1):
        uid = str(m.get("match_uid") or "")
        if not uid:
            continue
        out_path = MATCH_DETAILS_DIR / f"{uid}.json"
        if out_path.exists():
            continue  # já temos
        data = get(f"{API_BASE_URL_V1}/match/{uid}")
        if data:
            save_json(out_path, data)
            print(f"  [{i}/{len(matches)}] {uid} OK")
        else:
            print(f"  [{i}/{len(matches)}] {uid} sem retorno")
        time.sleep(0.3)  # respeitar rate limit


def fetch_catalogs() -> dict:
    print("[*] catalogos: heroes + maps")
    heroes = get(f"{API_BASE_URL_V1}/heroes")
    save_json(DATA_DIR / "heroes_catalog.json", heroes)

    all_maps: list[dict] = []
    for page in range(1, 11):
        data = get(f"{API_BASE_URL_V1}/maps", params={"page": page, "limit": 100})
        if not data:
            break
        page_maps = data.get("maps", []) if isinstance(data, dict) else []
        if not page_maps:
            break
        all_maps.extend(page_maps)
    save_json(DATA_DIR / "maps_catalog.json", all_maps)
    return {"heroes": heroes, "maps": all_maps}


def fetch_hero_extras(matches: list[dict]) -> None:
    """Pra cada herói jogado, puxa info detalhada + stats globais + leaderboard."""
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
        info = get(f"{API_BASE_URL_V1}/heroes/hero/{hid}")
        if info:
            save_json(HERO_INFO_DIR / f"{hid}.json", info)

        stats = get(f"{API_BASE_URL_V1}/heroes/hero/{hid}/stats")
        if stats:
            save_json(HERO_STATS_DIR / f"{hid}.json", stats)

        lb = get(f"{API_BASE_URL_V1}/heroes/leaderboard/{hid}", params={"platform": "pc"})
        if lb:
            save_json(HERO_LEADERBOARD_DIR / f"{hid}.json", lb)
        time.sleep(0.2)


def fetch_meta_context() -> None:
    print("[*] contexto meta: game-versions, balances, patch-notes")
    for endpoint, fname in [
        ("/game-versions", "game_versions.json"),
        ("/balances", "balances.json"),
        ("/patch-notes", "patch_notes.json"),
    ]:
        data = get(f"{API_BASE_URL_V1}{endpoint}")
        if data:
            save_json(DATA_DIR / fname, data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-match-details", action="store_true")
    parser.add_argument("--max-matches", type=int, default=200)
    args = parser.parse_args()

    if not API_KEY:
        print("ERRO: MARVEL_RIVALS_API_KEY não definida em .env")
        return 1

    ensure_dirs()
    started = datetime.now()
    print(f"=== Fetcher haechanie iniciado {started.isoformat(timespec='seconds')} ===")

    fetch_player_basics()
    matches = fetch_match_history(max_matches=args.max_matches)
    fetch_catalogs()
    fetch_hero_extras(matches)
    fetch_meta_context()

    if not args.skip_match_details:
        fetch_match_details(matches)
    else:
        print("(pulando /match/{uid} — use sem --skip-match-details pra dados completos)")

    elapsed = (datetime.now() - started).total_seconds()
    save_json(DATA_DIR / "_meta.json", {
        "nick": NICK,
        "fetched_at": started.isoformat(),
        "elapsed_sec": elapsed,
        "matches_collected": len(matches),
        "match_details_skipped": args.skip_match_details,
    })
    print(f"=== Concluído em {elapsed:.1f}s — {len(matches)} partidas ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
