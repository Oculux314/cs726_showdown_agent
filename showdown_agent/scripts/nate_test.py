import asyncio
import importlib.util
import os
import sys
from players.nwil508 import CustomAgent
from poke_env.player import Player

from poke_env import AccountConfiguration
from poke_env.teambuilder import

def gather_players() -> list[CustomAgent]:
    """Load all player bots from the players folder using the original method."""
    players_dir = os.path.join(os.path.dirname(__file__), "players")
    players = []
    replay_dir = os.path.join(os.path.dirname(__file__), "replays")
    if not os.path.exists(replay_dir):
        os.makedirs(replay_dir)

    for module_name in os.listdir(players_dir):
        if not module_name.endswith(".py"):
            continue

        module_path = os.path.join(players_dir, module_name)
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Get the class
        if hasattr(module, "CustomAgent"):
            player_name = module_name[:-3]
            agent_class = getattr(module, "CustomAgent")
            agent_replay_dir = os.path.join(replay_dir, player_name)
            if not os.path.exists(agent_replay_dir):
                os.makedirs(agent_replay_dir)

            account_config = AccountConfiguration(player_name, None)
            player = agent_class(
                account_configuration=account_config,
                battle_format="gen9ubers",
            )

            # attach replay dir for later use
            player._save_replays = agent_replay_dir
            players.append(player)

    return players


async def human_vs_bot_battle(bot_player):
    """Run a battle between human and bot."""
    # Accept 1 challenge from anyone
    print("Waiting for challenges...")
    await bot_player.accept_challenges(None, 1)
    print("\nBattle is ready to begin!")

    # Print battle results
    for battle_id, battle in bot_player.battles.items():
        if battle.finished:
            result = "Won" if battle.won else "Lost"
            print(f"\nBattle Result: You {result}!")
            print(f"Battle lasted {battle.turn} turns")
            if hasattr(bot_player, "_save_replays"):
                print(f"Bot replays saved to: {bot_player._save_replays}")
        else:
            print(f"Battle {battle_id} is still ongoing...")

def gather_bots() -> list[Player]:
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




## MARK: MAIN

async def main():
    print("Loading players & bots...")
    players = gather_players()
    print(f"Loaded {len(players)} player bots.")
    bots = gather_bots()
    print(f"Loaded {len(bots)} bot agents.")

    if not players or not bots:
        print("No players or bots found. Exiting.")
        return

    # For simplicity, we'll just use the first player and first bot
    player = players[0]
    bot = bots[0]
    print(f"Starting battle between human and bot: {bot.__class__.__name__}")

    await player.battle_against(bot)
    for battle_tag, battle in player.battles.items():
        print(battle_tag, battle.won)
        if battle.finished:
            result = "Won" if battle.won else "Lost"
            print(f"\nBattle Result: You {result}!")
            print(f"Battle lasted {battle.turn} turns")
        else:
            print(f"Battle {battle_tag} is still ongoing...")

    player.reset_battles()
    bot.reset_battles()


if __name__ == "__main__":
    asyncio.run(main())
