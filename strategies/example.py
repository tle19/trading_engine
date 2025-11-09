from strategies import Strategy, RiskManager

class ExampleIndicator(Strategy):
    def __init__(self, symbol, stop_loss=0.01, take_profit=0.02, 
                 trailing_ratio=0.15, position_size=1.0, target=0.01, loss=-0.01, 
                 risk_threshold=3, pause_duration=5, trade_max=3):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size)
        
        self.risk_manager = RiskManager(pnl_target=target, 
                                        pnl_loss=loss, 
                                        risk_threshold=risk_threshold, 
                                        pause_duration=pause_duration,
                                        trade_max=trade_max)
    
    def generate_signal(self, row):
        self.update(row)  # store OHLCV
        self.reset_data() # intraday data reset

        status = self.check_status() # close positions
        if status is not None:
            return status
        
        self.risk_manager.check_daily_target()
        self.risk_manager.check_daily_stop()
        if self.risk_manager.day_pause(): # day end early
            return None
        
        if self.risk_manager.intraday_pause(): # intraday risk factor
            self.risk_manager.tick()
            return None
        
        if not self.trade_window((9, 30), (12, 30)) and self.position is None:
            return None
        
        signal = None
        if self.position is None and self.activated:
            signal = self.enter_trade()
        elif self.position is not None:
            signal = self.exit_trade()
            self.set_trailing_stop()
        return signal
    
    def enter_trade(self):
        if self.open > self.close:
            return self.buy()
        elif self.open < self.close:
            return self.sell()
        
    def exit_trade(self):
        if self.close > self.entry_price:
            return self.sell()
        elif self.close < self.entry_price:
            return self.buy()
    
    def reset_indicators(self):
        raise NotImplementedError
        
    def minimum_computations(self):
        raise NotImplementedError
    
    def train(self):
        return NotImplementedError