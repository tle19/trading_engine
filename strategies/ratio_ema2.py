import numpy as np
from collections import deque

from strategies import StrategyPair

class RatioEMA2(StrategyPair):
    def __init__(self, pair, price_window=10000, ema_window=100, spread_window=1000, 
                 entry_threshold=2.0, exit_threshold=0.0, bid_ask_spread=0.03,
                 start_time=(15, 00), end_time=(19, 00), quote_delta_ms=500, max_latency_ms=500, 
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

        self.spread = None
        self.z_score = 0
        self.spread_mean = 0
        self.spread_std = 1
        self.spread_check = False

        self.mid1_history = deque(maxlen=price_window)
        self.mid2_history = deque(maxlen=price_window)
        self.spread_history = deque(maxlen=self.spread_window)
    
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
        if not self.position_manager.in_trade():
            self.features = {
                "z_score": self.z_score,
                "spread_mean": self.spread_mean,
                "spread_std": self.spread_std,
                "latency": self.latency,
                "time_diff": abs(self.s1["ts"] - self.s2["ts"]),
            }
        
        if self.z_score < -self.entry_threshold:
            signal = self.sell_pair()
        elif self.z_score > self.entry_threshold:
            signal = self.buy_pair()

        return signal
        
    def exit_trade(self, signal=None):
        direction = self.position_manager.direction()
        if direction == 1 and self.z_score <= self.entry_threshold:
            return self.exit()
        elif direction == -1 and self.z_score >= -self.entry_threshold:
            return self.exit()
        elif direction and self.compute_position_value() < self.stop_loss:
            return self.exit()
        return signal

    def compute_indicators(self):
        self.mid1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        self.mid2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        self.mid1_history.append(self.mid1)
        self.mid2_history.append(self.mid2)

        if len(self.spread_history) < 10:
            hedge_ratio, intercept = self.mid1 / self.mid2, 0
        else:
            x = np.array(self.mid2_history)
            y = np.array(self.mid1_history)
            x_mean = np.mean(x)
            y_mean = np.mean(y)
            hedge_ratio = np.sum((x - x_mean)*(y - y_mean)) / np.sum((x - x_mean)**2)
            intercept = y_mean - hedge_ratio * x_mean

        spread = self.mid1 - (hedge_ratio * self.mid2)
        self.spread_history.append(spread)
        # self.save_data(self.s1["ts"], spread)
        if len(self.spread_history) == self.spread_window:
            self.spread_mean = np.mean(self.spread_history)
            self.spread_std = np.std(self.spread_history, ddof=1)
            self.z_score = (spread - self.spread_mean) / self.spread_std

        self.spread_check = (self.s1["ask"] - self.s1["bid"] < self.bid_ask_spread and 
                    self.s2["ask"] - self.s2["bid"] < self.bid_ask_spread)
    
    def config(self):
        if self.pair == "SPY-QQQ":
            self.ema_window = 100
            self.spread_window = 1000
            self.entry_threshold = 2
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 1.0
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