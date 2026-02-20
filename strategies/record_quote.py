from strategies import StrategyPair
from utils import *

class RecordQuote(StrategyPair):
    def __init__(self, symbol, start_time=(14, 30), end_time=(20, 59)):
        super().__init__(symbol, start_time, end_time)

    def generate_signal(self, row, _=None):
        self.update(row)
        self.save_data()
        return None

