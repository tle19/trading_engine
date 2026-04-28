import numpy as np
from collections import deque

from strategies import StrategyPair

class TLS(StrategyPair):
    def __init__(self, pair, price_window=10000, spread_window=1500, 
                 entry_threshold=2.0, exit_threshold=0.0, bid_ask_spread=0.03,
                 start_time=(10, 00), end_time=(15, 00), quote_delta_ms=500, max_latency_ms=500, 
                 position_size=0.10, stop_loss=-0.0075, take_profit=0.00005, 
                 pnl_target=0.005, pnl_loss=-0.005, trade_max=1000):
        super().__init__(pair, start_time, end_time, quote_delta_ms, max_latency_ms,
                         position_size, stop_loss, take_profit, 
                         pnl_target, pnl_loss, trade_max)
        self.price_window = price_window
        self.spread_window = spread_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.bid_ask_spread = bid_ask_spread
        self.config()

        self.hedge_ratio = None
        self.hr_z = 0
        self.z_score = 0
        self.spread_mean = 0
        self.spread_std = 1
        self.spread_check = False

        self.hr = deque(maxlen=self.price_window)
        self.mid1_history = deque(maxlen=self.price_window)
        self.mid2_history = deque(maxlen=self.price_window)
        self.spread_history = deque(maxlen=self.spread_window)
    
    def generate_signal(self, row, symbol):
        self.update(row, symbol)
        self.reset_history()

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

        if self.z_score < -self.entry_threshold and self.hedge_ratio > 0 and abs(self.hr_z) < 2:
            signal = self.buy_pair()
        elif self.z_score > self.entry_threshold and self.hedge_ratio > 0 and abs(self.hr_z) < 2:
            signal = self.sell_pair()

        if self.position_manager.in_trade():
            self.features = {
                "hedge_ratio": self.hedge_ratio,
                "hr_z": self.hr_z,
                "z_score": self.z_score,
                "spread_mean": self.spread_mean,
                "spread_std": self.spread_std,
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
        elif direction and self.force_close:
            return self.exit()
        return signal

    def compute_indicators(self):
        self.mid1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        self.mid2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        self.mid1_history.append(self.mid1)
        self.mid2_history.append(self.mid2)

        x = np.array(self.mid2_history)
        y = np.array(self.mid1_history)
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        x_c = x - x_mean
        y_c = y - y_mean
        Sxx = np.sum(x_c * x_c)
        Syy = np.sum(y_c * y_c)
        Sxy = np.sum(x_c * y_c)
        denom = (2 * Sxy)
        if denom == 0:
            self.hedge_ratio = getattr(self, "hedge_ratio", 1.0)
        else:
            self.hedge_ratio = (Syy - Sxx + np.sqrt((Syy - Sxx)**2 + 4 * Sxy**2)) / denom
        intercept = y_mean - self.hedge_ratio * x_mean

        self.hr.append(self.hedge_ratio)
        if min(self.hr) != max(self.hr):
            hr = np.array(self.hr)
            hr_mean = np.mean(hr)
            hr_std = np.std(hr, ddof=1)
            if hr_std != 0:
                self.hr_z = (self.hedge_ratio - hr_mean) / hr_std  

        spread = self.mid1 - (intercept + self.hedge_ratio * self.mid2)
        self.spread_history.append(spread)
        # self.save_data(max(self.s1["ts"], self.s2["ts"]), spread)
        if len(self.spread_history) == self.spread_window:
            s = np.array(self.spread_history)
            self.spread_mean = np.mean(s)
            self.spread_std = np.std(s, ddof=1)
            self.z_score = (spread - self.spread_mean) / self.spread_std
            # self.save_data(max(self.s1["ts"], self.s2["ts"]), self.z_score)

        self.spread_check = (self.s1["ask"] - self.s1["bid"] <= self.bid_ask_spread and 
                            self.s2["ask"] - self.s2["bid"] <= self.bid_ask_spread)
        
    def reset_history(self, reset_time=(9, 30)):
        if self.trade_window(reset_time, reset_time):
            self.mid1_history.clear()
            self.mid2_history.clear()
            self.spread_history.clear()
    
    def config(self):
        if self.pair == "IVV-IWM":
            self.price_window = 10000
            self.spread_window = 1500
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.10
        if self.pair == "GLD-SLV":
            self.price_window = 10000
            self.spread_window = 1500
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.05
            self.position_size = 0.10
        if self.pair == "IAU-SIVR":
            self.price_window = 10000
            self.spread_window = 1500
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.10
        if self.pair == "USO-BNO":
            self.price_window = 10000
            self.spread_window = 1500
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.10
        if self.pair == "VT-VXUS":
            self.price_window = 10000
            self.spread_window = 1500
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.10

    def param_grid(self):
        params = {
            "price_window": [10000], # 5000, 10000, 15000, 20000
            "spread_window": [1000, 1500, 2000, 2500, 3000]
        }
        return params