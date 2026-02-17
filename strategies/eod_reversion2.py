import os
from datetime import datetime
import pandas as pd
import numpy as np

from strategies import Strategy
from models import *
from utils import *

class EODReversion2(Strategy):
    def __init__(self, symbol, fast_window=5, slow_window=10, htf_window=20,
                 stop_loss=0.0025, take_profit=0.005, position_size=1.0, trailing_ratio=0.05, 
                 pyramid=False, force_close=True, swing=False,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=1):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid, force_close, swing,
                         pnl_target, pnl_loss, trade_max)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window
        
        self.fast_ema = None
        self.slow_ema = None
        self.htf_ema = None

        self.pressure = []

    def generate_signal(self, row, _=None):
        self.update(row)
        self.reset_data()
        self.reset_day()
        self.reset_indicators()
        self.minimum_computations()
        
        self.compute_indicators()

        if self.risk_manager._day_pause:
            return None

        if not self.trade_window((15, 49), (15, 49)) and not self.position_manager.in_trade():
            return None
        
        signal = None
        if self.activated:
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade()
        return signal
    
    def enter_trade(self):
        signal = None
        # if not self.position_manager.in_trade():
        #     print(sum(self.pressure))
        if self.close < self.opens[0] and sum(self.pressure) < 0:
            signal, _ = self.buy()
        if self.close > self.opens[0] and sum(self.pressure) > 0:
            signal, _ = self.sell()
        # self.compute_swing(mode="high", lookback=10)
        return signal
        
    def compute_indicators(self):
        self.fast_ema = self.compute_ema(self.fast_ema, self.close, self.fast_window)
        self.slow_ema = self.compute_ema(self.slow_ema, self.close, self.slow_window)
        self.htf_ema = self.compute_ema(self.htf_ema, self.close, self.htf_window)
        range = (self.high - self.low) if (self.high != self.low) else 1e-9
        self.pressure.append(((self.close - self.open) / range) * self.volume)
        
    def reset_indicators(self, reset_time=(9, 30)):
        if self.trade_window(reset_time, reset_time):
            self.fast_ema = None
            self.slow_ema = None
            self.htf_ema = None

            self.pressure = []

    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.fast_window,
                self.slow_window,
                self.htf_window
            ) + 1
            self.activated = len(self.closes) > required_data
            
    def add_features(self, direction, stop_price, target_price):
        self.features = {
            "direction": direction,
            "entry_time": self.ts.isoformat(),
            "entry_price": self.close,
            "stop_price": stop_price,
            "target_price": target_price,
            "session_open": self.opens[0],
            "session_low": min(self.lows),
            "session_high": max(self.highs),
            "open_volume": sum(self.volumes[0:15])
        }

    def param_grid(self):
        params = {
            "fast_window": [2], # 5, 8, 10
            "slow_window": [10], # 10, 15, 20, 25
            "htf_window": [10], # 10, 15, 20, 25
            "stop_loss": [0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015], # 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015
            "take_profit": [0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015] # 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015
        }
        return params