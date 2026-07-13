import json
from pathlib import Path

import requests
import pandas as pd
import joblib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "saved_models"


def get_match_players(match_id: int) -> dict[int, list[dict]]:
    url = (
        f"http://localhost:3000/v1/matches/{match_id}/live/demo/events"
        "?subscribed_entities=player_controller"
    )

    players_by_steam_id = {}

    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        print(f"SSE connected. Match: {match_id}")
        print("Waiting for 6 players from teams 2 and 3...")

        event_name = None

        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue

            if raw_line.startswith("event:"):
                event_name = raw_line.removeprefix("event:").strip()
                continue

            if not raw_line.startswith("data:"):
                continue

            if event_name not in {
                "player_controller_entity_create",
                "player_controller_entity_update",
            }:
                continue

            payload = raw_line.removeprefix("data:").strip()
            if not payload:
                continue

            try:
                data = json.loads(payload)
                steam_id = int(data.get("steam_id", 0))
                hero_id = int(data.get("hero_id", 0))
                team_id = int(data.get("team", 0))
                steam_name = str(data.get("steam_name") or "")
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

            if steam_id == 0 or hero_id == 0 or team_id not in (2, 3):
                continue

            is_new_player = steam_id not in players_by_steam_id

            players_by_steam_id[steam_id] = {
                "steam_id": steam_id,
                "steam_name": steam_name,
                "hero_id": hero_id,
                "team_id": team_id,
            }

            source_teams = {
                2: [p for p in players_by_steam_id.values() if p["team_id"] == 2],
                3: [p for p in players_by_steam_id.values() if p["team_id"] == 3],
            }

            if is_new_player:
                display_name = steam_name or "no nickname"
                print(
                    f"Player added: {display_name} | "
                    f"steam_id={steam_id} | hero_id={hero_id} | team={team_id}"
                )
                print(
                    f"Lineups: team 2 — {len(source_teams[2])}/6, "
                    f"team 3 — {len(source_teams[3])}/6"
                )

            if all(len(source_teams[team_id]) == 6 for team_id in (2, 3)):
                teams = {0: [], 1: []}

                for source_team_id, model_team_id in ((2, 0), (3, 1)):
                    for player in source_teams[source_team_id]:
                        player_steam_id = player["steam_id"]
                        account_id = (
                            player_steam_id - 76561197960265728
                            if player_steam_id >= 76561197960265728
                            else player_steam_id
                        )
                        teams[model_team_id].append({
                            "account_id": account_id,
                            "steam_name": player["steam_name"],
                            "hero_id": player["hero_id"],
                        })

                print("Lineups ready: received 6 players from team 2 and 6 players from team 3.")
                print("Closing SSE connection.")
                return teams

            continue

    return {
        0: [],
        1: [],
    }


pl_url = "https://api.deadlock-api.com/v1/players/hero-stats"

team_features = {}


# Replace this with the ID of the Deadlock match you want to predict.
match_id = 93571231


teams = get_match_players(match_id=match_id)

if any(len(players) != 6 for players in teams.values()):
    raise ValueError("Не удалось получить по 6 игроков в каждой команде")

logistic_model = joblib.load(
    MODELS_DIR / "deadlock_logistic_regression.joblib"
)

random_forest_model = joblib.load(
    MODELS_DIR / "deadlock_random_forest.joblib"
)


for team_id, players in teams.items():

    first_time_on_hero_count = 0
    low_hero_exp_count = 0

    total_team_matches_played = 0
    total_team_winrate = 0
    total_team_kills_per_min = 0
    total_team_deaths_per_min = 0
    total_team_assists_per_min = 0
    total_team_networth_per_min = 0
    total_team_damage_per_min = 0
    total_team_damage_taken_per_min = 0
    total_team_obj_damage_per_min = 0
    total_team_crit_shot_rate = 0
    total_team_accuracy = 0
    
    print(f"\nFinal model team {team_id}:")
    for player in players:

        params = {
                    "account_ids": player["account_id"],
                    "hero_ids": player["hero_id"],
                    "game_mode": "normal"
                }

        response = requests.get(pl_url, params=params)
        player_stats= response.json()

        
        if not player_stats:
            first_time_on_hero_count += 1
            low_hero_exp_count += 1
            print(f"{player["steam_name"]} is playing this hero for the first time")


            total_matches_all_heroes = 0
            total_wins_all_heroes = 0
            total_kills_per_min_all_heroes = 0
            total_deaths_per_min_all_heroes = 0
            total_assists_per_min_all_heroes = 0
            total_networth_per_min_all_heroes = 0
            total_damage_per_min_all_heroes = 0
            total_damage_taken_per_min_all_heroes = 0
            total_obj_damage_per_min_all_heroes = 0
            total_crit_shot_rate_all_heroes = 0
            total_accuracy_all_heroes = 0
            
            params = {
                "account_ids": player["account_id"],
                "game_mode": "normal"
            }

            response = requests.get(pl_url, params=params)
            player_stats_all_heroes = response.json()
            heroes_count = len(player_stats_all_heroes)

            for hero_stats in player_stats_all_heroes:
                total_matches_all_heroes += hero_stats["matches_played"]
                total_wins_all_heroes += hero_stats["wins"]
                total_kills_per_min_all_heroes += hero_stats["kills_per_min"]
                total_deaths_per_min_all_heroes += hero_stats["deaths_per_min"]
                total_assists_per_min_all_heroes += hero_stats["assists_per_min"]
                total_networth_per_min_all_heroes += hero_stats["networth_per_min"]
                total_damage_per_min_all_heroes += hero_stats["damage_per_min"]
                total_damage_taken_per_min_all_heroes += hero_stats["damage_taken_per_min"]
                total_obj_damage_per_min_all_heroes += hero_stats["obj_damage_per_min"]
                total_crit_shot_rate_all_heroes += hero_stats["crit_shot_rate"]
                total_accuracy_all_heroes += hero_stats["accuracy"]

            if heroes_count > 0:
                avg_matches_per_hero = total_matches_all_heroes / heroes_count
                avg_winrate_per_hero = (total_wins_all_heroes / total_matches_all_heroes)
                avg_kills_per_min_per_hero = total_kills_per_min_all_heroes / heroes_count 
                avg_deaths_per_min_per_hero = total_deaths_per_min_all_heroes  / heroes_count
                avg_assists_per_min_per_hero = total_assists_per_min_all_heroes  / heroes_count
                avg_networth_per_min_per_hero = total_networth_per_min_all_heroes  / heroes_count
                avg_damage_per_min_per_hero = total_damage_per_min_all_heroes  / heroes_count
                avg_damage_taken_per_min_per_hero = total_damage_taken_per_min_all_heroes  / heroes_count
                avg_obj_damage_per_min_per_hero = total_obj_damage_per_min_all_heroes  / heroes_count
                avg_crit_shot_rate_per_hero = total_crit_shot_rate_all_heroes  / heroes_count
                avg_accuracy_per_hero = total_accuracy_all_heroes  / heroes_count

            else:
                avg_matches_per_hero = 0
                avg_winrate_per_hero = 0
                avg_kills_per_min_per_hero = 0
                avg_deaths_per_min_per_hero = 0
                avg_assists_per_min_per_hero = 0
                avg_networth_per_min_per_hero = 0
                avg_damage_per_min_per_hero = 0
                avg_damage_taken_per_min_per_hero = 0
                avg_obj_damage_per_min_per_hero = 0
                avg_crit_shot_rate_per_hero = 0
                avg_accuracy_per_hero = 0

            total_team_matches_played += avg_matches_per_hero
            total_team_winrate += avg_winrate_per_hero
            total_team_kills_per_min += avg_kills_per_min_per_hero
            total_team_deaths_per_min += avg_deaths_per_min_per_hero
            total_team_assists_per_min += avg_assists_per_min_per_hero
            total_team_networth_per_min += avg_networth_per_min_per_hero
            total_team_damage_per_min += avg_damage_per_min_per_hero
            total_team_damage_taken_per_min += avg_damage_taken_per_min_per_hero
            total_team_obj_damage_per_min += avg_obj_damage_per_min_per_hero
            total_team_crit_shot_rate += avg_crit_shot_rate_per_hero
            total_team_accuracy += avg_accuracy_per_hero



        else:
            if player_stats[0]["matches_played"] <= 3:
                low_hero_exp_count += 1
            

            print("====================================")
            print(f"{player["steam_name"]} (team {team_id}) stats on hero")
            print("***")
            
            print(f"{player_stats[0]["matches_played"]} games")
            print(f"{player_stats[0]["kills"]} kills")
            print(f"{player_stats[0]["deaths"]} deaths")
            print(f"{player_stats[0]["wins"]} wins")

            print("====================================")


            total_team_matches_played += (player_stats[0]["matches_played"])
            total_team_winrate += (player_stats[0]["wins"]) / (player_stats[0]["matches_played"])
            total_team_kills_per_min += (player_stats[0]["kills_per_min"])
            total_team_deaths_per_min += (player_stats[0]["deaths_per_min"])
            total_team_assists_per_min += (player_stats[0]["assists_per_min"])
            total_team_networth_per_min += (player_stats[0]["networth_per_min"])
            total_team_damage_per_min += (player_stats[0]["damage_per_min"])
            total_team_damage_taken_per_min += (player_stats[0]["damage_taken_per_min"])
            total_team_obj_damage_per_min += (player_stats[0]["obj_damage_per_min"])
            total_team_crit_shot_rate += (player_stats[0]["crit_shot_rate"])
            total_team_accuracy += (player_stats[0]["accuracy"])
            
    team_features[team_id] = {
        "first_time_on_hero_count": first_time_on_hero_count,
        "low_hero_exp_count": low_hero_exp_count,

        "avg_team_matches_played": total_team_matches_played/6,
        "avg_team_winrate": total_team_winrate/6,
        "avg_team_kills_per_min": total_team_kills_per_min/6,
        "avg_team_deaths_per_min": total_team_deaths_per_min/6,
        "avg_team_assists_per_min": total_team_assists_per_min/6,
        "avg_team_networth_per_min": total_team_networth_per_min/6,
        "avg_team_damage_per_min": total_team_damage_per_min/6,
        "avg_team_damage_taken_per_min": total_team_damage_taken_per_min/6,
        "avg_team_obj_damage_per_min": total_team_obj_damage_per_min/6,
        "avg_team_crit_shot_rate": total_team_crit_shot_rate/6,
        "avg_team_accuracy": total_team_accuracy/6
    }

    print("-----------------------")
    print(f"first-time hero players on team {team_id} = {first_time_on_hero_count}")
    print(f"players with low hero experience on team {team_id} = {low_hero_exp_count}")
    print(f"average matches played by team {team_id} = {total_team_matches_played/6}")
    print(f"average win rate of team {team_id} = {total_team_winrate/6}")
    print(f"average kills per minute of team {team_id} = {total_team_kills_per_min/6}")
    print(f"average deaths per minute of team {team_id} = {total_team_deaths_per_min/6}")
    print(f"average assists per minute of team {team_id} = {total_team_assists_per_min/6}")
    print(f"average net worth per minute of team {team_id} = {total_team_networth_per_min/6}")
    print(f"average damage per minute of team {team_id} = {total_team_damage_per_min/6}")
    print(f"average damage taken per minute of team {team_id} = {total_team_damage_taken_per_min/6}")
    print(f"average objective damage per minute of team {team_id} = {total_team_obj_damage_per_min/6}")
    print(f"average critical hit rate of team {team_id} = {total_team_crit_shot_rate/6}")
    print(f"average accuracy of team {team_id} = {total_team_accuracy/6}")
    print("-----------------------")
        


row = {

    "first_time_on_hero_count_diff": team_features[1]["first_time_on_hero_count"] - team_features[0]["first_time_on_hero_count"],
    "low_hero_exp_count_team_diff": team_features[1]["low_hero_exp_count"] - team_features[0]["low_hero_exp_count"],

    "matches_played_diff": team_features[1]["avg_team_matches_played"] - team_features[0]["avg_team_matches_played"],
    "winrate_diff": team_features[1]["avg_team_winrate"] - team_features[0]["avg_team_winrate"],
    "kills_per_min_diff": team_features[1]["avg_team_kills_per_min"] - team_features[0]["avg_team_kills_per_min"],
    "deaths_per_min_diff": team_features[1]["avg_team_deaths_per_min"] - team_features[0]["avg_team_deaths_per_min"], 
    "assists_per_min_diff": team_features[1]["avg_team_assists_per_min"] - team_features[0]["avg_team_assists_per_min"],
    "networth_per_min_diff": team_features[1]["avg_team_networth_per_min"] - team_features[0]["avg_team_networth_per_min"],
    "damage_per_min_diff": team_features[1]["avg_team_damage_per_min"] - team_features[0]["avg_team_damage_per_min"],
    "damage_taken_per_min_diff": team_features[1]["avg_team_damage_taken_per_min"] - team_features[0]["avg_team_damage_taken_per_min"],
    "obj_damage_per_min_diff": team_features[1]["avg_team_obj_damage_per_min"] - team_features[0]["avg_team_obj_damage_per_min"],
    "crit_shot_rate_diff": team_features[1]["avg_team_crit_shot_rate"] - team_features[0]["avg_team_crit_shot_rate"],
    "accuracy_diff": team_features[1]["avg_team_accuracy"] - team_features[0]["avg_team_accuracy"]
}

df = pd.DataFrame([row])

logistic_prediction = logistic_model.predict(df)[0]
logistic_probabilities = logistic_model.predict_proba(df)[0]

forest_prediction = random_forest_model.predict(df)[0]
forest_probabilities = random_forest_model.predict_proba(df)[0]


print("\nLogistic Regression:")
print(f"Prediction: team {logistic_prediction}")
print(f"Team 0: {logistic_probabilities[0] * 100:.2f}%")
print(f"Team 1: {logistic_probabilities[1] * 100:.2f}%")

print("\nRandom Forest:")
print(f"Prediction: team {forest_prediction}")
print(f"Team 0: {forest_probabilities[0] * 100:.2f}%")
print(f"Team 1: {forest_probabilities[1] * 100:.2f}%")
