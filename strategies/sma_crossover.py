import numpy as np
from strategies import Strategy, RiskManager

class SMACrossoverIndicator(Strategy):
    def __init__(self, symbol, fast_window=10, slow_window=20, htf_window=50, donch_smoothing=0.3, 
                 rsi_period=5, rsi_lower=35, rsi_upper=70,
                 stop_loss=0.003, take_profit=0.003, trailing_ratio=0.05, position_size=1.0,
                 target=0.015, loss=-0.015, force_close=True):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, force_close)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window
        self.donch_smoothing = donch_smoothing
        self.rsi_period = rsi_period
        self.rsi_lower = rsi_lower
        self.rsi_upper = rsi_upper
        
        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data()

        status = self.check_status()
        if status is not None:
            self.hold_time = 0
            return status

        self.risk_manager.daily_risk_target()
        self.risk_manager.daily_risk_stop()
        if self.risk_manager.is_day_pause():
            return None
        
        if len(self.prices) < self.slow_window:
            return None
        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
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
        rsi = self.compute_rsi(arr, self.rsi_period)

        if fast_ma > slow_ma >= htf_ma:
            if rsi <= self.rsi_lower and self.close < self.open:
                self.donchian_range(self.htf_window, htf_ma, "long")
                return self.buy()

        elif fast_ma < slow_ma <= htf_ma:
            if rsi >= self.rsi_upper and self.close > self.open:
                self.donchian_range(self.htf_window, htf_ma, "short")
                return self.sell()

    def donchian_range(self, window, ma, position=None):
        upper_band, lower_band = self.donchian_channel(window)
        upper_pct = (upper_band / ma) - 1
        lower_pct = (ma / lower_band) - 1
        donch_range = upper_band - lower_band

        smoothed_upper = (1 - self.donch_smoothing) * upper_pct + self.donch_smoothing * lower_pct
        smoothed_lower = (1 - self.donch_smoothing) * lower_pct + self.donch_smoothing * upper_pct

        smoothed_upper = max(min(smoothed_upper, 0.01), 0.003)
        smoothed_lower = max(min(smoothed_lower, 0.01), 0.003)

        if position == "long":
            self.stop_loss = smoothed_lower
            self.take_profit = smoothed_upper
        if position == "short":
            self.stop_loss = smoothed_upper
            self.take_profit = smoothed_lower
        self.trailing_ratio = donch_range / window