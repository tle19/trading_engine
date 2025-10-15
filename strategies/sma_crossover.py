from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from strategies import Strategy, RiskManager
from utils import *

class SMACrossoverIndicator(Strategy):
    def __init__(self, symbol, fast_window=10, slow_window=20, htf_window=40, position_size=1.0, 
                 stop_loss=0.005, take_profit=0.0175, trailing_ratio=0.1, target=400, loss=200):
        super().__init__(symbol, position_size, stop_loss, take_profit, trailing_ratio)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        # if self.trade_window((9, 30), (9, 30)):
        #     print(self.ts)
        #     current_date = self.ts.date().strftime("%Y-%m-%d")
        #     self.historical_data = open_data(self.symbol, start_date="2024-10-01", end_date=(datetime.fromisoformat(current_date) - timedelta(days=1)).date().isoformat())
        #     self.detect_regime()

        status = self.check_status()
        if status is not None:
            return status
        
        if len(self.prices) < self.slow_window:
            return None
        if not self.trade_window((9, 30), (15, 00)):
            # self.risk_manager.reset_risk()
            return None
        
        if self.position is None:
            return self.enter_trade()
        else:
            self.set_trailing_stop_safe()
        return None
    
    def enter_trade(self):
        fast_ma = self.compute_ma(self.prices, self.fast_window)
        slow_ma = self.compute_ma(self.prices, self.slow_window)
        htf_ma = self.compute_ma(self.prices, self.htf_window)

        if fast_ma > slow_ma >= htf_ma and self.close < self.open:
            return self.buy()
        elif fast_ma < slow_ma <= htf_ma and self.close > self.open:
            return self.sell()

    def volatility_adjustment(self):
        # candle strength as well as direction
        # enter on low spread? high-low moving average
        # volume and volatility (np.std) confirmation?
        # avg_vol = self.compute_ma(self.volumes, self.slow_window)

        # if 0 == 0:
        #     self.stop_loss = 0.0125
        # elif 0 == 0:
        #     self.take_profit = 0.0125
        raise NotImplementedError

    def detect_regime(self):
        daily = self.historical_data.resample('1D', on='timestamp').agg({
            'open':'first',
            'high':'max',
            'low':'min',
            'close':'last',
            'volume':'sum'
                }).dropna()
        
        short_ma = daily['close'].iloc[-10:].mean()
        medium_ma  = daily['close'].iloc[-50:].mean()
        long_ma  = daily['close'].iloc[-100:].mean()
        diff_short_long = (short_ma - long_ma) / long_ma

        if diff_short_long > 0.03:
            regime = "STRONG_BULLISH" if short_ma > medium_ma else "MILD_BULLISH"
        elif 0 < diff_short_long <= 0.03:
            regime = "MILD_BULLISH"
        elif -0.01 <= diff_short_long <= 0.01:
            regime = "STAGNANT"
        elif -0.03 <= diff_short_long < 0:
            regime = "MILD_BEARISH"
        elif diff_short_long < -0.03:
            regime = "STRONG_BEARISH" if short_ma < medium_ma else "MILD_BEARISH"
            
        print(regime)
        if regime == "STRONG_BULLISH":
            self.fast_window = 10
            self.slow_window = 20
            self.htf_window = 40
            self.stop_loss = 0.005
            self.take_profit = 0.0175
            self.trailing_ratio = 0.1
        elif regime == "MILD_BULLISH":
            self.fast_window = 10
            self.slow_window = 20
            self.htf_window = 40
            self.stop_loss = 0.005
            self.take_profit = 0.0175
            self.trailing_ratio = 0.1
        elif regime == "STAGNANT":
            self.fast_window = 10
            self.slow_window = 20
            self.htf_window = 40
            self.stop_loss = 0.005
            self.take_profit = 0.0175
            self.trailing_ratio = 0.1
        elif regime == "MILD_BEARISH":
            self.fast_window = 10
            self.slow_window = 25
            self.htf_window = 50
            self.stop_loss = 0.01
            self.take_profit = 0.015
            self.trailing_ratio = 0.1
        elif regime == "STRONG_BEARISH":
            self.fast_window = 10
            self.slow_window = 30
            self.htf_window = 60
            self.stop_loss = 0.0125
            self.take_profit = 0.0125
            self.trailing_ratio = 0.1