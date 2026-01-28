import numpy as np

from strategies import PairStrategy
from models import *
from utils import *

class SpreadDiff(PairStrategy):
    def __init__(self, pair, ema_window=10, time_start=(15, 00), time_end=(20, 00),
                 take_profit=0.001, position_size=1.0,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=200):
        super().__init__(pair, time_start, time_end, 
                         take_profit, position_size,
                         pnl_target, pnl_loss, trade_max)
        self.ema_window = ema_window

        self.ema1 = None
        self.ema2 = None
    
    def generate_signal(self, symbol, row):
        self.update(symbol, row)

        if self.risk_manager._day_pause: 
            return None
        if not self.trade_window() and not self.data[self.symbol1]["direction"]:
            return None

        signal = None
        if self.activated:
            self.compute_indicators()
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade()
        return signal
    
    def enter_trade(self):
        signal = None

        s1, s2 = self.data[self.symbol1], self.data[self.symbol2]
        spread1 = (s1["ask"] - s1["bid"])
        spread2 = (s2["ask"] - s2["bid"])

        if spread1 > 0.05 and spread2 > 0.05:
            return
        # s1 price > s2 price

        # if s1["bid"] < self.ema_fast1 and s2["price"] > self.ema_fast2:
        #     signal = self.buy_pair()
        # if s1["price"] > self.ema_fast1 and s2["price"] < self.ema_fast2:
        #     signal = self.sell_pair()
        return signal
        
    def exit_trade(self):
        direction = self.data[self.symbol1]["direction"]
        # compute pnls
        if direction == 1 and self.ema_fast1 < self.ema_slow1:
            return self.exit()
        if direction == -1 and self.ema_fast2 > self.ema_slow2:
            return self.exit()
        
    def compute_indicators(self):
        s1, s2 = self.data[self.symbol1], self.data[self.symbol2]
        
        mid1 = (s1["bid"] + s1["ask"]) * 0.5
        mid2 = (s2["bid"] + s2["ask"]) * 0.5
        spread = mid1 - mid2

        self.ema1 = self.compute_ema(self.ema1, mid1, self.ema_window)
        self.ema2 = self.compute_ema(self.ema2, mid2, self.ema_window)

        # calculate target_prices for a given bid-ask for both, 
        # look for positive difference, 