import numpy as np
from datetime import timedelta

from strategies import Strategy, RiskManager
from utils import *

class MACDIndicator(Strategy):
    def __init__(self, symbol, fast_window=12, slow_window=26, signal_window=9, rsi_period=14,
                 stop_loss=0.001, take_profit=0.01, trailing_ratio=0.05, position_size=1.0,
                 target=0.001, loss=-0.001, tf=1):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, tf)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.rsi_period = rsi_period

        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None
        self.prev_rsi = None
        self.prev_hist = None

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()

        status = self.check_status()
        if status is not None:
            return status
        
        # self.risk_manager.daily_risk_target()   
        # self.risk_manager.daily_risk_stop()
        # if self.risk_manager.is_day_pause():
        #     return None
        
        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
            self.prev_rsi = None
            self.prev_hist = None
            return None
        
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        hist = self.compute_macd(self.fast_window, self.slow_window, self.signal_window)
        
        signal = None
        if self.position is None and len(self.prices) > self.slow_window:
            signal = self.enter_trade(rsi, hist)
        else:
            signal = self.exit_trade(rsi)
        self.prev_rsi = rsi
        self.prev_hist = hist
        return signal

    def enter_trade(self, rsi, hist):
        if rsi < 50 and self.prev_hist < 0 and hist > 0 and rsi > self.prev_rsi:
            signal = self.buy()
            self.stop_price = round(self.low * (1 - self.stop_loss), 2)
            print(f"{self.ts} ENTRY (L): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
            return signal
        if rsi > 50 and self.prev_hist > 0 and hist < 0 and rsi < self.prev_rsi:
            signal = self.sell()
            self.stop_price = round(self.high * (1 + self.stop_loss), 2)
            print(f"{self.ts} ENTRY (S): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
            return signal
        
    def exit_trade(self, rsi):
        if self.position == "long" and rsi > 50:
            self.stop_price = round(self.close, 2)
            print(f"{self.ts} EXIT (L): {self.entry_price}, STOP: {self.stop_price}")
            return self.sell()
        if self.position == "short" and rsi < 50:
            self.stop_price = round(self.close, 2)
            print(f"{self.ts} EXIT (S): {self.entry_price}, STOP: {self.stop_price}")
            return self.buy()