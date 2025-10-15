from poke_env import RandomPlayer


class CustomAgent(RandomPlayer):
    def __init__(self, team, *args, **kwargs):
        super().__init__(team=team, *args, **kwargs)
