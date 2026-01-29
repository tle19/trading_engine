import numpy as np

from strategies import StrategyPair
from models import *
from utils import *

class SpreadDiff(StrategyPair):
    def __init__(self, pair, ema_window=20, start_time=(15, 00), end_time=(20, 00),
                 take_profit=0.001, pnl_target=0.01, pnl_loss=-0.01, trade_max=200):
        super().__init__(pair, start_time, end_time, take_profit, 
                         pnl_target, pnl_loss, trade_max)
        self.ema_window = ema_window

        self.ema1 = None
        self.ema2 = None
    
    def generate_signal(self, row, symbol):
        self.update(symbol, row)

        if self.risk_manager._day_pause: 
            return None
        if not self.trade_window() and not self.s1["direction"]:
            return None

        signal = None
        if self.activated:
            self.compute_indicators()
            if self.s1["direction"]:
                signal = self.exit_trade()
            else:
                signal = self.enter_trade()
        return signal
    
    def enter_trade(self):
        signal = None

        spread1 = (self.s1["ask"] - self.s1["bid"])
        spread2 = (self.s2["ask"] - self.s2["bid"])

        if spread1 > 0.05 and spread2 > 0.05:
            return
        # s1 price > s2 price

        # if s1["bid"] < self.ema_fast1 and s2["price"] > self.ema_fast2:
        #     signal = self.buy_pair()
        # if s1["price"] > self.ema_fast1 and s2["price"] < self.ema_fast2:
        #     signal = self.sell_pair()
        return signal
        
    def exit_trade(self):
        direction = self.s1["direction"]
        # compute pnls
        if direction == 1 and self.ema1 < 5000:
            return self.exit()
        if direction == -1 and self.ema2 > 5000:
            return self.exit()
        
    def compute_indicators(self):
        mid1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        mid2 = (self.s2["bid"] + self.s2["ask"]) * 0.5
        spread = mid1 - mid2

        self.ema1 = self.compute_ema(self.ema1, mid1, self.ema_window)
        self.ema2 = self.compute_ema(self.ema2, mid2, self.ema_window)

        # calculate target_prices for a given bid-ask for both, 
        # look for positive difference, 