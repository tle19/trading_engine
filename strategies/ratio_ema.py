import numpy as np
from collections import deque

from strategies import StrategyPair
from models import *
from utils import *

class RatioEMA(StrategyPair):
    def __init__(self, pair, ema_window=100, spread_window=1000, 
                 entry_threshold=2.0, exit_threshold=0.0, bid_ask_spread=0.03,
                 start_time=(15, 00), end_time=(19, 00), quote_delta_ms=1000, max_latency_ms=500, 
                 position_size=0.10, stop_loss=-0.005, take_profit=0.001, 
                 pnl_target=0.005, pnl_loss=-0.005, trade_max=800):
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
        self.z_score = 0.0
        self.spread_check = False

        self.rolling_spread = deque(maxlen=self.spread_window)

        self.history = []
        self.saved = False
    
    def generate_signal(self, row, symbol):
        self.update(row, symbol)

        if self.risk_manager._day_pause: 
            return None
        if not self.trade_window() and not self.position_manager.in_trade():
            return None

        signal = None
        if self.activated:
            self.compute_indicators()
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
        elif direction and self.compute_position_value() < self.stop_loss:
            return self.exit()
        # elif direction and self.compute_position_value() > self.take_profit:
        #     return self.exit()
        return signal
        
    def compute_indicators(self):
        self.mid1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        self.mid2 = (self.s2["bid"] + self.s2["ask"]) * 0.5
        
        if not self.position_manager.in_trade():
            hedge_ratio = round(self.mid1 / self.mid2, 3)
            self.hedge_ratio = self.compute_ema(self.hedge_ratio, hedge_ratio, self.ema_window)

        spread = self.mid1 - (self.hedge_ratio * self.mid2)
        self.rolling_spread.append(spread)
        self.save_data(spread)
        if len(self.rolling_spread) == self.spread_window:
            self.z_score = (spread - np.mean(self.rolling_spread)) / np.std(self.rolling_spread, ddof=1)

        self.spread_check = self.s1["ask"] - self.s1["bid"] < self.bid_ask_spread and self.s2["ask"] - self.s2["bid"] < self.bid_ask_spread
    
    def config(self):
        if self.pair == "SPY-QQQ":
            self.ema_window = 100
            self.spread_window = 1000
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.10
        if self.pair == "GLD-SLV":
            self.ema_window = 100
            self.spread_window = 1000
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.05
            self.position_size = 0.10
        if self.pair == "VOO-SCHX":
            self.ema_window = 100
            self.spread_window = 1000
            self.entry_threshold = 2.0
            self.exit_threshold = 2.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.20
        if self.pair == "IVV-IWM":
            self.ema_window = 100
            self.spread_window = 1000
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.10

    def save_data(self, spread):
        if not self.saved:
            self.history.append(spread)
            end_time = ((18, 55)[0] * 3600 + (18, 55)[1] * 60) * 1000
            if self.s1["ts"] % (24 * 3600 * 1000) > end_time:
                with open(f"{self.pair}_spread.json", "w") as f:
                    json.dump(self.history, f, indent=2)
                self.saved = True

    def param_grid(self):
        params = {
            "ema_window": [10, 20, 30, 40, 50, 75, 100, 200], # 10, 20, 30, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000
            "spread_window": [500, 1000, 1500, 2000] # 500, 1000, 1500, 2000
        }
        return params