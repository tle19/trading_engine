import numpy as np
from datetime import timedelta

from strategies import Strategy, RiskManager
from utils import *

class MACDIndicator(Strategy):
    def __init__(self, symbol, fast_window=12, slow_window=26, signal_window=9, htf_window=50,
                 rsi_period=14, vol_fast_window=7, vol_slow_window=12,
                 stop_loss=0.005, take_profit=0.0075, trailing_ratio=0.05, position_size=1.0,
                 target=0.001, loss=-0.001):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.htf_window = htf_window
        self.rsi_period = rsi_period
        self.vol_fast_window = vol_fast_window
        self.vol_slow_window = vol_slow_window

        self.ema = None
        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None
        self.prev_rsi = None
        self.prev_hist = None
        self.prev_vol = None
        self.entry_rsi = None

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()

        status = self.check_status()
        if status is not None:
            return status
        
        if not self.trade_window((9, 30), (13, 00)) and self.position is None:
            self.ema = None
            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
            self.prev_rsi = None
            self.prev_hist = None
            self.prev_vol = None
            self.entry_rsi = None
            return None
        
        ema = self.compute_ema(self.ema, self.prices[-1], self.htf_window)
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        hist = self.compute_macd(self.fast_window, self.slow_window, self.signal_window)
        vol = self.compute_volume_oscillator(self.volumes, self.vol_fast_window, self.vol_slow_window)
        
        signal = None
        if self.position is None and len(self.prices) > self.slow_window and rsi is not None:
            signal = self.enter_trade(ema, rsi, hist, vol)
        elif self.position is not None and rsi is not None:
            signal = self.exit_trade(rsi, hist)
        self.prev_rsi = rsi
        self.prev_hist = hist
        self.prev_vol = vol
        return signal

    def enter_trade(self, ema, rsi, hist, vol):
        vol_cond = vol > 0 and abs(vol - self.prev_vol) > 0.01
        if rsi < 50 and self.prev_hist < 0 and hist > 0 and rsi > self.prev_rsi:
            if self.close > ema or vol_cond:
                signal = self.buy()
                self.stop_price = round(self.low * (1 - self.stop_loss), 2)
                self.entry_rsi = rsi
                # print(f"{self.ts} ENTRY (L): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
                return signal
        if rsi > 50 and self.prev_hist > 0 and hist < 0 and rsi < self.prev_rsi:
            if self.close < ema or vol_cond:
                signal = self.sell()
                self.stop_price = round(self.high * (1 + self.stop_loss), 2)
                self.entry_rsi = rsi
                # print(f"{self.ts} ENTRY (S): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
                return signal
        
    def exit_trade(self, rsi, hist):
        if self.position == "long" and rsi > self.entry_rsi and rsi > 50 and hist > 0 and hist < self.prev_hist:
            self.stop_price = round(self.close, 2)
            # print(f"{self.ts} EXIT (L): {self.entry_price}, STOP: {self.stop_price}")
            return self.sell()
        if self.position == "short" and rsi < self.entry_rsi and rsi < 50 and hist < 0 and hist > self.prev_hist:
            self.stop_price = round(self.close, 2)
            # print(f"{self.ts} EXIT (S): {self.entry_price}, STOP: {self.stop_price}")
            return self.buy()

