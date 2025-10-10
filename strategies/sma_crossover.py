from strategies import Strategy
import numpy as np

class SMACrossoverIndicator(Strategy):
    def __init__(self, symbol, fast_window=10, slow_window=20, position_size=1.0, 
                 stop_loss=0.005, take_profit=0.015, trailing_ratio=0.2):
        super().__init__(symbol, position_size, stop_loss, take_profit, trailing_ratio)
        self.fast_window = fast_window
        self.slow_window = slow_window
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data()

        status = self.check_status()
        if status is not None:
            return status
        
        if len(self.prices) < self.slow_window:
            return None
        if not self.trade_window((9, 30), (15, 30)):
            return None

        self.check_risk()
        # if self.pause:
        #     self.risk_timer()
        #     return None
        
        fast_ma = self.compute_ma(self.fast_window)
        slow_ma = self.compute_ma(self.slow_window)

        # --- Entry logic ---
        if self.position is None:
            if fast_ma > slow_ma:
                return self.buy()
            elif fast_ma < slow_ma:
                return self.sell()

        self.set_trailing_stop_safe()
        return None
