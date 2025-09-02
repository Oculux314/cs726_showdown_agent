import json
from poke_env.battle import AbstractBattle
from poke_env.player import Player
from poke_env import AccountConfiguration
from poke_env.player.battle_order import BattleOrder
# Import move
from poke_env.battle import Move

# MARK: TEAM
team = """
Forretress (F) @ Leftovers
Ability: Sturdy
Tera Type: Bug
EVs: 252 HP / 252 Def / 4 SpD
Relaxed Nature
IVs: 0 Spe
- Spikes
- Toxic Spikes
- Stealth Rock
- Rapid Spin

Great Tusk @ Leftovers
Ability: Protosynthesis
Tera Type: Ground
EVs: 252 HP / 252 Def / 4 Spe
Impish Nature
- Rapid Spin
- Stealth Rock
- Headlong Rush
- Knock Off

Slowking-Galar (F) @ Heavy-Duty Boots
Ability: Regenerator
Tera Type: Poison
EVs: 252 HP / 4 Def / 252 SpD
Calm Nature
- Future Sight
- Sludge Bomb
- Toxic
- Slack Off

Toxapex (F) @ Black Sludge
Ability: Regenerator
Tera Type: Poison
EVs: 252 HP / 252 Def / 4 SpD
Bold Nature
IVs: 0 Atk
- Toxic
- Recover
- Haze
- Surf

Gholdengo @ Leftovers
Ability: Good as Gold
Tera Type: Steel
EVs: 252 HP / 80 Def / 176 Spe
Bold Nature
- Make It Rain
- Nasty Plot
- Recover
- Thunder Wave

Clodsire @ Leftovers
Ability: Unaware
Tera Type: Water
EVs: 252 HP / 4 Def / 252 SpD
Careful Nature
- Recover
- Toxic
- Toxic Spikes
- Stealth Rock
"""

# MARK: GLOBALS
round_count = 0

class CustomAgent(Player):
    def __init__(self, *args: AccountConfiguration | None, **kwargs: object):
        super().__init__(team=team, *args, **kwargs)

    def teampreview(self, battle: AbstractBattle) -> str:
        return "/team 123456"

    # MARK: CHOOSE MOVE
    def choose_move(self, battle: AbstractBattle):

        ## If half health, and can regen, use it
        if battle.active_pokemon.current_hp / battle.active_pokemon.max_hp < 0.5:
            move = self.findMove(battle.available_moves, "recover")
            if move:
                return self.create_order(move)

        ## Hazards
        hazardsToMax = { "stealthrock": 1, "toxicspikes": 2, "spikes": 3 }
        for hazard_name, max_layers in hazardsToMax.items():
            print(f"Checking {hazard_name}...")

            # Get move & side condition
            move = self.findMove(battle.available_moves, hazard_name)
            side_condition = move.side_condition if move else None
            if not side_condition:
                # print(f"REJECTED: {battle.active_pokemon.species} has no move that applies {hazard_name}.")
                continue

            # Get current layers
            current_layers = battle.opponent_side_conditions.get(side_condition, 0)

            # If we can apply another layer, do it
            if current_layers < max_layers:
                move = self.findMove(battle.available_moves, hazard_name)
                if move:
                    print(f"ACCEPTED: {battle.active_pokemon.species} applied {hazard_name} using {move.id}.")
                    return self.create_order(move)



        # global round_count
        # round_count += 1
        # print(f"\nROUND {round_count}:")
        # print(f"Active Pokemon: {battle.active_pokemon}")
        # print(f"Available Moves: {battle.available_moves}")
        # print(f"Available Switches: {battle.available_switches}")
        # print(f"Team: {battle.team.values()}")
        # print(f"Opponent Active: {battle.opponent_active_pokemon}")
        # print(f"Opponent Moves: {battle.opponent_active_pokemon}")
        # print(f"Opponent Team: {battle.opponent_team.values()}")
        return self.choose_max_damage_move(battle)

    # MARK: MAX DAMAGE
    # From max damage bot
    def choose_max_damage_move(self, battle: AbstractBattle):
        # Chooses a move with the highest base power when possible
        if battle.available_moves:
            # Iterating over available moves to find the one with the highest base power
            best_move = max(battle.available_moves, key=lambda move: move.base_power)
            # Creating an order for the selected move
            return self.create_order(best_move)
        else:
            # If no attacking move is available, perform a random switch
            # This involves choosing a random move, which could be a switch or another available action
            return self.choose_random_move(battle)

    # MARK: HELPERS

    def findMove(self, moves: list[Move], move_name: str) -> Move | None:
        for move in moves:
            if move.id == move_name:
                return move
        return None
