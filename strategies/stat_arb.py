import numpy as np
from collections import deque

from strategies import StrategyPair
from models import *
from utils import *

class StatArb(StrategyPair):
    def __init__(self, pair, ema_window=5, z_threshold=2.0, start_time=(15, 00), end_time=(20, 00), latency_ms=500,
                 stop_loss=0.0001, take_profit=0.00001, pnl_target=0.01, pnl_loss=-0.01, trade_max=400):
        super().__init__(pair, start_time, end_time, latency_ms, 
                         stop_loss, take_profit, 
                         pnl_target, pnl_loss, trade_max)
        self.ema_window = ema_window
        self.z_threshold = z_threshold

        self.ema1 = None
        self.ema2 = None
        
        self.rolling_spread = deque(maxlen=600)
    
    def generate_signal(self, row, symbol):
        self.update(row, symbol)
        self.save_data(symbol) # temp

        if self.risk_manager._day_pause: 
            return None
        if not self.trade_window() and not self.s1["direction"]:
            return None

        signal = None
        if self.activated:
            latency_check = self.s1["latency"] < self.latency_ms and self.s2["latency"] < self.latency_ms
            if self.received and latency_check and self.ticks > 10:
                self.compute_indicators()
                if self.s1["direction"]:
                    signal = self.exit_trade()
                else:
                    signal = self.enter_trade()

        return signal
   
    def enter_trade(self, signal=None):
        if self.bid_ask_spread1 > 0.03 or self.bid_ask_spread2 > 0.03:
            return signal
        if self.z_score < -self.z_threshold:
            self.features = [self.z_score, self.ticks, self.s1["latency"], self.s2["latency"]]
            signal = self.buy_pair()
        elif self.z_score > self.z_threshold:
            self.features = [self.z_score, self.ticks, self.s1["latency"], self.s2["latency"]]
            signal = self.sell_pair()
        return signal
        
    def exit_trade(self, signal=None):
        if self.bid_ask_spread1 > 0.03 or self.bid_ask_spread2 > 0.03: # or bid/ask in a profitable location
            return signal
        if self.s1["direction"] == 1 and self.z_score >= 0:
            self.features = [self.z_score, self.ticks, self.s1["latency"], self.s2["latency"]]
            return self.exit()
        elif self.s1["direction"] == -1 and self.z_score <= 0:
            self.features = [self.z_score, self.ticks, self.s1["latency"], self.s2["latency"]]
            return self.exit()
        return signal
        
    def compute_indicators(self, ms=500):
        self.mid1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        self.mid2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        # self.ema1 = self.compute_ema(self.ema1, self.mid1, self.ema_window)
        # self.ema2 = self.compute_ema(self.ema2, self.mid2, self.ema_window)

        self.spread = self.mid1 - self.mid2
        self.rolling_spread.append(self.spread)
        self.z_score = (self.spread - np.mean(self.rolling_spread)) / np.std(self.rolling_spread, ddof=1)

        self.bid_ask_spread1 = abs(self.s1["ask"] - self.s1["bid"])
        self.bid_ask_spread2 = abs(self.s2["ask"] - self.s2["bid"])