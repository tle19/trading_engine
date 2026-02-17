import os
from datetime import datetime
import pandas as pd
import numpy as np

from strategies import Strategy
from models import *
from utils import *

class EODReversion2(Strategy):
    def __init__(self, symbol, rsi_period=2, rsi_lower=30, rsi_upper=70, htf_window=30,
                 stop_loss=0.0025, take_profit=0.01, position_size=1.0, trailing_ratio=0.05, 
                 pyramid=False, force_close=True, swing=False,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=1):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid, force_close, swing,
                         pnl_target, pnl_loss, trade_max)
        self.rsi_period = rsi_period
        self.rsi_lower = rsi_lower
        self.rsi_upper = rsi_upper
        self.htf_window = htf_window
        
        self.ema = None

    def generate_signal(self, row, _=None):
        self.update(row)
        self.backfill_data()
        self.reset_data()
        self.reset_day()
        self.reset_indicators()
        self.minimum_computations()
        
        rsi = self.compute_indicators()

        if self.risk_manager._day_pause:
            return None

        if not self.trade_window((15, 49), (15, 49)) and not self.position_manager.in_trade():
            return None
        
        signal = None
        if self.activated:
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade(rsi)
        return signal
    
    def enter_trade(self, rsi, signal=None):
        if rsi < self.rsi_lower:
            signal, leg = self.buy()
            leg.stop_price = self.compute_swing(mode="low", lookback=10) * (1 - 0.001)
        if rsi > self.rsi_upper:
            signal, leg = self.sell()
            leg.stop_price = self.compute_swing(mode="high", lookback=10) * (1 + 0.001)
        return signal
    
    # def exit_trade(self, signal=None):
    #     direction = self.position_manager.direction()
    #     if direction == 1 and self.close > self.open:
    #         return self.exit()
    #     if direction == -1 and self.open < self.open:
    #         return self.exit()
    #     return signal
            
    def compute_indicators(self):
        self.ema = self.compute_ema(self.ema, self.close, window=self.htf_window)
        if self.trade_window((15, 49), (15, 49)):
            closes = self.d_closes.copy() + [self.close]
            daily_rsi = self.compute_rsi(closes, period=self.rsi_period)
        else:
            daily_rsi = 50
        return daily_rsi
        
    def reset_indicators(self, reset_time=(9, 30)):
        if self.trade_window(reset_time, reset_time):
            self.ema = None

    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.rsi_period,
                self.rsi_lower,
                self.rsi_upper,
                self.htf_window,
            ) + 1
            self.activated = len(self.closes) > required_data

    def backfill_data(self):
        if not self.back_filled:
            df = open_data(self.symbol, mode="daily")
            df = df[df['timestamp'] < self.ts.normalize()]
            if not df.empty:
                self.d_opens = list(df['open'])
                self.d_highs = list(df['high'])
                self.d_lows = list(df['low'])
                self.d_closes = list(df['close'])
                self.d_volumes = list(df['volume'])
            self.back_filled = True

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
            "rsi_period": [2, 5, 7, 14],
            "rsi_lower": [10, 20, 30],
            "rsi_upper": [70, 80, 90],
            "htf_window": [30],
            "stop_loss": [0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015], # 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015
            "take_profit": [0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015] # 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015
        }
        return params