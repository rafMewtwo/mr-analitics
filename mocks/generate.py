"""Gera um arquivo mock de jogador com padrões plausíveis para as análises detectarem.

Padrões embutidos de propósito:
- Win rate cai depois das 23h (fadiga)
- Win rate cai após 2 derrotas seguidas (tilt)
- Um herói "âncora" (alto win rate) e um "afundador" (baixo win rate)
- Performance pior em 1 mapa específico
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

HEROES = [
    ("Punisher", "Duelist"),
    ("Hela", "Duelist"),
    ("Spider-Man", "Duelist"),
    ("Iron Man", "Duelist"),
    ("Magneto", "Vanguard"),
    ("Hulk", "Vanguard"),
    ("Doctor Strange", "Vanguard"),
    ("Luna Snow", "Strategist"),
    ("Mantis", "Strategist"),
    ("Rocket Raccoon", "Strategist"),
]

MAPS = ["Yggsgard", "Tokyo 2099", "Hell's Heaven", "Hydra Base", "Klyntar"]
WEAK_MAP = "Tokyo 2099"

ANCHOR_HERO = "Punisher"
SINKER_HERO = "Spider-Man"


def _gen_match(idx: int, base_time: datetime, prev_results: list[bool]) -> dict:
    hero, role = random.choice(HEROES)
    map_name = random.choice(MAPS)

    # Base win rate
    p_win = 0.55

    # Tilt: depois de 2 derrotas seguidas
    if len(prev_results) >= 2 and not prev_results[-1] and not prev_results[-2]:
        p_win -= 0.20

    # Fadiga: depois das 23h
    if base_time.hour >= 23 or base_time.hour < 3:
        p_win -= 0.15

    # Hero modifiers
    if hero == ANCHOR_HERO:
        p_win += 0.18
    elif hero == SINKER_HERO:
        p_win -= 0.22

    # Map modifier
    if map_name == WEAK_MAP:
        p_win -= 0.12

    p_win = max(0.05, min(0.95, p_win))
    won = random.random() < p_win

    # KDA influenciada por vitória e por padrões
    if won:
        kills = random.randint(12, 28)
        deaths = random.randint(2, 7)
        assists = random.randint(5, 15)
    else:
        kills = random.randint(4, 14)
        deaths = random.randint(6, 14)
        assists = random.randint(2, 9)

    if hero == SINKER_HERO:
        deaths += random.randint(2, 5)

    damage = kills * random.randint(800, 1400) + random.randint(2000, 6000)
    healing = random.randint(8000, 22000) if role == "Strategist" else random.randint(0, 1500)
    damage_taken = random.randint(10000, 30000) if role == "Vanguard" else random.randint(3000, 12000)

    duration_min = random.randint(8, 18)

    return {
        "match_id": f"m_{idx:05d}",
        "played_at": base_time.isoformat(),
        "duration_min": duration_min,
        "map": map_name,
        "hero": hero,
        "role": role,
        "won": won,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "damage": damage,
        "healing": healing,
        "damage_taken": damage_taken,
        "rank": "Diamond III",
    }


def generate(player_name: str, n_matches: int = 80) -> dict:
    matches: list[dict] = []
    results: list[bool] = []
    # Sessões: distribui partidas em ~20 dias, com sessões de 3-6 partidas
    cursor = datetime.now() - timedelta(days=20)
    i = 0
    while i < n_matches:
        # Inicia uma sessão num horário aleatório
        cursor = cursor + timedelta(days=random.choice([0, 1, 1, 2]))
        # Horário de início da sessão (mais provável noite)
        start_hour = random.choices(
            [14, 17, 19, 20, 21, 22, 23, 0, 1],
            weights=[1, 2, 3, 4, 5, 5, 4, 2, 1],
        )[0]
        session_start = cursor.replace(hour=start_hour % 24, minute=random.randint(0, 59))
        if start_hour >= 24:
            session_start = session_start + timedelta(days=1)

        session_len = random.randint(3, 7)
        for _ in range(session_len):
            if i >= n_matches:
                break
            match = _gen_match(i, session_start, results)
            matches.append(match)
            results.append(match["won"])
            session_start = session_start + timedelta(minutes=match["duration_min"] + random.randint(2, 6))
            i += 1
        cursor = session_start

    wins = sum(1 for m in matches if m["won"])
    return {
        "player": {
            "name": player_name,
            "rank": "Diamond III",
            "total_matches": len(matches),
            "wins": wins,
            "losses": len(matches) - wins,
        },
        "matches": matches,
    }


def main() -> None:
    out_dir = Path(__file__).parent
    data = generate("MockPlayer", n_matches=80)
    out_path = out_dir / "player_MockPlayer.json"
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Gerado: {out_path} ({len(data['matches'])} partidas)")


if __name__ == "__main__":
    main()
