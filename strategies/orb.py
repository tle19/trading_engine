import numpy as np

from strategies import Strategy, RiskManager
from utils import *

class ORBIndicator(Strategy):
    def __init__(self, symbol, orb_window=15, rsi_period=14,
                 fast_window=12, slow_window=26, signal_window=9,
                 stop_loss=0.001, take_profit=0.0025, trailing_ratio=0.1, position_size=1.0,
                 target=0.0001, loss=-0.0001):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.orb_window = orb_window
        self.rsi_period = rsi_period

        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None

        self.orb_tick = 0
        self.upper_support = None
        self.lower_support = None

        self.prev_hist = None

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_day()
        self.orb_tick += 1

        status = self.check_status()
        if status is not None:
            return status
        
        self.risk_manager.check_daily_target()   
        self.risk_manager.check_daily_stop()
        if self.risk_manager.day_pause():
            return None

        if not self.trade_window((9, 30), (10, 00)) and self.position is None:
            return None
        
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        hist = self.compute_macd(self.fast_window, self.slow_window, self.signal_window)

        if self.orb_tick == self.orb_window:
            self.upper_support = max(self.highs)
            self.lower_support = min(self.lows)

        signal = None
        if self.position is None and self.orb_tick > self.orb_window:
            signal = self.enter_trade()
        elif self.position is not None:
            signal = self.exit_trade()
        self.prev_hist = hist

        return signal

    def enter_trade(self):
        if self.close > self.upper_support:
            signal = self.buy()
            self.stop_price = round(self.open * (1 - self.stop_loss), 2)
            # print(f"{self.ts} ENTRY (L): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
            return signal
        elif self.close < self.lower_support:
            signal = self.sell()
            self.stop_price = round(self.open * (1 + self.stop_loss), 2)
            # print(f"{self.ts} ENTRY (S): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
            return signal
        
    def exit_trade(self):
        if self.position == "long" and self.close > self.open:
            self.stop_price = round(self.close, 2)
            # print(f"{self.ts} EXIT (L): {self.entry_price}, STOP: {self.stop_price}")
            return self.sell()
        if self.position == "short" and self.close < self.open:
            self.stop_price = round(self.close, 2)
            # print(f"{self.ts} EXIT (S): {self.entry_price}, STOP: {self.stop_price}")
            return self.buy()
        
    def reset_day(self):
        if self.trade_window((9, 30), (9, 30)):
            self.orb_tick = 0
            self.upper_support = None
            self.lower_support = None

            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None

            self.prev_hist = None
