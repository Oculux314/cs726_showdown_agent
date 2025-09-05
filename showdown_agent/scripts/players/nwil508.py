from typing import Any, Tuple, cast
from poke_env.battle import AbstractBattle, Battle
from poke_env.player import Player
from poke_env import AccountConfiguration
from poke_env.player.battle_order import BattleOrder
from poke_env.battle import Move
from poke_env.battle import Pokemon
from poke_env.calc.damage_calc_gen9 import calculate_damage
from poke_env.data.gen_data import GenData

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
gen9_data = GenData.from_gen(9)

# MARK: INIT
class CustomAgent(Player):
    def __init__(self, *args: AccountConfiguration | None, **kwargs: object):
        super().__init__(team=team, *args, **kwargs)

    def teampreview(self, battle: AbstractBattle) -> str:
        return "/team 123456"

    def choose_move(self, battle: AbstractBattle) -> BattleOrder:
        # Cast: Ensure battle is of correct type
        if not isinstance(battle, Battle):
            print("ERROR: Expected battle to be of type Battle")
            return self.choose_random_move(battle)

        # Safeguard against unexpected errors
        try:
            if battle.force_switch:
                return self.choose_switch(battle)
            return self.choose_move_impl(battle)
        except Exception as e:
            print(f"ERROR: in main method: {e}")
            return self.choose_max_damage_move(battle)

    # MARK: CHOOSE MOVE
    def choose_move_impl(self, battle: Battle) -> BattleOrder:
        # Is this ever possible?
        if (not battle.active_pokemon) or (not battle.opponent_active_pokemon):
            # Random for now
            print("WARN: Missing active pokemon, choosing random move")
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

    # MARK: SWITCHING
    def choose_switch(self, battle: Battle) -> BattleOrder:
        # If we have no available switches, random
        if not battle.opponent_active_pokemon:
            print("INFO: No opponent active pokemon, choosing random move")
            return self.choose_random_move(battle)

        opposing_pokemon = battle.opponent_active_pokemon
        # Find the best switch
        best_switch = max(
            battle.available_switches,
            key=lambda poke: self.getTypeScoreTwoWay(poke, opposing_pokemon)
        )

        type_score = self.getTypeScoreTwoWay(best_switch, opposing_pokemon)
        print(f"DEBUG: Switching to {best_switch.species} with type score {type_score:.2f}")
        return self.create_order(best_switch)

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

    # MARK: TYPE HEURISTICS

    # >0 means A is better, <0 means B is better
    def getTypeScoreTwoWay(self, pokemonA: Pokemon, pokemonB: Pokemon) -> float:
        scoreAToB = self.getTypeScoreOneWay(pokemonA, pokemonB) # A -> B
        scoreBToA = self.getTypeScoreOneWay(pokemonB, pokemonA) # B -> A
        if scoreBToA == 0:
            print("WARN: Division by zero in type score calculation, returning large value")
        return scoreAToB / scoreBToA

    def getTypeScoreOneWay(self, attacker: Pokemon, defender: Pokemon) -> float:
        score = 0.0
        attacker_moves = self.getLearnableMoves(attacker)
        attacker_type_histogram = self.getTypeHistogramForMoves(attacker_moves)

        for attack_type, count in attacker_type_histogram.items():
            if attack_type == "TOTAL":
                continue
            multiplier = 1.0
            for defender_type in defender.types:
                multiplier *= self.getTypeMultiplier(attack_type, defender_type.name)
            # print(f"DEBUG: {attacker.species}'s {attack_type} moves have x{multiplier:.2f} effectiveness against {defender.species} (weight {count})")
            score += multiplier * count

        return score / attacker_type_histogram.get("TOTAL", 1)

    def getTypeMultiplier(self, attacking_type: str, defending_type: str) -> float:
        return gen9_data.type_chart.get(defending_type, {}).get(attacking_type, 1.0)

    def getLearnableMoves(self, pokemon: Pokemon) -> dict[str, Any]:
        learnset_of_original = gen9_data.learnset.get(pokemon.species)
        learnset_of_base = gen9_data.learnset.get(pokemon.base_species) if pokemon.base_species != pokemon.species else {}
        moveset = {**self.getLearnableMovesLearnset(learnset_of_base), **self.getLearnableMovesLearnset(learnset_of_original)}
        if len(moveset) == 0:
            print(f"ERROR: No species data for {pokemon.species}")
            return {}
        return moveset

    def getLearnableMovesLearnset(self, learnset: Any) -> dict[str, Any]:
        if not learnset:
            return {}
        move_ids = list(cast(dict[str, list[str]], learnset.get("learnset", {})).keys())
        moveset = {move_name: gen9_data.moves[move_name] for move_name in move_ids if move_name in gen9_data.moves}
        return moveset

    def getTypeHistogramForMoves(self, moves: dict[str, Any]) -> dict[str, int]:
        types = set(gen9_data.type_chart.keys())
        type_histogram = {t: 0 for t in types} # Initialize all types to 0

        for move in moves.values():
            move_type = cast(str, move.get("type")).upper()
            type_histogram[move_type] = type_histogram.get(move_type, 0) + 1
            type_histogram["TOTAL"] = type_histogram.get("TOTAL", 0) + 1

        # print(f"DEBUG: Move types histogram: {type_histogram}")
        return type_histogram

    # MARK: HELPERS

    def findMove(self, moves: list[Move], move_name: str) -> Move | None:
        for move in moves:
            if move.id == move_name:
                return move
        return None
