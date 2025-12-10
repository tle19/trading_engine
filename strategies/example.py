import numpy as np

from strategies import Strategy, RiskManager
from utils import *

class SMACrossover(Strategy):
    def __init__(self, symbol, fast_window=10, slow_window=20, htf_window=50, 
                 stop_loss=0.01, take_profit=0.02, trailing_ratio=0.15, 
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=3):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window

        self.ema = None
        
        self.risk_manager = RiskManager(pnl_target, pnl_loss, trade_max)
    
    def generate_signal(self, row):
        self.update(row)  # store OHLCV
        self.reset_data() # intraday data reset
        self.reset_indicators()
        self.minimum_computations() # ensure enough data for indicators
        
        # compute indicators
        arr = np.array(self.prices)
        fast_ma = self.compute_ma(arr, self.fast_window)
        slow_ma = self.compute_ma(arr, self.slow_window)
        self.ema = self.compute_ema(self.ema, self.prices[-1], self.htf_window)

        # end day after pnl target/loss
        if self.risk_manager.day_pause(): 
            return None

        # set trading window
        if not self.trade_window((9, 30), (16, 00)) and self.position is None:
            return None
        
        # enter/exit positions
        signal = None
        if self.position is None and self.activated:
            signal = self.enter_trade(fast_ma, slow_ma)
        elif self.position is not None:
            signal = self.exit_trade(fast_ma, slow_ma)
        return signal
    
    def enter_trade(self, fast_ma, slow_ma):
        if fast_ma > slow_ma >= self.ema:
            return self.buy()
        if fast_ma < slow_ma <= self.ema:
            return self.sell()
        
    def exit_trade(self, fast_ma, slow_ma):
        # check position sl/tp
        status = self.check_status()
        if status is not None:
            return status
        
        # additional exit logic
        if fast_ma < slow_ma:
            return self.sell()
        elif fast_ma > slow_ma:
            return self.buy()
        
        self.set_trailing_stop()
    
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

    def train(self):
        return NotImplementedError