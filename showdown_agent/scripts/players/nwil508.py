import json
from poke_env.battle import AbstractBattle
from poke_env.player import Player
from poke_env import AccountConfiguration
from poke_env.player.battle_order import BattleOrder

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

round_count = 0

class CustomAgent(Player):
    def __init__(self, *args: AccountConfiguration | None, **kwargs: object):
        super().__init__(team=team, *args, **kwargs)
        # Forfeit current battle if exists
        # self.reset_battles()

    def teampreview(self, battle: AbstractBattle) -> str:
        return "/team 123456"

    def choose_move(self, battle: AbstractBattle):

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

        return self.choose_random_move(battle)
        # return battle.available_moves[0]
