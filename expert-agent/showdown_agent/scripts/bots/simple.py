from poke_env import SimpleHeuristicsPlayer


class CustomAgent(SimpleHeuristicsPlayer):
    def __init__(self, team, *args, **kwargs):
        super().__init__(team=team, *args, **kwargs)
