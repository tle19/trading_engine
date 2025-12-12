import numpy as np

from strategies import Strategy, RiskManager
from utils import *

class ORBIndicator(Strategy):
    def __init__(self, symbol, orb_window=5, rsi_period=14,
                 stop_loss=0.001, take_profit=1.0, position_size=1.0, trailing_ratio=0.1,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=1):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio,
                         pnl_target, pnl_loss, trade_max)
        self.orb_window = orb_window
        self.rsi_period = rsi_period

        self.upper_support = None
        self.lower_support = None

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()

        # self.rsi = self.compute_rsi(self.prices, self.rsi_period)

        if self.risk_manager._day_pause: 
            return None
        if not self.trade_window((9, 30), (15, 30)) and self.position is None:
            return None

        signal = None
        if self.activated:
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade()
        return signal

    def enter_trade(self):
        signal = None
        if self.close > self.upper_support:
            signal, pos_leg = self.buy()
            if pos_leg is not None:
                diff = self.upper_support - self.lower_support
                self.stop_price = round(self.lower_support * (1 - self.stop_loss), 2)
                self.profit_price = round(self.upper_support + (diff * self.take_profit), 2)
        elif self.close < self.lower_support:
            signal, pos_leg = self.sell()
            if pos_leg is not None:
                diff = self.upper_support - self.lower_support
                self.stop_price = round(self.upper_support * (1 + self.stop_loss), 2)
                self.profit_price = round(self.lower_support - (diff * self.take_profit), 2)
        return signal
        
    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.upper_support = None
            self.lower_support = None
          
    def minimum_computations(self):
        if not self.activated:
            self.upper_support, self.lower_support = self.donchian_channel(self.orb_window)
            self.activated = len(self.prices) >= self.orb_window