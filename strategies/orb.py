import numpy as np

from strategies import Strategy, RiskManager
from utils import *

class ORBIndicator(Strategy):
    def __init__(self, symbol, orb_window=15, rsi_period=14,
                 fast_window=12, slow_window=26, signal_window=9,
                 stop_loss=0.005, take_profit=0.075, trailing_ratio=0.1, position_size=1.0,
                 target=0.0001, loss=-0.0001, tf=1):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, tf)
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
        self.daily_bias = None # bullish, bearish
        self.orb_rejected = False

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_day()
        self.orb_tick += 1

        status = self.check_status()
        if status is not None:
            return status
        
        self.risk_manager.daily_risk_target()   
        self.risk_manager.daily_risk_stop()
        if self.risk_manager.is_day_pause():
            return None

        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
            return None
        
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        hist = self.compute_macd(self.fast_window, self.slow_window, self.signal_window)

        if self.orb_tick == self.orb_window:
            self.upper_support = max(self.highs)
            self.lower_support = min(self.lows)

        if self.orb_tick >= self.orb_window:
            if not self.daily_bias and self.close > self.upper_support:
                self.daily_bias = "bullish"
            if not self.daily_bias and self.close < self.lower_support:
                self.daily_bias = "bearish"
            if self.daily_bias == "bullish" and self.close < self.upper_support:
                self.orb_rejected = True
            if self.daily_bias == "bearish" and self.close > self.lower_support:
                self.orb_rejected = True

        signal = None
        if self.position is None and self.orb_tick > self.orb_window:
            signal = self.enter_trade(rsi, hist)
        elif self.position is not None:
            if self.position == "long" and self.close > self.lower_support and self.stop_price < self.lower_support:
                self.stop_price = self.lower_support - self.compute_min_distance()
            elif self.position == "short" and self.close < self.upper_support and self.stop_price > self.lower_support:
                self.stop_price = self.upper_support + self.compute_min_distance()
            if self.orb_rejected:
                self.set_trailing_stop()
        return signal

    def enter_trade(self, rsi, hist):
        if self.daily_bias == "bearish" and rsi > 50 and hist > 0:
            signal = self.buy()
            self.stop_price = round(self.low * (1 - self.stop_loss), 2)
            print(self.ts, "ENTRY (L):", self.entry_price, "STOP:", self.stop_price)
            return signal
        if self.daily_bias == "bullish" and rsi < 50 and hist < 0:
            signal = self.sell()
            self.stop_price = round(self.high * (1 + self.stop_loss), 2)
            print(self.ts, "ENTRY (S):", self.entry_price, "STOP:", self.stop_price)
            return signal

    def exit_trade(self, rsi, hist):
        raise NotImplementedError
    
    def reset_day(self):
        if self.trade_window((9, 30), (9, 30)):
            self.orb_tick = 0
            self.upper_support = None
            self.lower_support = None
            self.daily_bias = None
            self.orb_rejected = False

            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
