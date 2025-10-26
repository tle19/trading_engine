import numpy as np
from strategies import Strategy, RiskManager

class TrendFollowIndicator(Strategy):
    def __init__(self, symbol, fast_window=30, slow_window=80, htf_window=120,
                 stop_loss=0.0125, take_profit=0.0125, trailing_ratio=0.1, position_size=1.0,
                 target=0.0001, loss=-0.0001, force_close=True):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, force_close)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window
        
        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data()

        status = self.check_status()
        if status is not None:
            return status

        self.risk_manager.daily_risk_target()
        self.risk_manager.daily_risk_stop()
        if self.risk_manager.is_day_pause():
            return None
        
        if len(self.prices) < self.htf_window:
            return None
        
        if self.position is None:
            return self.enter_trade()
        else:
            self.set_trailing_stop()
        return None
    
    def enter_trade(self):
        arr = np.array(self.prices)
        fast_ma = self.compute_ma(arr, self.fast_window)
        slow_ma = self.compute_ma(arr, self.slow_window)
        htf_ma = self.compute_ma(arr, self.htf_window)

        if fast_ma > slow_ma >= htf_ma:
            return self.buy()

        elif fast_ma < slow_ma <= htf_ma:
            return self.sell()