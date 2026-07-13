import json
from pathlib import Path

import requests
import pandas as pd
import time
import os
import asyncio
import aiohttp

from aiolimiter import AsyncLimiter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
pl_url = "https://api.deadlock-api.com/v1/players/hero-stats"


async def get_team_players_stats(
    players: list[dict],
    match_start_time: int,
) -> list[dict]:

    # Keep request throughput within the API rate limit.
    limiter = AsyncLimiter(
        max_rate=5,
        time_period=1,
    )

    timeout = aiohttp.ClientTimeout(total=30)

    connector = aiohttp.TCPConnector(
        limit=5
    )

    async def get_one_player_stats(
        session: aiohttp.ClientSession,
        player: dict,
    ) -> dict:

        account_id = player["account_id"]
        hero_id = player["hero_id"]

        params = {
            "account_ids": account_id,
            "hero_ids": hero_id,
            "max_unix_timestamp": match_start_time - 1,
            "game_mode": "normal",
        }

        for attempt in range(3):
            try:
                async with limiter:
                    async with session.get(
                        pl_url,
                        params=params,
                    ) as response:

                        if response.status == 200:
                            stats = await response.json()

                            return {
                                "account_id": account_id,
                                "hero_id": hero_id,
                                "team": player["team"],
                                "stats": stats,
                            }

                        text = await response.text()

                        if response.status == 429:
                            wait_time = float(
                                response.headers.get(
                                    "Retry-After",
                                    10,
                                )
                            )

                            print(
                                f"Player {account_id}: "
                                f"429, waiting {wait_time} sec."
                            )

                        elif response.status >= 500:
                            wait_time = 2 ** attempt

                            print(
                                f"Player {account_id}: "
                                f"server error "
                                f"{response.status}"
                            )

                        else:
                            print(
                                f"Player {account_id}: "
                                f"status={response.status}"
                            )
                            print(text[:300])

                            return {
                                "account_id": account_id,
                                "hero_id": hero_id,
                                "team": player["team"],
                                "stats": None,
                            }

                await asyncio.sleep(wait_time)

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
            ) as error:

                wait_time = 2 ** attempt

                print(
                    f"Player {account_id}: {error}. "
                    f"Retrying in {wait_time} sec."
                )

                await asyncio.sleep(wait_time)

        return {
            "account_id": account_id,
            "hero_id": hero_id,
            "team": player["team"],
            "stats": None,
        }

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
    ) as session:

        tasks = [
            asyncio.create_task(
                get_one_player_stats(
                    session,
                    player,
                )
            )
            for player in players
        ]

        results = await asyncio.gather(*tasks)

    return results
 


match_count = 0
rows = [] 
count = 0
filename = DATA_DIR / "matches_metadata.jsonl"

with open(filename, "r", encoding="utf-8") as file:
    for line in file:
        match_data = json.loads(line)



        count += 1
        team_features = {}
        teams = {
            0: [],
            1: []
        }
        stats_by_team = {
            0: [],
            1: [],
        }



        has_abandon = any(
            player.get("abandon_match_time_s") is not None
            for player in match_data["match_info"]["players"]
            )
        if has_abandon:
            print("Match skipped: a player abandoned the match")
            continue
        if match_data["match_info"].get("game_mode") != 1:
            game_mode = match_data["match_info"].get("game_mode")
            print(f"Match skipped: game_mode = {game_mode}")
            continue
        
    

        for player in match_data["match_info"]["players"]:
            team = player["team"]

            player_info = {
                "account_id": player["account_id"],
                "hero_id": player["hero_id"],
                "team": player["team"]
            }

            teams[team].append(player_info)
        if any(len(players) != 6 for players in teams.values()):
            print("One of the teams does not have 6 players; skipping the match")
            continue



        all_players = [
            player
            for players in teams.values()
            for player in players
        ]

        all_players_stats = asyncio.run(
            get_team_players_stats(
                players=all_players,
                match_start_time=match_data["match_info"]["start_time"],
            )
        )
        
        for player_result in all_players_stats:
            stats_by_team[player_result["team"]].append(player_result)




        win_team = match_data["match_info"]["winning_team"]

        for team_id, players in teams.items():
            players_stats = stats_by_team[team_id]


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
            

            for player_result in players_stats:
                player_stats = player_result["stats"]
                
                if not player_stats:
                    first_time_on_hero_count += 1
                    low_hero_exp_count += 1

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
                        "account_ids": player_result["account_id"],
                        "max_unix_timestamp": match_data["match_info"]["start_time"] - 1,
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

            """print("-----------------------")
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
            print("-----------------------")"""
                

    
        row = {
            "target": win_team,

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

        df.to_csv(
            DATA_DIR / "deadlock_dataset.csv",
            mode="a",              
            index=False,
            header=not (DATA_DIR / "deadlock_dataset.csv").exists()
        )

        match_count += 1
        print(f"Match #{match_count} written to CSV")

        if match_count > 0 and match_count % 250 == 0:
            print("Pausing for 30 seconds after 250 matches")
            time.sleep(60)
        
        
        
print("*****************************************************************************")
print("All done")
print("*****************************************************************************")
