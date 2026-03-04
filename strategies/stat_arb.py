import numpy as np
from collections import deque

from strategies import StrategyPair
from models import *
from utils import *

class StatArb(StrategyPair):
    def __init__(self, pair, ema_window=1000, entry_threshold=2.0, exit_threshold=0.0, bid_ask_spread=0.05, 
                 start_time=(15, 00), end_time=(20, 00), quote_delta_ms=1000, max_latency_ms=500, 
                 position_size=0.10, stop_loss=0.0001, take_profit=0.0001, 
                 pnl_target=0.01, pnl_loss=-0.0025, trade_max=400):
        super().__init__(pair, start_time, end_time, quote_delta_ms, max_latency_ms,
                         position_size, stop_loss, take_profit, 
                         pnl_target, pnl_loss, trade_max)
        self.ema_window = ema_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.bid_ask_spread = bid_ask_spread

        self.pair_preset(pair)

        self.ema1 = None
        self.ema2 = None
        self.z_score = 0.0
        self.spread_check = False
        
        self.rolling_ema1 = deque(maxlen=self.ema_window)
        self.rolling_ema2 = deque(maxlen=self.ema_window)
        self.rolling_spread = deque(maxlen=1000)
    
    def generate_signal(self, row, symbol):
        self.update(row, symbol)

        if self.risk_manager._day_pause: 
            return None
        if not self.trade_window() and not self.position_manager.in_trade():
            return None

        signal = None
        if self.activated:
            self.compute_indicators(symbol)
            if self.latency_check and self.spread_check:
                signal = self.exit_trade()
                if signal is None:
                    signal = self.enter_trade()
        return signal
   
    def enter_trade(self, signal=None):
        if self.z_score < -self.entry_threshold:
            signal = self.buy_pair()
        elif self.z_score > self.entry_threshold:
            signal = self.sell_pair()
            
        self.features = {
            "z_score": self.z_score,
            "latency": self.latency,
            "time_diff": abs(self.s1["ts"] - self.s2["ts"])
        }
        return signal
        
    def exit_trade(self, signal=None):
        direction = self.position_manager.direction()
        if direction == 1 and self.z_score >= self.exit_threshold:
            return self.exit()
        elif direction == -1 and self.z_score <= -self.exit_threshold:
            return self.exit()
        return signal
        
    def compute_indicators(self, symbol):
        self.mid1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        self.mid2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        if self.symbol1 == symbol:
            self.ema1 = self.compute_ema(self.ema1, self.mid1, self.ema_window)
            self.rolling_ema1.append(self.ema1)
        elif self.symbol2 == symbol:
            self.ema2 = self.compute_ema(self.ema2, self.mid2, self.ema_window)
            self.rolling_ema2.append(self.ema2)

        spread = self.mid1 - self.mid2
        self.rolling_spread.append(spread)
        if len(self.rolling_spread) == self.ema_window:
            self.z_score = (spread - np.mean(self.rolling_spread)) / np.std(self.rolling_spread, ddof=1)

        self.spread_check = abs(self.s1["ask"] - self.s1["bid"]) < self.bid_ask_spread and abs(self.s2["ask"] - self.s2["bid"]) < self.bid_ask_spread
    
    def pair_preset(self, pair):
        if self.pair == "SPY-QQQ":
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
        if self.pair == "GLD-SLV":
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.05
        if self.pair == "IBIT-ETHA":
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.05
        if self.pair == "XLE-VDE":
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.05
        if self.pair == "GOOG-GOOGL":
            self.entry_threshold = 2.25
            self.exit_threshold = 2.0
            self.bid_ask_spread = 0.04