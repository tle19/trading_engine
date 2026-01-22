from collections import deque
import pandas as pd
import numpy as np

from strategies import Strategy
from models import *
from utils import *

class BoxIndicator(Strategy):
    def __init__(self, symbol, fast_window=50, slow_window=50, htf_window=100, 
                 stop_loss=0.01, take_profit=0.01, position_size=1.0, trailing_ratio=0.15, pyramid=False, force_close=True,
                 pnl_target=0.02, pnl_loss=-0.02, trade_max=10):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid, force_close,
                         pnl_target, pnl_loss, trade_max)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window

        self.ema = None

        df = open_data(self.symbol, start_date="2024-01-01", end_date="2026-01-01")
        self.history = resample_data(df)
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()
        
        slow_ma, htf_ma = self.compute_indicators()

        if self.risk_manager._day_pause: 
            return None

        if not self.trade_window((9, 30), (15, 00)) and not self.position_manager.in_trade():
            return None
        
        signal = None
        if self.activated:
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade(slow_ma, htf_ma)
        return signal
    
    def enter_trade(self, slow_ma, htf_ma, threshold=0.005, ema_band=0.002):
        signal = None
        down_stretch = abs(self.ema - min(self.lows[-15:])) / self.ema
        up_stretch = abs(self.ema - max(self.highs[-15:])) / self.ema
        near_ema = (abs(self.close - self.ema) / self.ema) < ema_band
        if near_ema:
            if self.close > self.ema and down_stretch > threshold:
                if self.symbol == "GOOG":
                    signal, pos_leg = self.buy()
                    if signal:
                        pos_leg.target_price = self.close * (1 + threshold)
                        pos_leg.stop_price = (self.close * (1 - (threshold / 2)))
                elif self.symbol == "GOOGL":
                    signal, pos_leg = self.sell()
                    if signal:
                        pos_leg.target_price = self.close * (1 - threshold)
                        pos_leg.stop_price = (self.close * (1 + (threshold / 2)))
            elif self.close < self.ema and up_stretch > threshold:
                if self.symbol == "GOOG":
                    signal, pos_leg = self.sell()
                    if signal:
                        pos_leg.target_price = self.close * (1 - threshold)
                        pos_leg.stop_price = (self.close * (1 + (threshold / 2)))
                elif self.symbol == "GOOGL":
                    signal, pos_leg = self.buy()
                    if signal:
                        pos_leg.target_price = self.close * (1 + threshold)
                        pos_leg.stop_price = (self.close * (1 - (threshold / 2)))
            return signal
        
    # def exit_trade(self, slow_ma):
    #     direction = self.position_manager.direction()
    #     if direction == 1 and self.ema < slow_ma:
    #         return self.exit()
    #     if direction == -1 and self.ema > slow_ma:
    #         return self.exit()
        
    def compute_indicators(self):
        arr = np.array(self.prices)
        self.ema = self.compute_ema(self.ema, self.prices[-1], self.fast_window)
        slow_ma = self.compute_ma(arr, self.slow_window)
        htf_ma = self.compute_ma(arr, self.htf_window)
        
        return slow_ma, htf_ma

    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.ema = None

            history = self.history.loc[self.history.index < self.ts.normalize()].tail(20)
            highs = history["high"].values
            lows = history["low"].values
            closes = history["close"].values

            self.prev_day_close = closes[-1]
            self.regime_ema = self.compute_ma(closes, window=50)
            self.adx = self.compute_adx(highs, lows, closes)
            self.atr = self.compute_atr(highs, lows, closes)

    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.fast_window,
                self.slow_window,
                self.htf_window
            ) + 1
            self.activated = len(self.prices) > required_data

    def add_features(self, direction, stop_price, target_price):
        self.features = {
            "direction": direction,
            "entry_time": self.ts.isoformat(),
            "entry_price": self.price,
            "stop_price": stop_price,
            "target_price": target_price,
            "session_open": self.opens[0],
            "session_low": min(self.lows),
            "session_high": max(self.highs),
            "open_volume": sum(self.volumes[0:5]),
            "prev_day_close": self.prev_day_close,
            "ema": self.regime_ema,
            "adx": self.adx,
            "atr": self.atr,
        }