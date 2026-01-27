import numpy as np

from .risk import RiskManager
from utils import *

LONG = 1
SHORT = -1
EXIT = 0
HOLD = None
TICKS = 23500

class PairStrategy:
    def __init__(self, pair, stop_loss=0.01, take_profit=0.01, position_size=1.0,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=200):
        self.pair = pair
        self.symbol1, self.symbol2 = pair.split("-")
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.position_size = position_size

        self.data = {
            self.symbol1: {
                "ts": None,
                "bid": None,
                "ask": None,
                "last": None,
                "bid_size": None,
                "ask_size": None,
                "prices": np.empty(TICKS, dtype=float),
                "bids": np.empty(TICKS, dtype=float),
                "asks": np.empty(TICKS, dtype=float),
                "lasts": np.empty(TICKS, dtype=float),
                "bid_sizes": np.empty(TICKS, dtype=float),
                "ask_sizes": np.empty(TICKS, dtype=float),
                "index": 0,
                "direction": 0,
                "shares": 0,
                "position_size": 1.0,
                "entry_price": None,
                "stop_price": None,
                "target_price": None
            },
            self.symbol2: {
                "ts": None,
                "bid": None,
                "ask": None,
                "last": None,
                "bid_size": None,
                "ask_size": None,
                "prices": np.empty(TICKS, dtype=float),
                "bids": np.empty(TICKS, dtype=float),
                "asks": np.empty(TICKS, dtype=float),
                "lasts": np.empty(TICKS, dtype=float),
                "bid_sizes": np.empty(TICKS, dtype=float),
                "ask_sizes": np.empty(TICKS, dtype=float),
                "index": 0,
                "direction": 0,
                "shares": 0,
                "position_size": 1.0,
                "entry_price": None,
                "stop_price": None,
                "target_price": None
            }
        }

        self.risk_manager = RiskManager(pnl_target=pnl_target, pnl_loss=pnl_loss, trade_max=trade_max)
        self.cash = self.risk_manager.curr_cash / 2

    def generate_signal(self):
        raise NotImplementedError
    
    def enter_trade(self):
        raise NotImplementedError
    
    def exit_trade(self):
        return self.exit()
    
    def compute_indicators(self):
        raise NotImplementedError
    
    def pairmate(self, symbol):
        if symbol == self.symbol1:
            return self.symbol2
        elif symbol == self.symbol2:
            return self.symbol1
    
    def update(self, symbol, row=None): 
        s = self.data[symbol]
        idx = s["index"]

        if row is not None:
            s["ts"] = row.timestamp
            for attr in ("bid", "ask", "last", "bid_size", "ask_size"):
                val = getattr(row, attr)
                if val is not None:
                    s[attr] = val

        s["price"] = (s["bid"] + s["ask"] + s["last"]) / 3
        s["prices"][idx] = s["price"]
        s["bids"][idx] = s["bid"]
        s["asks"][idx] = s["ask"]
        s["lasts"][idx] = s["last"]
        s["bid_sizes"][idx] = s["bid_size"]
        s["ask_sizes"][idx] = s["ask_size"]

        s["index"] += 1

    def trade_window(self, start, end):
        ts = self.data[self.symbol1]["ts"]
        return start <= (ts.hour, ts.minute) <= end
    
    def buy_pair(self):
        s1, s2 = self.data[self.symbol1], self.data[self.symbol2]
        if s1["direction"] == 0:
            shares1 = int(self.cash / s1["price"])
            shares2 = int(self.cash / s2["price"])
            s1["direction"], s1["shares"] = 1, shares1
            s2["direction"], s2["shares"] = -1, shares2
            return LONG
        return HOLD
        
    def sell_pair(self):
        s1, s2 = self.data[self.symbol1], self.data[self.symbol2]
        if s1["direction"] == 0:
            shares1 = int(self.cash / s1["price"])
            shares2 = int(self.cash / s2["price"])
            s1["direction"], s1["shares"] = -1, shares1
            s2["direction"], s2["shares"] = 1, shares2
            return SHORT
        return HOLD
          
    def exit(self):
        if self.data[self.symbol1]["direction"]:
            return EXIT
        return HOLD
 
    def compute_ma(self, data, window=10):
        return np.mean(data[-window:])
    
    def compute_ema(self, prev_ema, new_value, window=10):
        if prev_ema is None:
            return new_value
        alpha = 2.0 / (window + 1.0)
        return alpha * new_value + (1.0 - alpha) * prev_ema