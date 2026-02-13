import numpy as np

from strategies import Strategy
from utils import *

class RSIScalp(Strategy):
    def __init__(self, symbol, rsi_period=2, rsi_lower=1, rsi_upper=99, htf_window=20, vol_length=5,
                 stop_loss=0.0025, take_profit=0.001, position_size=0.25, trailing_ratio=0.15, pyramid=True, force_close=True, swing=False,
                 pnl_target=0.02, pnl_loss=-0.02, trade_max=50):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid, force_close, swing,
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
        self.reset_day()
        self.reset_indicators()
        self.minimum_computations()

        rsi = self.compute_indicators()

        if self.risk_manager._day_pause: 
            return None
        if not self.trade_window((10, 30), (15, 00)) and not self.position_manager.in_trade():
            return None
        
        signal = None
        if self.activated:
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade(rsi)
                if self.position_manager.in_trade():
                    average_entry = self.position_manager.average_entry()
                    for leg in self.position_manager.legs:
                        leg.target_price = average_entry * (1 + self.take_profit)
        return signal
    
    def enter_trade(self, rsi):
        signal = None
        if rsi < self.rsi_lower:
            signal, _ = self.buy()
        if rsi > self.rsi_upper:
            signal, _ = self.sell()
        return signal
        
    # def exit_trade(self):
    #     direction = self.position_manager.direction()
    #     if direction == 1 and self.close > self.open:
    #         for leg in self.position_manager.legs:
    #             leg.stop_price = self.low - 0.01
    #     if direction == -1 and self.close < self.open:
    #         for leg in self.position_manager.legs:
    #             leg.stop_price = self.high + 0.01
    #     return self.exit()
        
    def compute_indicators(self):
        self.ema = self.compute_ema(self.ema, self.close, self.htf_window)
        rsi = self.compute_rsi(self.closes, self.rsi_period)
        
        return rsi

    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.ema = None
            return None

    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.rsi_period,
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
            "volumes": self.volumes[-10:]
        }