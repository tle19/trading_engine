import numpy as np

from strategies import Strategy, RiskManager
from utils import *

class ORBIndicator(Strategy):
    def __init__(self, symbol, orb_window=5, rsi_period=14, safety_dist=0.5,
                 stop_loss=0.001, take_profit=1.0, trailing_ratio=0.1,
                 target=0.0001, loss=-0.0001):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio)
        self.orb_window = orb_window
        self.rsi_period = rsi_period
        self.safety_dist = safety_dist

        self.upper_support = None
        self.lower_support = None

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()

        # self.rsi_period = self.compute_rsi(self.prices, self.rsi_period)
        
        self.risk_manager.check_daily_target()   
        self.risk_manager.check_daily_stop()
        if self.risk_manager.day_pause():
            return None
        
        status = self.check_status()
        if status is not None:
            return status
        if not self.trade_window((9, 30), (15, 30)) and self.position is None:
            return None

        signal = None
        if self.position is None and self.activated:
            signal = self.enter_trade()
        # elif self.position is not None:
        #     if self.position == "long":
        #         current_move = self.close - self.entry_price
        #         price_move = self.profit_price - self.entry_price
        #         if current_move >= self.safety_dist * price_move:
        #             self.stop_price = round(self.upper_support, 2)
        #     elif self.position == "short":
        #         current_move = self.entry_price - self.close
        #         price_move = self.entry_price - self.profit_price
        #         if current_move >= self.safety_dist * price_move:
        #             self.stop_price = round(self.lower_support, 2)
        #     self.set_trailing_stop()
        return signal

    def enter_trade(self):
        if self.close > self.upper_support:
            signal = self.buy()
            diff = self.upper_support - self.lower_support
            self.stop_price = round(self.lower_support * (1 - self.stop_loss), 2)
            self.profit_price = round(self.upper_support + (diff * self.take_profit), 2)
            return signal
        elif self.close < self.lower_support:
            signal = self.sell()
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