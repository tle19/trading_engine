import numpy as np
from strategies import Strategy, RiskManager

class MomentumSMAIndicator(Strategy):
    def __init__(self, symbol, momentum_window=10, sma_window=8, 
                 rsi_period=8, rsi_lower=30, rsi_upper=70,
                 stop_loss=0.01, take_profit=0.01, trailing_ratio=0.5, position_size=1.0,
                 target=0.03, loss=-0.03, force_close=True):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, force_close)
        self.momentum_window = momentum_window
        self.sma_window = sma_window
        self.rsi_period = rsi_period
        self.rsi_lower = rsi_lower
        self.rsi_upper = rsi_upper

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
        
        if len(self.prices) <= self.momentum_window + self.sma_window:
            return None

        if self.position is None:
            return self.enter_trade()
        else:
            self.set_trailing_stop()
        return None
    
    def enter_trade(self):
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        momentum, sma_momentum = self.compute_momentum_sma()
        if rsi < self.rsi_lower and momentum > sma_momentum:
            return self.buy()
        elif rsi > self.rsi_upper and momentum < sma_momentum:
            return self.sell()
    
    def compute_momentum_sma(self):
        momentum = self.prices[-1] - self.prices[-1 - self.momentum_window]

        momentum_history = [
            self.prices[i] - self.prices[i - self.momentum_window]
            for i in range(-self.sma_window, 0)
        ]
        sma_momentum = np.mean(momentum_history)

        return momentum, sma_momentum