# node pokemon-showdown start --no-security


import asyncio
import importlib
import os
import sys
from typing import Dict, List, Optional, Tuple, cast

import poke_env as pke
from poke_env import AccountConfiguration
from poke_env.battle import Battle
from poke_env.player.player import Player
from tabulate import tabulate

## MARK: GLOBALS

def rank_players_by_victories(results_dict, top_k=10):
    victory_scores = {}

    for player, opponents in results_dict.items():
        victories = [
            1 if (score is not None and score > 0.5) else 0
            for opp, score in opponents.items()
            if opp != player
        ]
        if victories:
            victory_scores[player] = sum(victories) / len(victories)
        else:
            victory_scores[player] = 0.0

    # Sort by descending victory rate
    sorted_players = sorted(victory_scores.items(), key=lambda x: x[1], reverse=True)

    return sorted_players[:top_k]


def gather_players() -> List[Player]:
    player_folders = os.path.join(os.path.dirname(__file__), "players")

    players = []

    replay_dir = os.path.join(os.path.dirname(__file__), "replays")
    if not os.path.exists(replay_dir):
        os.makedirs(replay_dir)

    for module_name in os.listdir(player_folders):
        if module_name.endswith(".py"):
            module_path = f"{player_folders}/{module_name}"

            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)

            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Get the class
            if hasattr(module, "CustomAgent"):
                # Check if the class is a subclass of Player

                player_name = f"{module_name[:-3]}"

                agent_class = getattr(module, "CustomAgent")

                agent_replay_dir = os.path.join(replay_dir, f"{player_name}")
                if not os.path.exists(agent_replay_dir):
                    os.makedirs(agent_replay_dir)

                account_config = AccountConfiguration(player_name, None)
                player = agent_class(
                    account_configuration=account_config,
                    battle_format="gen9ubers",
                )

                player._save_replays = agent_replay_dir

                players.append(player)

    return players


def gather_bots() -> List[Player]:
    bot_folders = os.path.join(os.path.dirname(__file__), "bots")
    bot_teams_folders = os.path.join(bot_folders, "teams")

    generic_bots = []

    bot_teams = {}

    for team_file in os.listdir(bot_teams_folders):
        if team_file.endswith(".txt"):
            with open(
                os.path.join(bot_teams_folders, team_file), "r", encoding="utf-8"
            ) as file:
                bot_teams[team_file[:-4]] = file.read()

    for module_name in os.listdir(bot_folders):
        if module_name.endswith(".py"):
            module_path = f"{bot_folders}/{module_name}"

            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)

            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            for team_name, team in bot_teams.items():
                # Get the class
                if hasattr(module, "CustomAgent"):
                    # Check if the class is a subclass of Player
                    agent_class = getattr(module, "CustomAgent")

                    config_name = f"{module_name[:-3]}-{team_name}"
                    account_config = AccountConfiguration(config_name, None)
                    generic_bots.append(
                        agent_class(
                            team=team,
                            account_configuration=account_config,
                            battle_format="gen9ubers",
                        )
                    )

    return generic_bots


async def cross_evaluate(bots: List[Player], player: Player):
    return await cross_evaluate_manual(bots, player, n_challenges=3)

## MARK: CROSS EVAL MANUAL
async def cross_evaluate_manual(
    bots: List[Player], player: Player, n_challenges: int
):
    battles = cast(Dict[str, Dict[str, Battle]], {})

    for _i, bot in enumerate(bots):
        await player.battle_against(bot, n_battles=n_challenges)
        battles[bot.username] = cast(Dict[str, Battle], player.battles)
        player.reset_battles()
        bot.reset_battles()
    return battles

def evalute_againts_bots(bots: List[Player], player: Player):
    print(f"{len(bots)} are competing in this challenge")

    print("Running Cross Evaluations...")
    cross_evaluation_results = asyncio.run(cross_evaluate(bots, player))
    print("Evaluations Complete")

    # # table = [["-"] + [p.username for p in players]]
    # # for p_1, results in cross_evaluation_results.items():
    # #     table.append([p_1] + [cross_evaluation_results[p_1][p_2] for p_2 in results])

    # # first row is headers
    # headers = table[0]
    # data = table[1:]

    # print(tabulate(data, headers=headers, floatfmt=".2f"))

    # print("Rankings")
    # top_players = rank_players_by_victories(
    #     cross_evaluation_results, top_k=len(cross_evaluation_results)
    # )

    return cross_evaluation_results


def assign_marks(rank: int) -> float:
    modifier = 1.0 if rank > 10 else 0.5

    top_marks = 10.0 if rank < 10 else 5.0

    mod_rank = rank % 10

    marks = top_marks - (mod_rank - 1) * modifier

    return 0.0 if marks < 0 else marks


## MARK: MAIN

def main():
    # bots = [gather_bots()[0]]
    bots = gather_bots()
    players = gather_players()


    for player in players:
        results_file = os.path.join(
            os.path.dirname(__file__), "results", f"hp_{player.username}.txt"
        )
        if not os.path.exists(os.path.dirname(results_file)):
            os.makedirs(os.path.dirname(results_file))

        battles = evalute_againts_bots(bots, player)

        # HP Results: bot_username -> (hp percentage lost, losses)
        hp_results = cast(Dict[str, Tuple[float, int]], {})
        overall_hp_percentage_lost = 0.0
        overall_losses = 0
        for bot_username, battle_list in battles.items():
            total_hp_percentage_lost = 0.0
            num_losses = 0
            for _battle_id, battle in battle_list.items():
                total_hp_percentage_lost += (
                    100.0 * sum(1.0 - battle.team[p].current_hp_fraction for p in battle.team)
                )
                if battle.lost:
                    num_losses += 1
                    overall_losses += 1
            avg_hp_percentage = total_hp_percentage_lost / len(battle_list) if battle_list else 0.0
            overall_hp_percentage_lost += avg_hp_percentage
            hp_results[bot_username] = (avg_hp_percentage, num_losses)

        hp_results["Overall"] = (overall_hp_percentage_lost / len(battles) if battles else 0.0, overall_losses)

        with open(results_file, "w", encoding="utf-8") as file:
            file.write(f"HP Results for player: {player.username}\n")
            print(f"HP Results for player: {player.username}")
            for bot_username, result in hp_results.items():
                hp_percentage, num_losses = result
                file.write(f"Against {bot_username}: {hp_percentage:.2f} (Losses: {num_losses})\n")
                print(f"Against {bot_username}: {hp_percentage:.2f} (Losses: {num_losses})")

if __name__ == "__main__":
    main()
