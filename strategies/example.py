import numpy as np

from strategies import Strategy
from utils import *

class SMACrossover(Strategy):
    def __init__(self, symbol, fast_window=10, slow_window=20, htf_window=50, 
                 stop_loss=0.01, take_profit=0.02, position_size=1.0, trailing_ratio=0.15, pyramid=False, 
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=3):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid,
                         pnl_target, pnl_loss, trade_max)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window

        self.ema = None
    
    def generate_signal(self, row):
        self.update(row)  # store OHLCV
        self.reset_data() # intraday data reset
        self.reset_indicators()
        self.minimum_computations() # ensure enough data for indicators
        
        # compute indicators
        slow_ma, htf_ma = self.compute_indicators()

        # end day after pnl target/loss
        if self.risk_manager._day_pause: 
            return None

        # set trading window
        if not self.trade_window((9, 30), (16, 00)) and not self.position_manager.in_trade():
            return None
        
        # enter/exit positions
        signal = None
        if self.activated:
            signal = self.exit_trade(slow_ma)
            if signal is None:
                signal = self.enter_trade(slow_ma, htf_ma)
        return signal
    
    def enter_trade(self, slow_ma, htf_ma):
        if self.ema > slow_ma >= htf_ma:
            return self.buy()
        if self.ema < slow_ma <= htf_ma:
            return self.sell()
        
    def exit_trade(self, slow_ma):
        direction = self.position_manager.direction()
        if direction == 1 and self.ema < slow_ma:
            return self.exit()
        if direction == -1 and self.ema > slow_ma:
            return self.exit()
        
    def compute_indicators(self):
        arr = np.array(self.prices)
        self.ema = self.compute_ema(self.ema, self.prices[-1], self.fast_window)
        slow_ma = self.compute_ma(arr, self.slow_window)
        htf_ma = self.compute_ma(arr, self.htf_window)
        
        return slow_ma, htf_ma

    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.ema = None
            return None

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
            "entry_time": self.ts,
            "entry_price": self.price,
            "stop_price": stop_price,
            "target_price": target_price,
            "session_open": self.opens[0],
            "session_low": min(self.lows),
            "session_high": max(self.highs),
            "volumes": self.volumes[-10:]
        }