from poke_env.battle import AbstractBattle, Battle
from poke_env.player import Player
from poke_env import AccountConfiguration
from poke_env.player.battle_order import BattleOrder
from poke_env.battle import Move
from poke_env.battle import Pokemon
from poke_env.calc.damage_calc_gen9 import calculate_damage
from typing import Tuple, cast

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
    def choose_move(self, battle: AbstractBattle) -> BattleOrder:
        # Cast: Ensure battle is of correct type
        if not isinstance(battle, Battle):
            print("ERROR: Expected battle to be of type Battle")
            return self.choose_random_move(battle)

        # Is this ever possible?
        if (not battle.active_pokemon) or (not battle.opponent_active_pokemon):
            # Random for now
            return self.choose_random_move(battle)

        if battle.force_switch:
            # TODO: Implement smart switch
            return self.choose_random_move(battle)

        ## If half health, and can regen, use it
        if battle.active_pokemon.current_hp / battle.active_pokemon.max_hp < 0.5:
            move = self.findMove(battle.available_moves, "recover")
            if move:
                return self.create_order(move)

        ## Hazards
        hazardsToMax = { "stealthrock": 1, "toxicspikes": 2, "spikes": 3 }
        for hazard_name, max_layers in hazardsToMax.items():
            # print(f"Checking {hazard_name}...")

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

        return self.choose_max_damage_move(battle)

    # MARK: DAMAGE HEURISTICS
    def estimate_damage(self, attacker: Pokemon, defender: Pokemon, move: Move, battle: Battle, attackingOpponent: bool) -> Tuple[float, float]:
        attacker_id = self.generateIdentifier(attacker, attackingOpponent, battle)
        defender_id = self.generateIdentifier(defender, not attackingOpponent, battle)
        try:
            return calculate_damage(attacker_id, defender_id, move, battle)
        except Exception as e:
            print(f"ERROR: couldn't estimating damage ({attacker_id} -{move.id}-> {defender_id}): {e}")
            return 0, 0

    # Get ID string needed for damage calculator
    # Also ensures opponent has stats, yeak ik
    def generateIdentifier(self, pokemon: Pokemon, isP1: bool, battle: Battle) -> str:
        key = None
        pokemons_list = battle.team if isP1 else battle.opponent_team

        # For each 'None' value in stats, backfill from base_stats
        for stat in pokemon.base_stats:
            if pokemon.stats[stat] is None:
                pokemon.stats[stat] = pokemon.base_stats[stat]

        for k, v in pokemons_list.items():
            if v == pokemon:
                key = k
                # print(f"Generated identifier for {pokemon}: {key}")
                return key
        print("ERROR: Pokemon identifier not found")
        return ""

    # From max damage bot
    def choose_max_damage_move(self, battle: Battle) -> BattleOrder:
        # Chooses a move with the highest base power when possible
        if (
            battle.available_moves
            and battle.active_pokemon is not None
            and battle.opponent_active_pokemon is not None
        ):
            # Iterating over available moves to find the one with the highest base power
            best_move = max(
                battle.available_moves,
                key=lambda move: self.estimate_damage(
                    cast(Pokemon, battle.active_pokemon),
                    cast(Pokemon, battle.opponent_active_pokemon),
                    move,
                    battle,
                    True
                )[1]  # Use max damage value for comparison
            )
            # Creating an order for the selected move
            return self.create_order(best_move)
        # If no attacking move is available, perform a random switch
        # This involves choosing a random move, which could be a switch or another available action
        print("WARN: No attacking move available. Choosing random move.")
        return self.choose_random_move(battle)

    # MARK: HELPERS

    def findMove(self, moves: list[Move], move_name: str) -> Move | None:
        for move in moves:
            if move.id == move_name:
                return move
        return None
