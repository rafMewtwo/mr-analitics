import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MARVEL_RIVALS_API_KEY", "").strip()
API_BASE_URL_V1 = "https://marvelrivalsapi.com/api/v1"
API_BASE_URL_V2 = "https://marvelrivalsapi.com/api/v2"
# Compatibilidade: clientes antigos que importam API_BASE_URL caem na v1.
API_BASE_URL = API_BASE_URL_V1

DB_PATH = Path(os.getenv("DB_PATH", "mr_analytics.db"))
MOCK_DIR = Path(__file__).parent / "mocks"

# Máximo de partidas históricas a puxar por refresh (paginando v2).
# Cada página = 40 partidas. 200 = até 5 páginas.
MAX_MATCHES = int(os.getenv("MAX_MATCHES", "200"))

USE_MOCK = not bool(API_KEY)
