import numpy as np
from datetime import timedelta

from strategies import Strategy, RiskManager
from utils import *

class SMACrossoverIndicator(Strategy):
    def __init__(self, symbol, fast_window=10, slow_window=20, htf_window=50, 
                 rsi_period=6, rsi_lower=30, rsi_upper=70,
                 stop_loss=0.01, take_profit=0.01, trailing_ratio=0.05, position_size=1.0,
                 target=0.0000000001, loss=-0.0000000001, force_close=True):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, force_close)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window
        self.rsi_period = rsi_period
        self.rsi_lower = rsi_lower
        self.rsi_upper = rsi_upper
        
        self.prev_closes = None
        self.mode = None
        self.prev_rsi = None
        
        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss, pause_duration=390)
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data()

        self.short_term_regime()
        # self.mode = "both"

        status = self.check_status()
        if status is not None:
            return status

        self.risk_manager.daily_risk_target()
        self.risk_manager.daily_risk_stop()
        if self.risk_manager.is_day_pause():
            return None
        
        # self.risk_manager.intraday_risk()
        # if self.risk_manager.is_trade_pause():
        #     self.risk_manager.tick()
        #     return None
        
        if len(self.prices) < self.slow_window:
            return None
        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
            self.mode = None
            return None
        
        if self.position is None:
            return self.enter_trade()
        else:
            if self.position == "long" and self.stop_price <= self.entry_price:
                if self.close > self.entry_price * 1.0025:
                    self.stop_price = self.entry_price * 0.9975
            if self.position == "short" and self.stop_price >= self.entry_price:
                if self.close < self.entry_price * 0.9975:
                    self.stop_price = self.entry_price * 1.0025
            self.set_trailing_stop()
        return None
    
    def enter_trade(self):
        arr = np.array(self.prices)
        fast_ma = self.compute_ma(arr, self.fast_window)
        slow_ma = self.compute_ma(arr, self.slow_window)
        htf_ma = self.compute_ma(arr, self.htf_window)
        rsi = self.compute_rsi(arr, self.rsi_period)

        if self.mode == "long":
            if fast_ma > slow_ma >= htf_ma:
                if rsi <= self.rsi_lower and self.close < self.open:
                    # self.donchian_range(self.htf_window, htf_ma, "long")
                    return self.buy()
        
        elif self.mode == "short":
            if fast_ma < slow_ma <= htf_ma:
                if rsi >= self.rsi_upper and self.close > self.open:
                    # self.donchian_range(self.htf_window, htf_ma, "short")
                    return self.sell()
                
        elif self.mode == "both":
            if fast_ma > slow_ma >= htf_ma:
                if rsi <= self.rsi_lower and self.close < self.open:
                    # self.donchian_range(self.htf_window, htf_ma, "long")
                    return self.buy()
            if fast_ma < slow_ma <= htf_ma:
                if rsi >= self.rsi_upper and self.close > self.open:
                    # self.donchian_range(self.htf_window, htf_ma, "short")
                    return self.sell()

    def donchian_range(self, window, ma, position=None, rr_ratio=1.0):
        upper_band, lower_band = self.donchian_channel(window)
        norm_range = (upper_band - lower_band) / ma
        base_risk = min(max(norm_range * 0.5, 0.0075), 0.01)
        base_reward = base_risk * rr_ratio

        if position == "long":
            self.stop_loss = base_risk
            self.take_profit = base_reward
        elif position == "short":
            self.stop_loss = base_risk
            self.take_profit = base_reward

    def short_term_regime(self):
        if self.trade_window((9, 30), (9, 30)):
            end_date = self.ts.date()
            start_date = end_date - timedelta(days=30)
            df = open_data(self.symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            df.set_index('timestamp', inplace=True)
            df = df.resample('1D', offset='9h30min').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last'
            }).dropna()

            self.prev_closes = df['open'].iloc[-15:].tolist()
            self.prev_rsi = self.compute_rsi(self.prev_closes, 10)

        price_series = np.append(self.prev_closes, self.open)

        prev_rsi = self.prev_rsi
        rsi = self.compute_rsi(price_series, 10)

        neutral_band = 5
        rsi_upper = 80
        rsi_lower = 20
        if rsi >= rsi_upper:
            self.mode = "short"
        elif rsi <= rsi_lower:
            self.mode = "long"
        elif rsi > prev_rsi + neutral_band:
            self.mode = "long"
        elif rsi < prev_rsi - neutral_band:
            self.mode = "short"
        else:
            self.mode = "both"

        
            