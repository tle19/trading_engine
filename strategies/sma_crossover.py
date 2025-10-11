from strategies import Strategy, RiskManager
import numpy as np

class SMACrossoverIndicator(Strategy):
    def __init__(self, symbol, fast_window=10, slow_window=20, htf_window=40, position_size=1.0, 
                 stop_loss=0.005, take_profit=0.015, trailing_ratio=0.2, 
                 rt=5, pd=7, target=200, loss=250):
        super().__init__(symbol, position_size, stop_loss, take_profit, trailing_ratio)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window

        self.risk_manager = RiskManager(risk_threshold=rt, pause_duration=pd, 
                                        pnl_target=target, pnl_loss=loss)
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data()

        status = self.check_status()
        if status is not None:
            return status
        
        if len(self.prices) < self.slow_window:
            return None
        if not self.trade_window((9, 30), (15, 30)):
            self.risk_manager.reset_risk()
            return None

        self.risk_manager.intraday_risk()
        self.position_size = self.risk_manager.dynamic_position_sizing(self.default_position_size)
        if self.risk_manager.is_day_stop():
            return None
        if self.risk_manager.is_paused():
            self.risk_manager.tick()
            return None
        
        if self.position is None:
            return self.enter_trade()
        else:
            self.set_trailing_stop_safe()
        return None
    
    def enter_trade(self):
        # avg_vol = self.compute_ma(self.volumes, self.slow_window)
        fast_ma = self.compute_ma(self.prices, self.fast_window)
        slow_ma = self.compute_ma(self.prices, self.slow_window)
        htf_ma = self.compute_ma(self.prices, self.htf_window)

        trend_strength = abs(fast_ma - slow_ma)
        min_trend = 0.01
        if trend_strength < min_trend:
            return None
        
        if fast_ma > slow_ma >= htf_ma:
            return self.buy()
        elif fast_ma < slow_ma <= htf_ma:
            return self.sell()