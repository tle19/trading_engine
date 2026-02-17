import os
import pandas as pd

from strategies import StrategyBook
from models import *
from utils import *

class RecordBook(StrategyBook):
    def __init__(self, symbol, start_time=(14, 30), end_time=(20, 59)):
        super().__init__(symbol, start_time, end_time)
        
        self.saved = False
        self.history = []

    def generate_signal(self, row, symbol):
        self.update(symbol, row)
        
        self.history.append({
            "timestamp": self.ts,
            "bid_side": self.bid_side,
            "ask_side": self.ask_side
        })

        if not self.trade_window() and not self.saved:
            file_path = os.path.join("data", f"{self.symbol}_book.csv")

            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    existing_history = json.load(f)
            else:
                existing_history = []

            existing_history.extend(self.history)

            with open(file_path, "w") as f:
                json.dump(existing_history, f, indent=2)

            self.saved = True
        return None

