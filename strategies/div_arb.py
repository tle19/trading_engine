import numpy as np
from collections import deque

from strategies import StrategyPair
from models import *
from utils import *

class DivArb(StrategyPair):
    def __init__(self, pair, ema_window=5, decay_start=1000, decay_end=2000, start_time=(16, 00), end_time=(20, 00),
                 stop_loss=0.0001, take_profit=0.00001, pnl_target=0.01, pnl_loss=-0.01, trade_max=400):
        super().__init__(pair, start_time, end_time, 
                         stop_loss, take_profit, 
                         pnl_target, pnl_loss, trade_max)
        self.ema_window = ema_window
        self.decay_start = decay_start
        self.decay_end = decay_end

        self.ema1 = None
        self.ema2 = None
        
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

        self.save_data(symbol)
        return signal
    
    def enter_trade(self, signal=None):
        if self.mid1 < self.ema1 and self.mid2 > self.ema2:
            signal = self.buy_pair()
        elif self.mid1 > self.ema1 and self.mid2 < self.ema2:
            signal = self.sell_pair()
        return signal
        
    def exit_trade(self, signal=None):
        exit1 = self.s1["bid"] if self.s1["direction"] > 0 else self.s1["ask"]
        exit2 = self.s2["bid"] if self.s2["direction"] > 0 else self.s2["ask"]
        pnl1 = self.s1["direction"] * (exit1 - self.s1["entry_price"]) * self.s1["shares"]
        pnl2 = self.s2["direction"] * (exit2 - self.s2["entry_price"]) * self.s2["shares"]

        position_value = (self.s1["shares"] * self.s1["entry_price"]) + (self.s2["shares"] * self.s2["entry_price"])
        pnl_pct = (pnl1 + pnl2) / position_value

        if pnl_pct >= self.take_profit:
            return self.exit()
        if pnl_pct <= -self.stop_loss:
            return self.exit()

        # time decay
        if self.ticks >= self.decay_end:
            return self.exit()
        if self.ticks > self.decay_start:
            decay_factor = 1 - ((self.ticks - self.decay_start) / (self.decay_end - self.decay_start))
            if pnl_pct >= self.take_profit * decay_factor:
                return self.exit()

        return signal
        
    def compute_indicators(self, symbol):
        if self.symbol1 == symbol:
            self.mid1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
            self.ema1 = self.compute_ema(self.ema1, self.mid1, self.ema_window)
        elif self.symbol2 == symbol:
            self.mid2 = (self.s2["bid"] + self.s2["ask"]) * 0.5
            self.ema2 = self.compute_ema(self.ema2, self.mid2, self.ema_window)
        
        bid_ask_spread1 = abs(self.s1["ask"] - self.s1["bid"])
        bid_ask_spread2 = abs(self.s2["ask"] - self.s2["bid"])
        self.spread_check = bid_ask_spread1 < 0.05 and bid_ask_spread2 < 0.05