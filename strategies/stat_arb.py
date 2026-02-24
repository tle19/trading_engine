import numpy as np
from collections import deque

from strategies import StrategyPair
from models import *
from utils import *

class StatArb(StrategyPair):
    def __init__(self, pair, ema_window=1000, entry_threshold=1.75, exit_threshold=0.0, start_time=(16, 00), end_time=(20, 00),
                 stop_loss=0.0001, take_profit=0.00001, pnl_target=0.01, pnl_loss=-0.01, trade_max=400):
        super().__init__(pair, start_time, end_time, 
                         stop_loss, take_profit, 
                         pnl_target, pnl_loss, trade_max)
        self.ema_window = ema_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        if pair == "GOOG-GOOGL": # "SPY-VOO", "QQQ-QQQM"
            self.exit_threshold = 1.5
        if pair == "SPY-QQQ":
            self.exit_threshold = 0.5

        self.ema1 = None
        self.ema2 = None
        
        self.rolling_spread = deque(maxlen=1000)
    
    def generate_signal(self, row, symbol):
        self.update(row, symbol)
        self.save_data(symbol)

        if self.risk_manager._day_pause: 
            return None
        if not self.trade_window() and not self.s1["direction"]:
            return None

        signal = None
        if self.activated:
            self.compute_indicators()
            spread_check = self.bid_ask_spread1 < 0.05 or self.bid_ask_spread2 < 0.05
            if self.latency_check and spread_check:
                if self.s1["direction"]:
                    signal = self.exit_trade()
                else:
                    signal = self.enter_trade()
        return signal
   
    def enter_trade(self, signal=None):
        if self.z_score < -self.entry_threshold:
            self.features = [self.z_score, self.latency, abs(self.s1["ts"] - self.s2["ts"])]
            signal = self.buy_pair()
        elif self.z_score > self.entry_threshold:
            self.features = [self.z_score, self.latency, abs(self.s1["ts"] - self.s2["ts"])]
            signal = self.sell_pair()
        return signal
        
    def exit_trade(self, signal=None):
        if self.s1["direction"] == 1 and self.z_score >= self.exit_threshold:
            return self.exit()
        elif self.s1["direction"] == -1 and self.z_score <= -self.exit_threshold:
            return self.exit()
        return signal
        
    def compute_indicators(self):
        self.mid1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        self.mid2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        # self.ema1 = self.compute_ema(self.ema1, self.mid1, self.ema_window)
        # self.ema2 = self.compute_ema(self.ema2, self.mid2, self.ema_window)

        self.spread = self.mid1 - self.mid2
        self.rolling_spread.append(self.spread)
        self.z_score = (self.spread - np.mean(self.rolling_spread)) / np.std(self.rolling_spread, ddof=1)

        self.bid_ask_spread1 = abs(self.s1["ask"] - self.s1["bid"])
        self.bid_ask_spread2 = abs(self.s2["ask"] - self.s2["bid"])