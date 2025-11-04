import numpy as np
from datetime import timedelta

from strategies import Strategy, RiskManager
from utils import *

class MACDIndicator(Strategy):
    def __init__(self, symbol, fast_window=12, slow_window=26, signal_window=9,
                 rsi_period=14, k_period=14, k_smooth=3, d_period=3,
                 stop_loss=0.005, take_profit=1.5, trailing_ratio=0.05, position_size=1.0,
                 target=0.001, loss=-0.0025, tf=5):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, tf)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.rsi_period = rsi_period
        self.k_period = k_period
        self.k_smooth = k_smooth
        self.d_period = d_period

        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None

        self.stoch_signal = None # None, "long", "short"

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()

        status = self.check_status()
        if status is not None:
            return status
        
        if not self.trade_window((9, 30), (15, 30)) and self.position is None:
            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
            self.stoch_signal = None
            return None
        
        stoch_k, stoch_d = self.compute_stochastic(self.highs, self.lows, self.prices, self.k_period, self.k_smooth, self.d_period)
        hist = self.compute_macd(self.prices, self.fast_window, self.slow_window, self.signal_window)
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        
        signal = None
        if self.position is None and hist != 0:
            signal = self.enter_trade(stoch_k, stoch_d, rsi, hist)
        # elif self.position is not None:
        #     self.set_trailing_stop()
        self.prev_rsi = rsi
        return signal
    
    def enter_trade(self, stoch_k, stoch_d, rsi, hist):
        if stoch_k < 20 and stoch_d < 20: #stoch threshold walk forwward search
            self.stoch_signal = "long"
        elif stoch_k > 80 and stoch_d > 80:
            self.stoch_signal = "short"
       
        if self.stoch_signal == "long" and 20 < stoch_k < 80 and 20 < stoch_d < 80 and rsi > 50 and hist > 0:
            signal = self.buy() 
            self.stop_price = round(self.low * (1 - self.stop_loss), 2)
            stop_dist = self.entry_price - self.stop_price
            self.profit_price = round(self.entry_price + (stop_dist * self.take_profit), 2)
            # print(self.ts, self.stoch_signal, self.entry_price, self.stop_price, self.profit_price)
            return signal
        if self.stoch_signal == "short" and 20 < stoch_k < 80 and 20 < stoch_d < 80 and rsi < 50 and hist < 0:
            signal = self.sell() 
            self.stop_price = round(self.high * (1 + self.stop_loss), 2)
            stop_dist = self.stop_price - self.entry_price
            self.profit_price = round(self.entry_price - (stop_dist * self.take_profit), 2)
            # print(self.ts, self.stoch_signal, self.entry_price, self.stop_price, self.profit_price)
            return signal