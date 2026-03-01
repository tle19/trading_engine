import numpy as np
from collections import deque

from strategies import StrategyPair
from models import *
from utils import *

class StatArb(StrategyPair):
    def __init__(self, pair, ema_window=1000, entry_threshold=2.0, exit_threshold=0.0, bid_ask_spread=0.05, 
                 start_time=(16, 00), end_time=(20, 00),
                 stop_loss=0.0001, take_profit=0.0001, pnl_target=0.01, pnl_loss=-0.005, trade_max=200):
        super().__init__(pair, start_time, end_time, 
                         stop_loss, take_profit, 
                         pnl_target, pnl_loss, trade_max)
        self.ema_window = ema_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.bid_ask_spread = bid_ask_spread

        self.pair_preset(pair)

        self.ema1 = None
        self.ema2 = None
        self.z_score = 0.0
        self.slope_diff = 0.0
        self.spread_check = False
        
        self.rolling_ema1 = deque(maxlen=ema_window)
        self.rolling_ema2 = deque(maxlen=ema_window)
        self.rolling_spread = deque(maxlen=ema_window)
    
    def generate_signal(self, row, symbol):
        self.update(row, symbol)

        if self.risk_manager._day_pause: 
            return None
        if not self.trade_window() and not self.s1["direction"]:
            return None

        signal = None
        if self.activated:
            self.compute_indicators(symbol)
            if self.latency_check and self.spread_check:
                if self.s1["direction"]:
                    signal = self.exit_trade()
                else:
                    signal = self.enter_trade()
        return signal
   
    def enter_trade(self, signal=None):
        if self.z_score < -self.entry_threshold:
            signal = self.buy_pair()
        elif self.z_score > self.entry_threshold:
            signal = self.sell_pair()

        # TEST MIN SHARES
        if self.pair == "GOOG-GOOGL":
            self.s1["shares"] = 1
            self.s2["shares"] = 1
        if self.pair == "SPY-QQQ":
            self.s1["shares"] = 7
            self.s2["shares"] = 8
        if self.pair == "V-MA":
            self.s1["shares"] = 5
            self.s2["shares"] = 3
        if self.pair == "KO-PEP":
            self.s1["shares"] = 6
            self.s2["shares"] = 3
        if self.pair == "HD-LOW":
            self.s1["shares"] = 2
            self.s2["shares"] = 3
        if self.pair == "XOM-CVX":
            self.s1["shares"] = 5
            self.s2["shares"] = 4
        if self.pair == "GS-MS":
            self.s1["shares"] = 1
            self.s2["shares"] = 5
            
        self.features = [self.z_score, self.slope_diff, self.latency, abs(self.s1["ts"] - self.s2["ts"])]
        return signal
        
    def exit_trade(self, signal=None):
        if self.s1["direction"] == 1 and self.z_score >= self.exit_threshold:
            return self.exit()
        elif self.s1["direction"] == -1 and self.z_score <= -self.exit_threshold:
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

        if len(self.rolling_ema1) == self.ema_window and len(self.rolling_ema2) == self.ema_window:
            slope1 = self.ema1 - self.rolling_ema1[0]
            slope2 = self.ema2 - self.rolling_ema2[0]
            norm_slope1 = slope1 / np.std(self.rolling_ema1, ddof=1)
            norm_slope2 = slope2 / np.std(self.rolling_ema2, ddof=1)
            self.slope_diff = norm_slope1 - norm_slope2

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
        if pair == "GOOG-GOOGL":
            self.entry_threshold = 2.0
            self.exit_threshold = 2.0
            self.bid_ask_spread = 0.03
        if self.pair == "HD-LOW":
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.25
        if self.pair == "KO-PEP":
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.10
        if self.pair == "V-MA":
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.25
        if self.pair == "XOM-CVX":
            self.entry_threshold = 2.0
            self.exit_threshold = 0.0
            self.bid_ask_spread = 0.05