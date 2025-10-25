import os
import time
from typing import Any, Dict, TypedDict
from typing import Tuple, cast

import numpy as np
from typing_extensions import NotRequired
from poke_env import (
    AccountConfiguration,
    MaxBasePowerPlayer,
    RandomPlayer,
    SimpleHeuristicsPlayer,
)
from poke_env.battle import AbstractBattle
from poke_env.battle import Battle
from poke_env.environment.single_agent_wrapper import SingleAgentWrapper
from poke_env.player.player import Player
from poke_env.data import GenData

from poke_env.player.battle_order import BattleOrder, SingleBattleOrder
from poke_env.battle import Move
from poke_env.battle import Pokemon
from poke_env.calc.damage_calc_gen9 import calculate_damage
from poke_env.battle import Effect
from poke_env.data.normalize import to_id_str
from poke_env.battle.pokemon_type import PokemonType
import requests

from showdown_gym.base_environment import BaseShowdownEnv


# MARK: EXPERT AGENT

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


# MARK: GLOBALS
gen9_data = GenData.from_gen(9)

class CustomAgent(Player):

    # MARK: INIT
    def __init__(self, *args: AccountConfiguration | None, **kwargs: object):
        super().__init__(team=team, *args, **kwargs)

    def teampreview(self, battle: AbstractBattle) -> str:
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
                for move in battle.available_moves:
                    if move.heal > 0:
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
        move = self.findMove(battle.available_moves, "knockoff")
        if move:
            print(f"ACCEPTED: {battle.active_pokemon.species} used knockoff.")
            return self.create_order(move)

        ## Rapid Spin if we can and hazards are up
        if self.check_hazards(battle) > 0:
            move = self.findMove(battle.available_moves, "rapidspin")
            if move:
                return self.create_order(move)

        ## Toxic if we can and opponent isn't already statused
        if not self.opponent_has_status(battle, "tox"):
            move = self.findMove(battle.available_moves, "toxic")
            if move:
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













# MARK: TYPES
class Action(TypedDict):
    chosen_action: np.int64
    true_action: np.int64

class Reward(TypedDict):
    reward: float
    suggested: int

class Log(TypedDict):
    state: np.ndarray[np.float32, np.dtype[np.float32]]
    action: NotRequired[Action]
    reward: NotRequired[Reward]

# MARK: GLOBALS
PRINT_LOGS = True

gen9_data = GenData.from_gen(9)
logs: list[Log] = []
expertAgent = CustomAgent()
simpleAgent = DummyOpponentAgent("")

class ShowdownEnvironment(BaseShowdownEnv):

    def __init__(
        self,
        battle_format: str = "gen9randombattle",
        account_name_one: str = "train_one",
        account_name_two: str = "train_two",
        team: str | None = None,
    ):
        super().__init__(
            battle_format=battle_format,
            account_name_one=account_name_one,
            account_name_two=account_name_two,
            team=team,
        )

        self.rl_agent = account_name_one

    # -----------------------------------------------------------------------------------------------------------------------------------------
    # MARK: ACTION SIZE
    def _get_action_size(self) -> int | None:
        """
        None just uses the default number of actions as laid out in process_action - 26 actions.

        This defines the size of the action space for the agent - e.g. the output of the RL agent.

        This should return the number of actions you wish to use if not using the default action scheme.
        """
        return 10  # Return None if action size is default

    # -----------------------------------------------------------------------------------------------------------------------------------------
    # MARK: ACTION
    def process_action(self, action: np.int64) -> np.int64:
        """
        Returns the np.int64 relative to the given action.

        The action mapping is as follows:
        action = -2: default
        action = -1: forfeit
        0 <= action <= 5: switch
        6 <= action <= 9: move
        10 <= action <= 13: move and mega evolve
        14 <= action <= 17: move and z-move
        18 <= action <= 21: move and dynamax
        22 <= action <= 25: move and terastallize

        :param action: The action to take.
        :type action: int64

        :return: The battle order ID for the given action in context of the current battle.
        :rtype: np.Int64
        """

        if PRINT_LOGS: print("--------------------------------------------------------")
        # 0-3 => 6-9
        true_action = action

        if PRINT_LOGS: print(f"Action: {action} ({true_action})")
        logs[-1]["action"] = {"chosen_action": action, "true_action": true_action}
        return true_action

    # -----------------------------------------------------------------------------------------------------------------------------------------
    # MARK: INFO
    def get_additional_info(self) -> Dict[str, Dict[str, Any]]:
        info = super().get_additional_info()

        # Add any additional information you want to include in the info dictionary that is saved in logs
        # For example, you can add the win status

        if self.battle1 is not None and self.battle1.won is not None:
            agent = self.possible_agents[0]
            info[agent]["win"] = self.battle1.won
            # info[agent]["logs"] = logs
            # Reset logs if battle is over
            # info[agent]["logs"] = logs.copy()
            logs.clear()
            # Timestamp
            info[agent]["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")


        # if print_logs: print(f"Info: {info}")
        return info

    # -----------------------------------------------------------------------------------------------------------------------------------------
    # MARK: REWARD
    def calc_reward(self, battle: AbstractBattle) -> float:
        """
        Calculates the reward based on the changes in state of the battle.

        You need to implement this method to define how the reward is calculated

        Args:
            battle (AbstractBattle): The current battle instance containing information
                about the player's team and the opponent's team from the player's perspective.
            prior_battle (AbstractBattle): The prior battle instance to compare against.
        Returns:
            float: The calculated reward based on the change in state of the battle.
        """
        if battle.player_username[1] == "2":
            return 0

        reward = 0.0

        # prev_battle = self._get_prior_battle(battle)
        # if prev_battle is None:
        #     print("ERROR: prior battle is None, cannot calculate reward")
        #     return 0.0

        # # Reward for winning
        # if battle.won:
        #     reward += 1.0
        # elif battle.lost:
        #     reward -= 1.0
        # # Reward for KO
        # num_ko = self.getNumberOfFainted(battle.opponent_team) - self.getNumberOfFainted(prev_battle.opponent_team)
        # num_ko_self = self.getNumberOfFainted(battle.team) - self.getNumberOfFainted(prev_battle.team)
        # reward += (num_ko - num_ko_self) * 0.1
        # # Reward for damage dealt
        # if battle.active_pokemon and battle.opponent_active_pokemon:
        #     damage_dealt = self.getDamageDealt(prev_battle.opponent_active_pokemon, battle.opponent_active_pokemon)
        #     damage_taken = self.getDamageDealt(prev_battle.active_pokemon, battle.active_pokemon)
        #     reward += (damage_dealt - damage_taken) * 0.1

        # # Logging
        # status_str = "WIN" if battle.won else ("LOSS" if battle.lost else "ONGOING")
        # stats_string = f"{status_str} | +{num_ko} KOs, -{num_ko_self} Team, DID {damage_dealt:.2f} dmg, TOOK {damage_taken:.2f} dmg"
        # logs[-2]["reward"] = {"reward": reward, "suggested": stats_string}
        # if PRINT_LOGS: print(f"Reward: {reward} ({stats_string})")
        return reward

    # MARK: HELPERS
    def getNumberOfFainted(self, team: Dict[str, Pokemon]) -> int:
        fainted_count = 0
        for mon in team.values():
            if mon.fainted:
                fainted_count += 1
        return fainted_count

    def getDamageDealt(self, prior_pokemon: Pokemon, current_pokemon: Pokemon) -> float:
        if prior_pokemon.species != current_pokemon.species:
            return 0.0
        return prior_pokemon.current_hp_fraction - current_pokemon.current_hp_fraction

    # MARK: ORDER -> INDEX
    def getIndexFromOrder(self, battle: Battle, battleOrder: BattleOrder) -> int:
        """
        Returns the index of the given order in the current battle's available orders.

        Args:
            battle (Battle): The current battle instance.
            order (BattleOrder): The battle order to find the index for.
        Returns:
            int: The index of the given order in the battle's available orders.
        """
        # Switches: 0 - 5
        # Moves: 6 - 9
        if not isinstance(battleOrder, SingleBattleOrder):
            raise TypeError("ERROR: Expected simple_agent_move to be of type SingleBattleOrder")
        order = battleOrder.order

        if isinstance(order, Move):
            move_index = battle.available_moves.index(order)
            return move_index + 6  # Move index

        if isinstance(order, Pokemon):
            team_species = [mon.species for mon in battle.team.values()]
            pokemon_index = team_species.index(order.species)
            return pokemon_index  # Switch index

        print(f"ERROR: Order {order} is neither Move nor Pokemon")
        return -2

    def getMoveIndexFromSimple(self, battle: Battle) -> int:
        # Switches: 0 - 5
        # Moves: 6 - 9
        simple_agent_order = simpleAgent.choose_move(battle)
        return self.getIndexFromOrder(battle, simple_agent_order)


    # -----------------------------------------------------------------------------------------------------------------------------------------
    # MARK: OBSERVATION SIZE
    def _observation_size(self) -> int:
        """
        Returns the size of the observation size to create the observation space for all possible agents in the environment.

        You need to set obvervation size to the number of features you want to include in the observation.
        Annoyingly, you need to set this manually based on the features you want to include in the observation from emded_battle.

        Returns:
            int: The size of the observation space.
        """

        # Simply change this number to the number of features you want to include in the observation from embed_battle.
        # If you find a way to automate this, please let me know!
        return 1

    # MARK: OBSERVATION
    def embed_battle(self, battle: AbstractBattle) -> np.ndarray[np.float32, np.dtype[np.float32]]:
        """
        Embeds the current state of a Pokémon battle into a numerical vector representation.
        This method generates a feature vector that represents the current state of the battle,
        this is used by the agent to make decisions.

        You need to implement this method to define how the battle state is represented.

        Args:
            battle (AbstractBattle): The current battle instance containing information about
                the player's team and the opponent's team.
        Returns:
            np.float32: A 1D numpy array containing the state you want the agent to observe.
        """
        if battle.player_username[1] == "2":
            return np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)

        if not isinstance(battle, Battle):
            raise TypeError("ERROR: Expected battle to be of type Battle")

        if battle.active_pokemon is None or battle.opponent_active_pokemon is None:
            raise TypeError("ERROR: Battle or active pokemon is None")

        # Health of active pokemon
        health_active = battle.active_pokemon.current_hp_fraction
        type_active_1 = battle.active_pokemon.type_1.value
        type_active_2 = battle.active_pokemon.type_2.value if battle.active_pokemon.type_2 else 0
        health_team = [mon.current_hp_fraction for mon in battle.team.values()]
        team_species = [mon.species for mon in battle.team.values()]
        team_types_1 = [mon.type_1.value for mon in battle.team.values()]
        team_types_2 = [mon.type_2.value if mon.type_2 else 0 for mon in battle.team.values()]
        current_pokemon_index = team_species.index(battle.active_pokemon.species)
        if PRINT_LOGS: print(f"Team: {health_active} ({current_pokemon_index}) {health_team}")

        # Type of each move
        move_strs = [move for move in battle.active_pokemon.moves]
        moves = [gen9_data.moves.get(move_str) for move_str in move_strs]
        assert None not in moves, "ERROR: Move not found in gen9_data"
        moves = [move for move in moves if move is not None]

        # moves_damages = [move.get("basePower") for move in moves]
        # move_types = [PokemonType.from_name(move.get("type")).value for move in moves]

        # # Opponent
        health_opponent = battle.opponent_active_pokemon.current_hp_fraction
        health_opp_team = [mon.current_hp_fraction for mon in battle.opponent_team.values()]
        health_opp_team.extend([1.0] * (6 - len(health_opp_team)))
        if PRINT_LOGS: print(f"Opponent: {health_opponent} {health_opp_team}")
        type1_opponent = battle.opponent_active_pokemon.type_1.value
        type2_opponent = battle.opponent_active_pokemon.type_2.value if battle.opponent_active_pokemon.type_2 else 0

        # True Move Damage
        moves_true_dmg: list[float] = []
        moves_pp: list[int] = []
        for i, move in enumerate(moves):
            if PRINT_LOGS: print(f"  {i}: {move.get('name')}  |  BP: {move.get('basePower')}  |  T: {move.get('type')}  |  PP: {move.get('pp')}")
            move_id = Move.retrieve_id(move.get("name"))
            real_move = battle.active_pokemon.moves.get(move_id)
            if real_move is None:
                print(f"ERROR: real_move for {move.get('name')} is None")
                moves_true_dmg.append(0)
                moves_pp.append(0)
                break
            dmg_range = expertAgent.estimate_damage(
                attacker=battle.active_pokemon,
                defender=battle.opponent_active_pokemon,
                move=real_move,
                battle=battle,
                attackingOpponent=True
            )
            true_dmg = (dmg_range[0] + dmg_range[1]) / 2.0

            pp = move.get("pp")

            moves_true_dmg.append(true_dmg)
            moves_pp.append(pp)

        # Ensure we have 4 moves, fill missing with default values
        while len(moves_true_dmg) < 4:
            print("WARN: Less than 4 moves_true_dmg found, adding 0")
            moves_true_dmg.append(0)
        while len(moves_pp) < 4:
            print("WARN: Less than 4 moves_pp found, adding 0")
            moves_pp.append(0)

        # Health of team
        # health_team = [mon.current_hp_fraction for mon in battle.team.values()]
        # health_opponent = [
        #     mon.current_hp_fraction for mon in battle.opponent_team.values()
        # ]

        # Ensure health_opponent has 6 components, filling missing values with 1.0 (fraction of health)
        # if len(health_opponent) < len(health_team):
        #     health_opponent.extend([1.0] * (len(health_team) - len(health_opponent)))

        # Previous action
        # prev_action = -1
        # if len(logs) >= 1:
        #     prev_action_info = logs[-1].get("action")
        #     if prev_action_info is not None:
        #         prev_action = prev_action_info.get("chosen_action")

        #########################################################################################################
        # Caluclate the length of the final_vector and make sure to update the value in _observation_size above #
        #########################################################################################################

        # MARK: Final vector
        final_vector = np.concatenate(
            [
                [0]
                # self.normaliseArray(moves_true_dmg, 400.0),  # Normalize damage to [0, 1] assuming max damage is 400
                # self.normaliseArray(moves_pp, 64.0),  # Normalize PP to [0, 1] assuming max PP is 64
                # [health_active],
                # # self.oneHotType(type_active_1),
                # # self.oneHotType(type_active_2),
                # [type_active_1],
                # [type_active_2],
                # health_team,
                # # self.oneHotTypeTeam(team_types_1),
                # # self.oneHotTypeTeam(team_types_2),
                # team_types_1,
                # team_types_2,
                # [current_pokemon_index],
                # # [prev_action],
                # [health_opponent],
                # health_opp_team,
                # # self.oneHotType(type1_opponent),
                # # self.oneHotType(type2_opponent),
                # [type1_opponent],
                # [type2_opponent],
            ]
        )

        # Logs
        if PRINT_LOGS: print(f"Final Vector: {final_vector}")
        logs.append({"state": final_vector.copy()})

        if len(final_vector) != self._observation_size():
            raise ValueError(
                f"ERROR: final_vector size {len(final_vector)} does not match observation_size {self._observation_size()}."
            )

        return final_vector

    # MARK: HELPERS
    def normaliseArray(self, arr: list[float], max_val: float) -> list[float]:
        for i in range(len(arr)):
            arr[i] = arr[i] / max_val
        return arr

    def oneHotTypeTeam(self, pokemon_types: list[int]) -> np.ndarray[np.float32, np.dtype[np.float32]]:
        one_hot_team = np.zeros(18 * 6, dtype=np.float32)
        for i, pokemon_type in enumerate(pokemon_types):
            start_index = i * 18
            if pokemon_type == 0:
                # None
                continue
            one_hot_team[start_index:start_index + 18] = self.oneHotType(pokemon_type)
        return one_hot_team

    def oneHotType(self, pokemon_type: int) -> np.ndarray[np.float32, np.dtype[np.float32]]:
        if pokemon_type == 0:
            # None
            return np.zeros(18, dtype=np.float32)
        return self.oneHotEncode(pokemon_type - 1, 18)

    def oneHotEncode(self, index: int, size: int) -> np.ndarray[np.float32, np.dtype[np.float32]]:
        one_hot = np.zeros(size, dtype=np.float32)
        if index < 0:
            print (f"WARN: oneHotEncode received negative index {index}, returning all zeros")
            return one_hot
        if index >= size:
            print (f"WARN: oneHotEncode received out-of-bounds index {index} for size {size}, returning all zeros")
            return one_hot
        one_hot[index] = 1.0
        return one_hot

########################################
# DO NOT EDIT THE CODE BELOW THIS LINE #
########################################

# MARK: SINGLE AGENT WRAPPER
class SingleShowdownWrapper(SingleAgentWrapper):
    """
    A wrapper class for the PokeEnvironment that simplifies the setup of single-agent
    reinforcement learning tasks in a Pokémon battle environment.

    This class initializes the environment with a specified battle format, opponent type,
    and evaluation mode. It also handles the creation of opponent players and account names
    for the environment.

    Do NOT edit this class!

    Attributes:
        battle_format (str): The format of the Pokémon battle (e.g., "gen9randombattle").
        opponent_type (str): The type of opponent player to use ("simple", "max", "random").
        evaluation (bool): Whether the environment is in evaluation mode.
    Raises:
        ValueError: If an unknown opponent type is provided.
    """

    def __init__(
        self,
        team_type: str = "random",
        opponent_type: str = "random",
        evaluation: bool = False,
    ):
        opponent: Player
        unique_id = time.strftime("%H%M%S")

        opponent_account = "ot" if not evaluation else "oe"
        opponent_account = f"{opponent_account}_{unique_id}"

        opponent_configuration = AccountConfiguration(opponent_account, None)
        if opponent_type == "simple":
            opponent = SimpleHeuristicsPlayer(
                account_configuration=opponent_configuration
            )
        elif opponent_type == "max":
            opponent = MaxBasePowerPlayer(account_configuration=opponent_configuration)
        elif opponent_type == "random":
            opponent = RandomPlayer(account_configuration=opponent_configuration)
        else:
            raise ValueError(f"Unknown opponent type: {opponent_type}")

        account_name_one: str = "t1" if not evaluation else "e1"
        account_name_two: str = "t2" if not evaluation else "e2"

        account_name_one = f"{account_name_one}_{unique_id}"
        account_name_two = f"{account_name_two}_{unique_id}"

        team = self._load_team(team_type)

        battle_format = "gen9randombattle" if team is None else "gen9ubers"

        primary_env = ShowdownEnvironment(
            battle_format=battle_format,
            account_name_one=account_name_one,
            account_name_two=account_name_two,
            team=team,
        )

        super().__init__(env=primary_env, opponent=opponent)

    def _load_team(self, team_type: str) -> str | None:
        bot_teams_folders = os.path.join(os.path.dirname(__file__), "teams")

        bot_teams = {}

        for team_file in os.listdir(bot_teams_folders):
            if team_file.endswith(".txt"):
                with open(
                    os.path.join(bot_teams_folders, team_file), "r", encoding="utf-8"
                ) as file:
                    bot_teams[team_file[:-4]] = file.read()

        if team_type in bot_teams:
            return bot_teams[team_type]

        return None
