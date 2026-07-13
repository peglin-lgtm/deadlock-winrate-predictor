import json
from pathlib import Path

import requests
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

url = "https://api.deadlock-api.com/v1/matches/recently-fetched"
pl_url = "https://api.deadlock-api.com/v1/players/hero-stats"
# Change 30 to the number of days of player history you want to collect.
month_ago_timestamp = int(time.time()) - 30 * 24 * 60 * 60

response = requests.get(url)
matches = response.json()

all_match_ids = set()

for i, match in enumerate(matches):

    # Change 30 to the number of recent seed matches you want to process.
    if i >= 30:
        break

    teams = {
        0: [],
        1: []
    }

    match_id = match["match_id"]

    url = f"https://api.deadlock-api.com/v1/matches/{match_id}/metadata"

    try:
        response = requests.get(url, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Match {match_id} skipped: request error")
        print(e)
        continue

    print("status:", response.status_code)

    if response.status_code != 200:
        print(f"Match {match_id} skipped: status = {response.status_code}")
        print(response.text[:200])
        time.sleep(0.2)
        continue

    try:
        match_data = response.json()
    except:
        print(f"Match {match_id} skipped: response is not JSON")
        print(response.text[:200])
        continue
    for player in match_data["match_info"]["players"]:

        params = {
                "account_ids": player["account_id"],
                "min_unix_timestamp": month_ago_timestamp,
                "game_mode": "normal"
            }

        response = requests.get(pl_url, params=params)
        player_stats = response.json()

        for hero_stats in player_stats:
            all_match_ids.update(hero_stats.get("matches", []))

    print(len(all_match_ids))

with open(DATA_DIR / "collected_match_ids.json", "w", encoding="utf-8") as file:
    json.dump(sorted(all_match_ids), file, ensure_ascii=False, indent=2)
