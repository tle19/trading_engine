import numpy as np

from strategies import PairStrategy
from models import *
from utils import *

class SpreadDiff(PairStrategy):
    def __init__(self, pair, fast_window=10, slow_window=25, 
                 stop_loss=0.01, take_profit=0.01, position_size=1.0,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=200):
        super().__init__(pair, stop_loss, take_profit, position_size,
                         pnl_target, pnl_loss, trade_max)
        self.fast_window = fast_window
        self.slow_window = slow_window

        self.ema_fast1 = None
        self.ema_slow1 = None
        self.ema_fast2 = None
        self.ema_slow2 = None
    
    def generate_signal(self):
        self.compute_indicators()

        if self.risk_manager._day_pause: 
            return None

        if not self.trade_window((10, 00), (14, 30)) and not self.position_manager.in_trade():
            return None
        
        signal = None
        signal = self.exit_trade()
        if signal is None:
            signal = self.enter_trade()
        return signal
    
    def enter_trade(self):
        s1, s2 = self.data[self.symbol1], self.data[self.symbol2]
        s1["target_price"], s2["target_price"] = 0, 0
        # if spread is tight
        # calculate target_prices for a given bid-ask for both, 
        # look for positive difference, 

        signal = self.buy_pair()
        signal = self.sell_pair()
        return signal
        
    def exit_trade(self):
        direction = self.data[self.symbol1]["direction"]
        target_price1 = self.data[self.symbol1]["target_price"]
        target_price2 = self.data[self.symbol2]["target_price"]
        # both must be above stop to exit
        if direction == 1 and self.ema_fast1 < self.ema_slow1:
            return self.exit()
        if direction == -1 and self.ema_fast2 > self.ema_slow2:
            return self.exit()
        
    def compute_indicators(self):
        self.ema_fast1 = self.compute_ema(self.ema_fast1, self.prices[-1], self.fast_window)
        self.ema_slow1 = self.compute_ema(self.ema_slow1, self.prices[-1], self.slow_window)

        self.ema_fast2 = self.compute_ema(self.ema_fast2, self.prices[-1], self.fast_window)
        self.ema_slow2 = self.compute_ema(self.ema_slow2, self.prices[-1], self.slow_window)