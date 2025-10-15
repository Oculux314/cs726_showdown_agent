from typing import Any, Tuple, cast
from poke_env.battle import AbstractBattle, Battle
from poke_env.player import Player
from poke_env import AccountConfiguration
from poke_env.player.battle_order import BattleOrder
from poke_env.battle import Move
from poke_env.battle import Pokemon
from poke_env.calc.damage_calc_gen9 import calculate_damage
from poke_env.data.gen_data import GenData
from poke_env.battle import Effect
from poke_env.data.normalize import to_id_str
from poke_env import SimpleHeuristicsPlayer
import requests

## MARK: Simple Agent
class DummyOpponentAgent(SimpleHeuristicsPlayer):
    def __init__(self, team, *args, **kwargs):
        super().__init__(team=team, *args, **kwargs)

# MARK: TEAM
team = """
Koraidon @ Life Orb
Ability: Orichalcum Pulse
Tera Type: Fire
EVs: 252 Atk / 4 SpD / 252 Spe
Jolly Nature
- Flare Blitz
- Close Combat
- Outrage
- Zen Headbutt

Arceus-Ground @ Earth Plate
Ability: Multitype
Tera Type: Fairy
EVs: 248 HP / 8 SpA / 252 Spe
Timid Nature
IVs: 0 Atk
- Judgment
- Ice Beam
- Recover
- Earth Power

Necrozma-Dusk-Mane @ Leftovers
Ability: Prism Armor
Tera Type: Flying
EVs: 252 HP / 252 Def / 4 SpD
Impish Nature
IVs: 0 SpA
- Sunsteel Strike
- Earthquake
- Morning Sun
- Stealth Rock

Kyogre @ Expert Belt
Ability: Drizzle
Tera Type: Water
EVs: 252 SpA / 4 SpD / 252 Spe
Modest Nature
IVs: 0 Atk
- Water Spout
- Origin Pulse
- Ice Beam
- Thunder

Flutter Mane @ Life Orb
Ability: Protosynthesis
Tera Type: Fairy
EVs: 4 Def / 252 SpA / 252 Spe
Timid Nature
IVs: 0 Atk
- Moonblast
- Shadow Ball
- Energy Ball
- Power Gem

Ting-Lu @ Leftovers
Ability: Vessel of Ruin
Tera Type: Poison
EVs: 252 HP / 4 Atk / 252 SpD
Careful Nature
IVs: 0 SpA
- Earthquake
- Ruination
- Body Press
- Heavy Slam
"""

# MARK: MEMORY
class Memory:
    def __init__(self):
        self.knockoffed_pokes = cast(set[str], set()) # species names of pokes that have been knockoffed
        self.last_used_future_sight = -10 # round number when future sight was last used
        self.toxiced_pokes = cast(set[str], set()) # species names of pokes that have been toxiced
        self.prev_damage = cast(dict[tuple[str, str, str], float], {}) # attacker_id, defender_id, move_id -> damage

# MARK: GLOBALS
gen9_data = GenData.from_gen(9)
memory = cast(dict[str, Memory], {}) # battle_tag -> Memory

class CustomAgent(Player):

    # MARK: INIT
    def __init__(self, *args: AccountConfiguration | None, **kwargs: object):
        super().__init__(team=team, *args, **kwargs)

    def teampreview(self, battle: AbstractBattle) -> str:
        memory[battle.battle_tag] = Memory() # Set up memory for this battle
        # Cast: Ensure battle is of correct type
        if not isinstance(battle, Battle):
            print("ERROR: Expected battle to be of type Battle")
            return "/team 123456"

        # return "/team 123456"

        # Assume opponent will lead with first pokemon
        try:
            best_lead_order = self.choose_forced_switch(battle)
            best_lead_species = cast(str, best_lead_order.order.species)
            # print(f"DEBUG: Teampreview chose {best_lead_species}")
            best_lead_index = next((i for i, p in enumerate(battle.team.values()) if p.species == best_lead_species), 0)
            return f"/team {best_lead_index + 1}" + "123456".replace(str(best_lead_index + 1), "")
        except Exception as e:
            print(f"ERROR: in teampreview method: {e}")
            return "/team 123456"

    ## MARK: BATTLE MSGs
    async def _handle_battle_message(self, split_messages: list[list[str]]) -> None:
        await super()._handle_battle_message(split_messages)
        battle = await self._get_battle(split_messages[0][0])

        # Remember moves which did no damage due to immunity
        attacking_poke = ""
        current_move = ""
        defender_poke = ""
        for msg in split_messages:
            if len(msg) < 2:
                continue
            if msg[1] == 'move':
                attacking_poke = to_id_str(msg[2][4:])
                current_move = to_id_str(msg[3])
                defender_poke = to_id_str(msg[4][4:])
            if msg[1] == '-immune':
                memory[battle.battle_tag].prev_damage[(attacking_poke, defender_poke, current_move)] = 0

    def aggregateAllMessages(self, battle: Battle) -> str:
        # Make a network call to localhost:3001 to get latest data
        try:
            # Make the API call
            response = requests.get(
                f"http://localhost:3002/battle/{battle.battle_tag}/log",
                timeout=5
            )

            if response.status_code == 200:
                return response.json().get("log", "NO LOG")
            else:
                return f"API call failed with status {response.status_code}"
        except requests.exceptions.RequestException as e:
            return f"Network error: {str(e)}"
        except Exception as e:
            return f"Error aggregating messages: {str(e)}"

    def choose_move(self, battle: AbstractBattle) -> BattleOrder:
        # print(f"--- ROUND {battle.turn} ---")

        # Cast: Ensure battle is of correct type
        if not isinstance(battle, Battle):
            print("ERROR: Expected battle to be of type Battle")
            return self.choose_random_move(battle)

        # msg = self.aggregateAllMessages(battle)
        # print(msg)

        # Safeguard against unexpected errors
        try:
            if battle.force_switch:
                return self.choose_forced_switch(battle)
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

        # Try switching if we can
        switch_order = self.try_switch(battle)
        if switch_order:
            return switch_order

        ## If half health, and can regen, use it
        if battle.active_pokemon.current_hp / battle.active_pokemon.max_hp < 0.5:
            # Check for heal block
            if battle.active_pokemon.effects.get(Effect.HEAL_BLOCK):
                print(f"INFO: {battle.active_pokemon.species} is affected by Heal Block, cannot use recovery move")
            else:
                move = self.findMove(battle.available_moves, "recover")
                if not move:
                    move = self.findMove(battle.available_moves, "slackoff")
                if not move:
                    move = self.findMove(battle.available_moves, "morningsun")
                if move:
                    # print(f"ACCEPTED: {battle.active_pokemon.species} used recovery move.")
                    return self.create_order(move)

        ## Hazards
        hazardsToMax = { "stealthrock": 1, "spikes": 3, "toxicspikes": 2 }
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
                    # print(f"ACCEPTED: {battle.active_pokemon.species} applied {hazard_name} using {move.id}.")
                    return self.create_order(move)

        ## Knock off if we can and haven't already
        if battle.active_pokemon.species not in memory[battle.battle_tag].knockoffed_pokes:
            move = self.findMove(battle.available_moves, "knockoff")
            if move:
                memory[battle.battle_tag].knockoffed_pokes.add(battle.active_pokemon.species)
                print(f"ACCEPTED: {battle.active_pokemon.species} used knockoff.")
                return self.create_order(move)

        ## Rapid Spin if we can and hazards are up
        if self.check_hazards(battle) > 0:
            move = self.findMove(battle.available_moves, "rapidspin")
            if move:
                return self.create_order(move)

        ## Toxic if we can and opponent isn't already statused
        if not self.opponent_has_status(battle, "tox") and battle.opponent_active_pokemon.species not in memory[battle.battle_tag].toxiced_pokes:
            move = self.findMove(battle.available_moves, "toxic")
            if move:
                # print("DEBUG: Using Toxic. Current toxiced pokes:", memory[battle.battle_tag].toxiced_pokes)
                memory[battle.battle_tag].toxiced_pokes.add(battle.opponent_active_pokemon.species) # Avoid re-toxicing with same pokemon
                # print("DEBUG: Current toxiced pokes:", memory[battle.battle_tag].toxiced_pokes)
                return self.create_order(move)

        ## Gholdengo Nasty Plot
        if battle.active_pokemon.species == 'gholdengo':
            # Get current Special Attack
            sp_atk_boosts = battle.active_pokemon.boosts.get('spa', 0)
            health_pct = battle.active_pokemon.current_hp_fraction
            if sp_atk_boosts < 6 and health_pct > 0.5:
                move = self.findMove(battle.available_moves, "nastyplot")
                if move:
                    return self.create_order(move)

        ## Necrozma Dusk Mane Swords Dance
        if battle.active_pokemon.species == 'necrozmaduskmane':
            # Get current Attack
            atk_boosts = battle.active_pokemon.boosts.get('atk', 0)
            health_pct = battle.active_pokemon.current_hp_fraction
            if atk_boosts < 6 and health_pct > 0.5:
                move = self.findMove(battle.available_moves, "swordsdance")
                if move:
                    return self.create_order(move)

        ## If all else fails, just go for max damage
        return self.choose_max_damage_move(battle)

    # MARK: STATUS CHECKS
    def check_hazards(self, battle: Battle) -> int:
        total_hazards = 0
        hazards = battle.side_conditions.items()
        for _condition, layers in hazards:
            total_hazards += layers
        return total_hazards

    def opponent_has_status(self, battle: Battle, status: str) -> bool:
        if not battle.opponent_active_pokemon:
            return False
        opp_status = battle.opponent_active_pokemon.status
        if not opp_status:
            return False
        return status.lower() == opp_status.name.lower()

    # MARK: SWITCHING

    # Find first non-fainted opponent pokemon
    def findFirstNonFaintedOpponent(self, battle: dict[str, Pokemon]) -> Pokemon | None:
        for poke in battle.values():
            if not poke.fainted:
                return poke
        return None

    # Only when pokemon faints or otherwise forced
    def choose_forced_switch(self, battle: Battle) -> BattleOrder:
        opponent_pokemon = battle.opponent_active_pokemon

        # If we have no available switches, random
        if not opponent_pokemon:
            opponent_pokemon = self.findFirstNonFaintedOpponent(battle.opponent_team)
            if not opponent_pokemon:
                print("INFO: No opponent active pokemon, choosing random move")
                return self.choose_random_move(battle)
        if len(battle.available_switches) == 0:
            print("INFO: No available switches, choosing random move")
            return self.choose_random_move(battle)

        best_switch = self.getPokemonToTypeScore(battle, opponent_pokemon)[0]
        # print(f"DEBUG: Switching to {best_switch[0].species} with type score {best_switch[1]:.2f}")
        return self.create_order(best_switch[0])

    # Return None if better to stay in
    def try_switch(self, battle: Battle) -> BattleOrder | None:
        if not battle.active_pokemon:
            print("ERROR: No active pokemon, this should never happen")
            return None
        # If opponent is fainted, better to stay in and attack
        if not battle.opponent_active_pokemon:
            print("INFO: No opponent active pokemon, choosing to stay in")
            return None
        if len(battle.available_switches) == 0:
            # print("INFO: No available switches, choosing to stay in")
            return None

        current_pokemon = battle.active_pokemon
        opposing_pokemon = battle.opponent_active_pokemon
        type_score_current = self.getTypeScoreTwoWay(current_pokemon, opposing_pokemon)
        switches = self.getPokemonToTypeScore(battle, opposing_pokemon)
        best_switch = switches[0]

        if best_switch[0].species == 'gholdengo' and len(switches) > 1 and switches[1][1] < best_switch[1] * 1.2:
            # print(f"INFO: Avoiding switch to {best_switch[0].species}")
            best_switch = switches[1] # Avoid switching to Gholdengo unless it's clearly better

        if best_switch[1] > type_score_current * 1.5:
            # print(f"INFO: Switching to {best_switch[0].species}")
            return self.create_order(best_switch[0])
        # print("INFO: Better to stay in")
        return None

    def getPokemonToTypeScore(self, battle: Battle, opponent_pokemon: Pokemon) -> list[tuple[Pokemon, float]]:
        result = cast(list[tuple[Pokemon, float]], [])
        for poke in battle.available_switches:
            result.append((poke, self.getTypeScoreTwoWay(poke, opponent_pokemon) if opponent_pokemon else 1))
        # Sort by descending type score
        result.sort(key=lambda x: x[1], reverse=True)
        return result

    # MARK: DAMAGE HEURISTICS
    def estimate_damage(self, attacker: Pokemon, defender: Pokemon, move: Move, battle: Battle, attackingOpponent: bool) -> Tuple[float, float]:
        attacker_id = self.generateIdentifier(attacker, attackingOpponent, battle)
        defender_id = self.generateIdentifier(defender, not attackingOpponent, battle)

        attacker_simple_id = to_id_str(attacker_id[3:])
        defender_simple_id = to_id_str(defender_id[3:])
        if (attacker_simple_id, defender_simple_id, move.id) in memory[battle.battle_tag].prev_damage:
            damage = memory[battle.battle_tag].prev_damage[(attacker_simple_id, defender_simple_id, move.id)]
            return damage, damage

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
            # Iterating over available moves to find the one with the highest expected damage
            best_move = self.getMaxDamageMove(battle)
            # Creating an order for the selected move
            return self.create_order(best_move)
        # If no attacking move is available, perform a random switch
        # This involves choosing a random move, which could be a switch or another available action
        print("WARN: No attacking move available. Choosing random move.")
        return self.choose_random_move(battle)

    def getMaxDamageMove(self, battle: Battle) -> Move:
        ranked_moves = self.getRankedMovesByDamage(battle)
        best_move = ranked_moves[0][0] if ranked_moves else battle.available_moves[0]

        # Avoid wasting moves like Future Sight
        if best_move.id == "futuresight" and battle.turn - memory[battle.battle_tag].last_used_future_sight < 3:
            if len(ranked_moves) > 1:
                best_move = ranked_moves[1][0]
        if best_move.id == "futuresight": # Update memory only if we actually use Future Sight
            memory[battle.battle_tag].last_used_future_sight = battle.turn

        return best_move

    def getRankedMovesByDamage(self, battle: Battle) -> list[tuple[Move, float]]:
        """Returns moves ranked by average damage in descending order."""
        move_damage_pairs: list[tuple[Move, float]] = []

        for move in battle.available_moves:
            min_damage, max_damage = self.estimate_damage(
                cast(Pokemon, battle.active_pokemon),
                cast(Pokemon, battle.opponent_active_pokemon),
                move,
                battle,
                True
            )
            avg_damage = (min_damage + max_damage) / 2.0
            move_damage_pairs.append((move, avg_damage))

        # Sort by average damage in descending order
        move_damage_pairs.sort(key=lambda x: x[1], reverse=True)
        return move_damage_pairs

    # MARK: TYPE HEURISTICS

    # >0 means A is better, <0 means B is better
    def getTypeScoreTwoWay(self, pokemonA: Pokemon, pokemonB: Pokemon) -> float:
        scoreAToB = self.getTypeScoreOneWay(pokemonA, pokemonB) # A -> B
        scoreBToA = self.getTypeScoreOneWay(pokemonB, pokemonA) # B -> A
        if scoreBToA == 0:
            # print("WARN: Division by zero in type score calculation, returning large value")
            return float("inf")
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

        if score / attacker_type_histogram.get("TOTAL", 1) == 0:
            # print("WARN: Division by zero in type score calculation, returning 0")
            return 0.0

        return score / attacker_type_histogram.get("TOTAL", 1)

    def getTypeMultiplier(self, attacking_type: str, defending_type: str) -> float:
        return gen9_data.type_chart.get(defending_type, {}).get(attacking_type, 1.0)

    def getLearnableMoves(self, pokemon: Pokemon) -> dict[str, Any]:
        if pokemon.moves and len(pokemon.moves) > 0:
            return {move_id: gen9_data.moves[move_id] for move_id in pokemon.moves if move_id in gen9_data.moves}

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









## MARK: MONTE CARLO AGENT

# class CustomAgent(Player):

#     def __init__(self, *args: AccountConfiguration | None, **kwargs: object):
#         super().__init__(team=team, *args, **kwargs)

#     def teampreview(self, battle: AbstractBattle) -> str:
#         return "/team 123456"

#     def choose_move(self, battle: AbstractBattle) -> BattleOrder:
#         # Cast: Ensure battle is of correct type
#         if not isinstance(battle, Battle):
#             print("ERROR: Expected battle to be of type Battle")
#             return self.choose_random_move(battle)

#         # Safeguard against unexpected errors
#         try:
#             if battle.force_switch:
#                 return self.choose_forced_switch(battle)
#             return self.choose_move_impl(battle)
#         except Exception as e:
#             print(f"ERROR: in main method: {e}")
#             return self.choose_max_damage_move(battle)