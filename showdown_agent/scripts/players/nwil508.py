import json
from poke_env.battle import AbstractBattle
from poke_env.player import Player
from poke_env import AccountConfiguration

team = """
Pikachu @ Focus Sash
Ability: Static
Tera Type: Electric
EVs: 8 HP / 248 SpA / 252 Spe
Timid Nature
IVs: 0 Atk
- Thunder Wave
- Thunder
- Reflect
- Thunderbolt
"""


class CustomAgent(Player):
    def __init__(self, *args: AccountConfiguration | None, **kwargs: object):
        super().__init__(team=team, *args, **kwargs)

    def choose_move(self, battle: AbstractBattle):
        print(json.dumps(battle, indent=2))

        return self.choose_random_move(battle)
