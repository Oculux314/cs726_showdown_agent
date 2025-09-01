import asyncio
import importlib.util
import os
import sys

from poke_env import AccountConfiguration


def gather_players():
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


def main():
    print("Loading player bots...")
    players = gather_players()

    if not players:
        print("No player bots found in the 'players' folder!")
        print("Make sure you have .py files with a 'CustomAgent' class in the players directory.")
        return

    print(f"Found {len(players)} player bots:")
    for i, player in enumerate(players, 1):
        print(f"{i}. {player.username}")

    # Select bot to battle against
    while True:
        try:
            choice = int(input(f"\nSelect a bot to battle against (1-{len(players)}): ")) - 1
            if 0 <= choice < len(players):
                selected_bot = players[choice]
                break
            else:
                print("Invalid selection, please try again.")
        except ValueError:
            print("Please enter a valid number.")

    print(f"\nYou will battle against: {selected_bot.username}\n")
    print("Instructions:")
    print("1. Open your browser to http://localhost:8000 (or your server's address)")
    print("2. Send a challenge to the bot (by username) using the web interface")
    print("3. You'll control your team through the web interface")
    print("4. The bot will make moves automatically")

    # Run the battle
    try:
        print("Battle started.")
        asyncio.run(human_vs_bot_battle(selected_bot))
        print("Battle finished.")
    except KeyboardInterrupt:
        print("\nBattle cancelled by user.")
    except Exception as e:
        print(f"\nError during battle: {e}")
        print("Make sure your Pokemon Showdown server is running and accessible.")


if __name__ == "__main__":
    main()
