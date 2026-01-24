from collections import deque
import pandas as pd
import numpy as np

from strategies import Strategy
from models import *
from utils import *

class EODBuyBack(Strategy):
    def __init__(self, symbol, orb_window=1, htf_window=10, overnight_thresh=0.04,
                 stop_loss=0.01, take_profit=0.01, position_size=1.0, trailing_ratio=0.15, pyramid=False, force_close=True,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=1, drawdown_max=0.20):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid, force_close,
                         pnl_target, pnl_loss, trade_max, drawdown_max)
        self.orb_window = orb_window
        self.htf_window = htf_window
        self.overnight_thresh = overnight_thresh

        self.upper_support = None
        self.lower_support = None
        self.ema = None
        self.weighted_pressure = []
        self.overnight_pct = 0

        self.prev_day_close = None
        self.regime_ema = None
        self.adx = None
        self.atr = None
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_day()
        self.reset_indicators()
        self.minimum_computations()
        
        self.compute_indicators()

        if self.risk_manager._day_pause: 
            return None

        if not self.trade_window((15, 00), (15, 45)) and not self.position_manager.in_trade():
            return None
        
        signal = None
        if self.activated:
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade()
        return signal
    
    def enter_trade(self):
        signal = None
        pos_sum = sum(x for x in self.weighted_pressure if x > 0)
        neg_sum = sum(x for x in self.weighted_pressure if x < 0)
        pressure = pos_sum + neg_sum
        self.position_size = self.risk_manager.position_size
        if pressure < 0 and self.close < self.lower_support and self.overnight_pct < self.overnight_thresh and self.close > self.open:
            signal, _ = self.buy()
        if pressure > 0 and self.close > self.upper_support and self.overnight_pct < self.overnight_thresh and self.close < self.open:
            signal, _ = self.sell()
        return signal
        
    def compute_indicators(self):
        self.ema = self.compute_ema(self.ema, self.prices[-1], self.htf_window)
        self.weighted_pressure.append((self.close - self.open) * self.volume)

    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.upper_support = None
            self.lower_support = None
            self.ema = None

            self.weighted_pressure = []

            if self.d_closes:
                self.prev_day_close = self.d_closes[-1]
                self.regime_ema = self.compute_ma(self.d_closes, window=50)
                self.adx = self.compute_adx(self.d_highs, self.d_lows, self.d_closes)
                self.atr = self.compute_atr(self.d_highs, self.d_lows, self.d_closes)
                self.overnight_pct = abs(self.open - self.prev_day_close) / self.prev_day_close

    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.orb_window,
                self.htf_window
            ) + 1
            self.upper_support, self.lower_support = self.donchian_channel(self.orb_window)
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