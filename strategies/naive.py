import numpy as np
from collections import deque

from strategies import StrategyPair

import json

class Naive(StrategyPair):
    def __init__(self, pair, ema_window=100, spread_window=1000, 
                 entry_threshold=2.0, exit_threshold=0.0, bid_ask_spread=0.03,
                 start_time=(10, 00), end_time=(15, 00), quote_delta_ms=500, max_latency_ms=500, 
                 position_size=0.10, stop_loss=-0.005, take_profit=0.00005, 
                 pnl_target=0.005, pnl_loss=-0.005, trade_max=1000):
        super().__init__(pair, start_time, end_time, quote_delta_ms, max_latency_ms,
                         position_size, stop_loss, take_profit, 
                         pnl_target, pnl_loss, trade_max)
        self.ema_window = ema_window
        self.spread_window = spread_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.bid_ask_spread = bid_ask_spread
        self.config()

        self.hedge_ratio = None
        self.hedge_ratio_live = None
        self.z_score = 0
        self.spread_mean = 0
        self.spread_std = 1
        self.spread_check = False

        # self.file = open(f"{self.pair}_hedge_ratios.jsonl", "ab")

        self.spread_history = deque(maxlen=self.spread_window)
    
    def generate_signal(self, row, symbol):
        self.update(row, symbol)
        self.reset_history()
        
        # self.file.write(json.dumps({"ts": self.s1["ts"], "hedge_ratio": self.hedge_ratio}).encode() + b"\n")

        if self.risk_manager._day_pause: 
            return None

        signal = None
        if self.activated and self.sync_check:
            self.compute_indicators()
            if self.latency_check and self.spread_check:
                signal = self.exit_trade()
                if signal is None:
                    signal = self.enter_trade()
        return signal
   
    def enter_trade(self, signal=None):
        if not self.trade_window() and not self.position_manager.in_trade():
            return None

        if self.z_score < -self.entry_threshold:
            signal = self.buy_pair()
        elif self.z_score > self.entry_threshold:
            signal = self.sell_pair()
        
        if self.position_manager.in_trade():
            self.features = {
                "z_score": self.z_score,
                "spread_mean": self.spread_mean,
                "spread_std": self.spread_std,
                "spread_dist": abs(self.spread_history[-1] - self.spread_mean),
                "latency": self.latency,
                "time_diff": abs(self.s1["ts"] - self.s2["ts"]).total_seconds() * 1000,
            }

        return signal
        
    def exit_trade(self, signal=None):
        direction = self.position_manager.direction()
        if direction == 1 and self.z_score >= self.exit_threshold:
            return self.exit()
        elif direction == -1 and self.z_score <= -self.exit_threshold:
            return self.exit()
        elif direction and self.compute_position_value() < self.stop_loss:
            return self.exit()
        # elif direction and self.compute_position_value() > self.take_profit:
        #     return self.exit()
        elif direction and self.features:
            anchored_z = (self.spread_history[-1] - self.features["spread_mean"]) / self.features["spread_std"]
            if abs(anchored_z) > 8.0:
                return self.exit()
        elif direction and self.force_close:
            return self.exit()
        return signal

    def compute_indicators(self):
        self.mid1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        self.mid2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        hedge_ratio = round(self.mid1 / self.mid2, 3)
        self.hedge_ratio_live = self.compute_ema(self.hedge_ratio_live, hedge_ratio, self.ema_window)
        if not self.position_manager.in_trade():
            self.hedge_ratio = self.hedge_ratio_live

        spread = self.mid1 - (self.hedge_ratio * self.mid2)
        self.spread_history.append(spread)
        # self.save_data(self.s1["ts"] if self.s1["ts"] > self.s2["ts"] else self.s2["ts"], spread)
        if len(self.spread_history) == self.spread_window:
            s = np.array(self.spread_history)
            self.spread_mean = np.mean(s)
            self.spread_std = np.std(s, ddof=1)
            self.z_score = (spread - self.spread_mean) / self.spread_std

        self.spread_check = (self.s1["ask"] - self.s1["bid"] <= self.bid_ask_spread and 
                            self.s2["ask"] - self.s2["bid"] < self.bid_ask_spread)
        
    def reset_history(self, reset_time=(9, 30)):
        if self.trade_window(reset_time, reset_time):
            self.spread_history.clear()

    def config(self):
        if self.pair == "SPY-QQQ":
            self.ema_window = 100
            self.spread_window = 1000
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.10
        if self.pair == "IVV-IWM":
            self.ema_window = 100
            self.spread_window = 1000
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.10
        if self.pair == "GLD-SLV":
            self.ema_window = 100
            self.spread_window = 1500
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.05
            self.position_size = 0.10

    def param_grid(self):
        params = {
            "ema_window": [25, 50, 75, 100, 200, 500], 
            "spread_window": [500, 1000, 1500, 2000]
        }
        return params