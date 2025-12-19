import numpy as np

from strategies import Strategy
from utils import *

class RSIScalp(Strategy):
    def __init__(self, symbol, rsi_period=2, rsi_lower=10, rsi_upper=90, htf_window=50, vol_length=5,
                 stop_loss=0.01, take_profit=0.01, position_size=1.0, trailing_ratio=0.15, pyramid=False, 
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=20):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid,
                         pnl_target, pnl_loss, trade_max)
        self.rsi_period = rsi_period
        self.rsi_lower = rsi_lower
        self.rsi_upper = rsi_upper
        self.htf_window = htf_window
        self.vol_length = vol_length

        self.ema = None
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()

        rsi = self.compute_indicators()

        # if self.risk_manager._day_pause: 
        #     return None
        if not self.trade_window((10, 30), (15, 00)) and not self.position_manager.in_trade():
            return None
        
        signal = None
        if self.activated:
            signal = self.exit_trade(rsi)
            if signal is None:
                signal = self.enter_trade(rsi)
        return signal
    
    def enter_trade(self, rsi):
        if rsi < self.rsi_lower:
            return self.buy()
        if rsi > self.rsi_upper:
            return self.sell()
        
    def exit_trade(self, rsi):
        direction = self.position_manager.direction()
        if direction == 1 and rsi > self.rsi_upper:
            return self.exit()
        if direction == -1 and rsi < self.rsi_lower:
            return self.exit()
        
    def compute_indicators(self):
        self.ema = self.compute_ema(self.ema, self.prices[-1], self.fast_window)
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        
        return rsi

    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.ema = None
            return None

    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.rsi_period
            ) + 1
            self.activated = len(self.prices) > required_data

    def add_features(self, direction, stop_price, target_price):
        self.features = {
            "direction": direction,
            "entry_time": self.ts,
            "entry_price": self.price,
            "stop_price": stop_price,
            "target_price": target_price,
            "session_open": self.opens[0],
            "session_low": min(self.lows),
            "session_high": max(self.highs),
            "volumes": self.volumes[-10:]
        }