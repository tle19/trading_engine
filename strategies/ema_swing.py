import numpy as np
import pandas as pd

from strategies import Strategy
from models import *
from utils import *

class EMASwing(Strategy):
    def __init__(self, symbol, fast_window=5, slow_window=10, htf_window=25, 
                 stop_loss=0.01, take_profit=0.03, position_size=1.0, trailing_ratio=0.15, pyramid=False, force_close=False):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid, force_close)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window

        self.ema = None

        self.df = pd.DataFrame()
        # construct daily df inside
    
    def generate_signal(self, row):
        self.update(row)
        self.minimum_computations()
        
        if self.trade_window((9, 30), (15, 57)):
            return None
        
        slow_ma, htf_ma = self.compute_indicators()

        signal = None
        if self.activated:
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade(slow_ma, htf_ma)
        return signal
    
    def enter_trade(self, slow_ma, htf_ma):
        signal = None
        if self.ema > slow_ma >= htf_ma:
            signal, _ = self.buy()
        # if self.ema < slow_ma <= htf_ma:
        #     signal, _ = self.sell()
        return signal
        
    def compute_indicators(self):
        arr = np.array(self.prices)
        self.ema = self.compute_ema(self.ema, self.prices[-1], self.fast_window)
        slow_ma = self.compute_ma(arr, self.slow_window)
        htf_ma = self.compute_ma(arr, self.htf_window)
        
        return slow_ma, htf_ma

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
        }