from strategies import StrategyPair

class RecordQuote(StrategyPair):
    def __init__(self, pair):
        super().__init__(pair)

    def generate_signal(self, row, symbol):
        return None

