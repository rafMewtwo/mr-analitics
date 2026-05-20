import time
import requests
from config import API_KEY

H = {"x-api-key": API_KEY, "Accept": "application/json"}
url = "https://marvelrivalsapi.com/api/v1/player/marinão/update"

for i in range(12):
    r = requests.get(url, headers=H, timeout=30)
    print(f"try {i+1}: {r.status_code} {r.text[:120]}", flush=True)
    if r.status_code == 200:
        print("UPDATE TRIGGERED", flush=True)
        break
    time.sleep(30)
