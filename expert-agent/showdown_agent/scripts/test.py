from poke_env import cross_evaluate
from poke_env import RandomPlayer, MaxBasePowerPlayer, SimpleHeuristicsPlayer
from poke_env import AccountConfiguration

uber_team = """
Deoxys-Speed @ Focus Sash  
Ability: Pressure  
Tera Type: Ghost  
EVs: 248 HP / 8 SpA / 252 Spe  
Timid Nature  
IVs: 0 Atk  
- Thunder Wave  
- Spikes  
- Taunt  
- Psycho Boost  

Kingambit @ Dread Plate  
Ability: Supreme Overlord  
Tera Type: Dark  
EVs: 56 HP / 252 Atk / 200 Spe  
Adamant Nature  
- Swords Dance  
- Kowtow Cleave  
- Iron Head  
- Sucker Punch  

Zacian-Crowned @ Rusted Sword  
Ability: Intrepid Sword  
Tera Type: Flying  
EVs: 252 Atk / 4 SpD / 252 Spe  
Jolly Nature  
- Swords Dance  
- Behemoth Blade  
- Close Combat  
- Wild Charge  

Arceus-Fairy @ Pixie Plate  
Ability: Multitype  
Tera Type: Fire  
EVs: 248 HP / 72 Def / 188 Spe  
Bold Nature  
IVs: 0 Atk  
- Calm Mind  
- Judgment  
- Taunt  
- Recover  

Eternatus @ Power Herb  
Ability: Pressure  
Tera Type: Fire  
EVs: 124 HP / 252 SpA / 132 Spe  
Modest Nature  
IVs: 0 Atk  
- Agility  
- Meteor Beam  
- Dynamax Cannon  
- Fire Blast  

Koraidon @ Life Orb  
Ability: Orichalcum Pulse  
Tera Type: Fire  
EVs: 8 HP / 248 Atk / 252 Spe  
Jolly Nature  
- Swords Dance  
- Scale Shot  
- Flame Charge  
- Close Combat  
"""


async def main():

    first_account_config = AccountConfiguration("Random", None)
    first_player = RandomPlayer(
        account_configuration=first_account_config,
        # team=uber_team,
        # battle_format="gen9ubers",
        battle_format="gen9randombattle",
    )

    second_account_config = AccountConfiguration("Max", None)
    second_player = MaxBasePowerPlayer(
        account_configuration=second_account_config,
        # team=uber_team,
        # battle_format="gen9ubers",
        battle_format="gen9randombattle",
    )

    third_account_config = AccountConfiguration("SimpleHeuristics", None)
    third_player = SimpleHeuristicsPlayer(
        account_configuration=third_account_config,
        # team=uber_team,
        # battle_format="gen9ubers",
        battle_format="gen9randombattle",
    )

    players = [first_player, second_player, third_player]

    cross_evaluation = await cross_evaluate(players, n_challenges=100)

    print("Cross Evaluation Results:")
    print(cross_evaluation)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
