from collections import deque

from strategies import Strategy
from utils import *

class ORBIndicator(Strategy):
    def __init__(self, symbol, orb_window=5,
                 stop_loss=0.01, take_profit=0.01, position_size=1.0, trailing_ratio=0.1, pyramid=False,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=2):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid,
                         pnl_target, pnl_loss, trade_max)
        self.orb_window = orb_window

        self.upper_support = None
        self.lower_support = None

        self.cond_1 = False
        self.cond_2 = False

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()

        if self.risk_manager._day_pause: 
            return None
        if not self.trade_window((9, 30), (11, 30)) and not self.position_manager.in_trade():
            return None

        signal = None
        if self.activated:
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade()
        return signal

    def enter_trade(self):
        signal = None
        if not self.cond_1 and self.close > self.upper_support:
            self.cond_1 = self.closes[-2] > self.opens[-2] and self.highs[-2] < self.upper_support
        elif not self.cond_2 and self.cond_1 and self.close > self.upper_support:
            if self.close > self.open and self.low > self.highs[-3] and self.low > self.upper_support:
                self.cond_2 = True
            else:
                self.cond_1 = False

        if not self.cond_1 and self.close < self.lower_support:
            self.cond_1 = self.closes[-2] < self.opens[-2] and self.lows[-2] > self.lower_support
        elif not self.cond_2 and self.cond_1 and self.close < self.lower_support:
            if self.close < self.open and self.high < self.lows[-3] and self.high < self.lower_support:
                self.cond_2 = True
            else:
                self.cond_1 = False

        if self.cond_1 and self.cond_2 and self.close > self.upper_support:
            signal, pos_leg = self.buy()
            if pos_leg is not None:
                self.stop_price = round(self.lows[-3] * (1 - 0.0001), 2)
                diff = self.price - self.stop_price
                self.profit_price = round(self.price + (diff * self.take_profit * 100), 2)
                self.cond_1 = False
                self.cond_2 = False
        elif self.cond_1 and self.cond_2 and self.close < self.lower_support:
            signal, pos_leg = self.sell()
            if pos_leg is not None:
                self.stop_price = round(self.highs[-3] * (1 + 0.0001), 2)
                diff = self.stop_price - self.price
                self.profit_price = round(self.price - (diff * self.take_profit * 100), 2)
                self.cond_1 = False
                self.cond_2 = False
        return signal
        
    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.upper_support = None
            self.lower_support = None
            
            self.cond_1 = False
            self.cond_2 = False
          
    def minimum_computations(self):
        if not self.activated:
            self.upper_support, self.lower_support = self.donchian_channel(self.orb_window)
            self.activated = len(self.prices) >= self.orb_window