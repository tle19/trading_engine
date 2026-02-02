from collections import deque
import pandas as pd
import numpy as np

from strategies import Strategy
from models import *
from utils import *

class EODReversion2(Strategy):
    def __init__(self, symbol, orb_window=1, fast_window=2, slow_window=10, htf_window=20, atr_diff=0.2,
                 stop_loss=0.01, take_profit=0.01, position_size=1.0, trailing_ratio=0.05, pyramid=False, force_close=True,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=1):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid, force_close,
                         pnl_target, pnl_loss, trade_max)
        self.orb_window = orb_window
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window
        self.atr_diff = atr_diff

        self.upper_support = None
        self.lower_support = None
        self.pre_market_high = None
        self.pre_market_low = None
        self.fast_ema = None
        self.slow_ema = None
        self.htf_ema = None
        
        self.weighted_pressure = []
        self.rolling_atr = []
        self.prev_day_atr_mean = 0.0

    def generate_signal(self, row, _=None):
        self.update(row)
        self.backfill_data()
        self.reset_data(reset_time=(4, 00))
        self.reset_day()
        self.reset_indicators(reset_time=(4, 00))
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

        self.atr_cond = np.mean(self.rolling_atr) - self.prev_day_atr_mean < self.atr_diff
        self.prev_day_atr_mean = np.mean(self.rolling_atr)

        if self.atr_cond and not self.position_manager.in_trade():
            if self.close < self.pre_market_low:
                if self.pressure < 0 and self.fast_ema < self.slow_ema and self.close > self.open:  # and self.slow_ema > self.htf_ema
                    signal, _ = self.buy()
            elif self.close > self.pre_market_high:
                if self.pressure > 0 and self.fast_ema > self.slow_ema and self.close < self.open:  # and self.slow_ema < self.htf_ema
                    signal, _ = self.sell()
            elif self.close < self.lower_support:
                if self.pressure < 0 and self.slow_ema > self.htf_ema and self.close > self.open:
                    signal, _ = self.buy()
            elif self.close > self.upper_support:
                if self.pressure > 0 and self.slow_ema < self.htf_ema and self.close < self.open:
                    signal, _ = self.sell()
        return signal
    
    def compute_indicators(self):
        self.fast_ema = self.compute_ema(self.fast_ema, self.price, self.fast_window)
        self.slow_ema = self.compute_ema(self.slow_ema, self.price, self.slow_window)
        # self.htf_ema = self.compute_ema(self.htf_ema, self.price, self.htf_window)
        self.rolling_atr.append(self.compute_atr(self.highs, self.lows, self.closes))
        self.weighted_pressure.append((self.close - self.open) / self.open * self.volume)
        self.pressure = sum(self.weighted_pressure)
        if self.trade_window((9, 28), (9, 29)):
            self.pre_market_high, self.pre_market_low = self.donchian_channel(period=330)

    def reset_indicators(self, reset_time=(4, 00)):
        if self.trade_window(reset_time, reset_time):
            self.upper_support = None
            self.lower_support = None
            self.pre_market_support = None
            self.pre_market_resistance = None
            self.fast_ema = None
            self.slow_ema = None
            self.htf_ema = None

            self.weighted_pressure = []
            self.rolling_atr = []

    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.orb_window,
                self.fast_window,
                self.slow_window,
                self.htf_window
            ) + 1
            self.upper_support, self.lower_support = self.donchian_channel(self.orb_window)
            self.activated = len(self.closes) > required_data

    def backfill_data(self):
        if not self.back_filled:
            df = open_data(self.symbol, start_time="9:30", end_time="15:00")
            df = df[df['timestamp'] < self.ts]
            last_trading_day = df['timestamp'].dt.date.max()
            df = df[df['timestamp'].dt.date == last_trading_day]
            if not df.empty:
                atr = self.compute_atr(df['high'], df['low'], df['close'])
                self.prev_day_atr_mean = np.mean(atr)
            else:
                self.prev_day_atr_mean = 0.25
            self.back_filled = True
            
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
            "open_volume": sum(self.volumes[0:15]),
            "upper_support": self.upper_support,
            "lower_support": self.lower_support,
            "curr_day_atr_mean": np.mean(self.rolling_atr), 
            "prev_day_atr_mean": self.prev_day_atr_mean
        }

    def param_grid(self):
        params = {
            "orb_window": [1], # 1, 2, 3, 4, 5, 10, 15, 30, 45, 60
            "fast_window": [2, 3, 4, 5], # 5, 8, 10
            "slow_window": [6, 7, 8, 9, 10, 12, 15, 20], # 10, 15, 20, 25
            "atr_diff": [0.20], # 0.05, 0.10, 0.15, 0.20, 0.25, 0.30
            "stop_loss": [0.01], # 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015
            "take_profit": [0.01] # 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015
        }
        return params
    