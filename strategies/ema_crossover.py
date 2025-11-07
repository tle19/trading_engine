import numpy as np

from strategies import Strategy, RiskManager
from utils import *

class EMACrossoverIndicator(Strategy):
    def __init__(self, symbol, fast_window=10, slow_window=20, htf_window=50, 
                 rsi_period=6, rsi_lower=30, rsi_upper=70,
                 stop_loss=0.01, take_profit=0.01, trailing_ratio=0.05, position_size=1.0,
                 target=0.001, loss=-0.001):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window
        self.rsi_period = rsi_period
        self.rsi_lower = rsi_lower
        self.rsi_upper = rsi_upper
        
        self.fast_ema = None
        self.slow_ema = None
        self.htf_ema = None

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss, pause_duration=390)
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data()

        status = self.check_status()
        if status is not None:
            return status
        
        if len(self.prices) < self.slow_window:
            return None
        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
            self.mode = None
            return None

        self.fast_ema = self.compute_ema(self.fast_ema, self.prices[-1], self.fast_window)
        self.slow_ema = self.compute_ema(self.slow_ema, self.prices[-1], self.slow_window)
        self.htf_ema = self.compute_ema(self.htf_ema, self.prices[-1], self.htf_window)

        if self.position is None:
            return self.enter_trade(self.fast_ema, self.slow_ema, self.htf_ema)
        elif self.position is not None:
            self.exit_trade(self.fast_ema, self.slow_ema, self.htf_ema)
        return None
    
    def enter_trade(self, fast_ema, slow_ema, htf_ema):
        if fast_ema > slow_ema >= htf_ema:
            if self.close < self.open:
                signal = self.buy() 
                self.stop_price = round(self.low * (1 - self.stop_loss), 2)
                return signal
        if fast_ema < slow_ema <= htf_ema:
            if self.close > self.open:
                signal = self.sell() 
                self.stop_price = round(self.high * (1 + self.stop_loss), 2)
                return signal

    def exit_trade(self, fast_ema, slow_ema, htf_ema):
        if self.position == "long" and fast_ema < slow_ema <= htf_ema:
            self.stop_price = round(self.close, 2)
            return self.sell()
        if self.position == "short" and fast_ema > slow_ema >= htf_ema:
            self.stop_price = round(self.close, 2)
            return self.sell() 