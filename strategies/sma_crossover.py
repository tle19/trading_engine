from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from strategies import Strategy, RiskManager
from core import DataHandler
from utils import *

class SMACrossoverIndicator(Strategy):
    def __init__(self, symbol, fast_window=10, slow_window=20, htf_window=40, donch_smoothing=0.7, 
                 stop_loss=0.003, take_profit=0.003, trailing_ratio=0.1, position_size=1.0,
                 target=0.03, loss=-0.03, force_close=True):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, force_close)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window
        self.donch_smoothing = donch_smoothing

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        # if self.trade_window((9, 30), (9, 30)):
        #     self.detect_regime()

        status = self.check_status()
        if status is not None:
            return status

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
            # after certain amount of holding time 
            # and price is below entry, begin moving profit and/or stop
        return None
    
    def enter_trade(self):
        arr = np.array(self.prices)
        fast_ma = self.compute_ma(arr, self.fast_window)
        slow_ma = self.compute_ma(arr, self.slow_window)
        htf_ma = self.compute_ma(arr, self.htf_window)
        
        if fast_ma > slow_ma >= htf_ma and self.close < self.open:
            self.donchian_range(self.htf_window, htf_ma, "long")
            return self.buy()
        elif fast_ma < slow_ma <= htf_ma and self.close > self.open:
            self.donchian_range(self.htf_window, htf_ma, "short")
            return self.sell()

    def donchian_range(self, window, ma, position=None):
        upper_band, lower_band = self.donchian_channel(self.highs, self.lows, window)
        upper_pct = (upper_band / ma) - 1
        lower_pct = (ma / lower_band) - 1
        donch_range = upper_band - lower_band

        smoothed_upper = (1 - self.donch_smoothing) * upper_pct + self.donch_smoothing * lower_pct
        smoothed_lower = (1 - self.donch_smoothing) * lower_pct + self.donch_smoothing * upper_pct

        smoothed_upper = max(min(smoothed_upper, 0.01), 0.002)
        smoothed_lower = max(min(smoothed_lower, 0.01), 0.002)

        if position == "long":
            self.stop_loss = smoothed_lower
            self.take_profit = smoothed_upper
        if position == "short":
            self.stop_loss = smoothed_upper
            self.take_profit = smoothed_lower
        self.trailing_ratio = min(donch_range / window, 0.05)
    
    def donchian_channel(self, highs, lows, window):
        upper_band = max(highs[-window:])
        lower_band = min(lows[-window:])
        return upper_band, lower_band

    def detect_regime(self):  
        current_date = self.ts.date().strftime("%Y-%m-%d")
        data = open_data("SPY", start_date="2023-10-01", end_date=(datetime.fromisoformat(current_date) - timedelta(days=1)).date().isoformat())
        daily = data.resample('1D', on='timestamp').agg({
            'open':'first',
            'high':'max',
            'low':'min',
            'close':'last',
            'volume':'sum'
                }).dropna()
        
        # dh = DataHandler()
        # data = dh.schwab_data("SPY", end_date=current_date)

        short_ma = daily['close'].iloc[-10:].mean()
        medium_ma  = daily['close'].iloc[-40:].mean()
        long_ma  = daily['close'].iloc[-80:].mean()
        diff_short_long = (short_ma - long_ma) / long_ma
        regime = None

        if short_ma > medium_ma > long_ma and diff_short_long > 0.015:
            regime = "BULLISH"
        elif short_ma < medium_ma < long_ma and diff_short_long < -0.015:
            regime = "BEARISH"
        else:
            regime = "TRANSITION"
        
        # print(self.ts.date())
        # print(regime) #sanity check

        self.select_regime(regime)

    def select_regime(self, regime):
        if regime == "BULLISH":
            self.fast_window = 10
            self.slow_window = 20
            self.htf_window = 40
        elif regime == "TRANSITION":
            self.fast_window = 10
            self.slow_window = 20
            self.htf_window = 45
        elif regime == "BEARISH":
            self.fast_window = 10
            self.slow_window = 25
            self.htf_window = 70