import numpy as np
from strategies import Strategy, RiskManager

class TrendFollowIndicator(Strategy):
    def __init__(self, symbol, stop_loss=0.0125, take_profit=0.0125, trailing_ratio=0.1, 
                 position_size=1.0, target=0.0001, loss=-0.0001, risk_threshold=3, pause_duration=5):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size)
        
        self.risk_manager = RiskManager(pnl_target=target, 
                                        pnl_loss=loss, 
                                        risk_threshold=risk_threshold, 
                                        pause_duration=pause_duration)
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data() # optional

        status = self.check_status()
        if status is not None:
            return status
        
        self.position_size = self.risk_manager.dynamic_position_sizing(self.default_position_size) # optional

        self.risk_manager.daily_risk_target() # optional   
        self.risk_manager.daily_risk_stop() # optional
        if self.risk_manager.is_day_pause(): # optional
            return None
        
        self.risk_manager.intraday_risk() # optional
        if self.risk_manager.is_trade_pause(): # optional
            self.risk_manager.tick() # optional
            return None
        
        if self.position is None:
            return self.enter_trade()
        else:
            self.set_trailing_stop() # optional
    
    def enter_trade(self):
        if self.open > self.close:
            return self.buy()
        elif self.open < self.close:
            return self.sell()
        
    def exit_trade(self):
        if self.close > self.entry_price * 1.5:
            return self.buy()
        elif self.close < self.entry_price * 1.5:
            return self.sell()
    
    def train(self):
        return NotImplementedError