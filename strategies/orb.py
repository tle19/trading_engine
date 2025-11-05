import numpy as np

from strategies import Strategy, RiskManager
from utils import *

class ORBIndicator(Strategy):
    def __init__(self, symbol, orb_window=15, rsi_period=14,
                 stop_loss=0.005, take_profit=0.01, trailing_ratio=0.05, position_size=1.0,
                 target=0.001, loss=-0.001, tf=1):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, tf)
        self.orb_window = orb_window
        self.rsi_period = rsi_period

        self.orb_tick = 0
        self.upper_support = None
        self.lower_support = None
        self.above_orb = False
        self.below_orb = False
        self.above_orb_rejected = False
        self.below_orb_rejected = False

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.orb_tick += 1

        status = self.check_status()
        if status is not None:
            return status
        
        self.risk_manager.daily_risk_target()   
        self.risk_manager.daily_risk_stop()
        if self.risk_manager.is_day_pause():
            return None

        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
            self.orb_tick = 0
            self.upper_support = None
            self.lower_support = None
            self.above_orb = False
            self.below_orb = False
            self.above_orb_rejected = False
            self.below_orb_rejected = False
            return None
        
        if self.orb_tick == self.orb_window:
            self.upper_support = max(self.highs)
            self.lower_support = min(self.lows)

        if self.orb_tick >= self.orb_window:
            if not self.above_orb and self.close > self.upper_support:
                self.above_orb = True
            if not self.below_orb and self.close < self.lower_support:
                self.below_orb = True
            if self.above_orb and self.close < self.upper_support:
                self.above_orb = False
                self.above_orb_rejected = True
            if self.below_orb and self.close > self.lower_support:
                self.below_orb = False
                self.below_orb_rejected = True

        signal = None
        if self.position is None and self.orb_tick > self.orb_window:
            signal = self.enter_trade()
        # elif self.position is not None:
        #     self.set_trailing_stop()
        return signal

    def enter_trade(self):
        if self.above_orb:
            signal = self.buy()
            # self.stop_price = max(self.lower_support, self.stop_price)
            stop_dist = self.entry_price - self.stop_price
            self.profit_price = round(self.entry_price + (stop_dist * 0.5), 2)
            return signal
        if self.below_orb:
            signal = self.sell()
            # self.stop_price = min(self.upper_support, self.stop_price)
            stop_dist = self.stop_price - self.entry_price
            self.profit_price = round(self.entry_price - (stop_dist * 0.5), 2)
            return signal
        # if self.below_orb_rejected:
        #     signal = self.buy()
        #     return signal
        # if self.above_orb_rejected:
        #     signal = self.sell()
        #     return signal