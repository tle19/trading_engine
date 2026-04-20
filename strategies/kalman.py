import numpy as np
from collections import deque

from strategies import StrategyPair

class KalmanFilter(StrategyPair):
    def __init__(self, pair, q=1e-5, r=1e-2, spread_window=1000, 
                 entry_threshold=2.0, exit_threshold=0.0, bid_ask_spread=0.03,
                 start_time=(15, 00), end_time=(19, 00), quote_delta_ms=500, max_latency_ms=500, 
                 position_size=0.10, stop_loss=-0.0075, take_profit=0.00005, 
                 pnl_target=0.005, pnl_loss=-0.005, trade_max=1000):
        super().__init__(pair, start_time, end_time, quote_delta_ms, max_latency_ms,
                         position_size, stop_loss, take_profit, 
                         pnl_target, pnl_loss, trade_max)
        self.Q = q
        self.R = r
        self.spread_window = spread_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.bid_ask_spread = bid_ask_spread
        self.config()

        self.hedge_ratio = 1.0
        self.P = 1.0
        self.mid1 = 1.0
        self.mid2 = 1.0
        self.prev_mid1 = 1.0
        self.prev_mid2 = 1.0
        
        self.z_score = 0
        self.spread_mean = 0
        self.spread_std = 1
        self.spread_check = False

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

        if self.z_score < -self.entry_threshold:
            signal = self.buy_pair()
        elif self.z_score > self.entry_threshold:
            signal = self.sell_pair()

        if self.position_manager.in_trade():
            self.features = {
                "hedge_ratio": self.hedge_ratio,
                "z_score": self.z_score,
                "spread_mean": self.spread_mean,
                "spread_std": self.spread_std,
                "latency": self.latency,
                "time_diff": abs(self.s1["ts"] - self.s2["ts"]),
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
        self.prev_mid1 = self.mid1
        self.prev_mid2 = self.mid2
        
        self.mid1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        self.mid2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        x = np.log(self.mid2 / self.prev_mid2)
        y = np.log(self.mid1 / self.prev_mid1)

        P_pred = self.P + self.Q
        k = (P_pred * x) / (x * P_pred * x + self.R)
        self.hedge_ratio += k * (y - self.hedge_ratio * x)
        self.P = (1 - k * x) * P_pred
        
        spread = self.mid1 - (self.hedge_ratio * self.mid2)
        self.spread_history.append(spread)
        self.save_data(self.s1["ts"] if self.s1["ts"] > self.s2["ts"] else self.s2["ts"], spread)
        if len(self.spread_history) == self.spread_window:
            s = np.array(self.spread_history)
            self.spread_mean = np.mean(s)
            self.spread_std = np.std(s, ddof=1)
            self.z_score = (spread - self.spread_mean) / self.spread_std

        self.spread_check = (self.s1["ask"] - self.s1["bid"] <= self.bid_ask_spread and 
                            self.s2["ask"] - self.s2["bid"] <= self.bid_ask_spread)
        
    def reset_history(self, reset_time=(13, 31)):
        ts = self.s1["ts"] or self.s2["ts"]
        start_time = (reset_time[0] * 3600 + reset_time[1] * 60) * 1000
        if ts % (24 * 3600 * 1000) < start_time:
            self.spread_history.clear()

    def compute_share_split(self):
        cash = self.risk_manager.curr_cash
        price1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        price2 = (self.s2["bid"] + self.s2["ask"]) * 0.5
        
        lower = self.beta_mean - self.beta_std*2
        upper = self.beta_mean + self.beta_std*2
        beta = np.clip(self.hedge_ratio, lower, upper)

        denom = price1 + beta * price2
        if denom <= 0:
            shares1 = max(1, int(cash / 2 // price1))
            shares2 = max(1, int(cash / 2 // price2))

        shares1 = max(1, int(cash // denom))
        shares2 = max(1, int(beta * shares1))

        return shares1, shares2
    
    def config(self):
        if self.pair == "SPY-QQQ":
            self.spread_window = 1000
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.20
        if self.pair == "IVV-IWM":
            self.spread_window = 1500
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.10
        if self.pair == "GLD-SLV":
            self.spread_window = 1500
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.05
            self.position_size = 0.10
        if self.pair == "IAU-SIVR":
            self.spread_window = 1500
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.10
        if self.pair == "USO-BNO":
            self.spread_window = 1500
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.10
        if self.pair == "VT-VXUS":
            self.spread_window = 1500
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.03
            self.position_size = 0.10

    def param_grid(self):
        params = {
            "q": [1e-6, 3e-6, 1e-5, 3e-5, 1e-4, 3e-4, 1e-3],
            "r": [1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2],
            "spread_window": [1000, 1500, 2000, 2500, 3000]
        }
        return params