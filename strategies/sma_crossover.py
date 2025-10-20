from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from strategies import Strategy, RiskManager
from core import DataHandler
from utils import *

class SMACrossoverIndicator(Strategy):
    def __init__(self, symbol, fast_window=10, slow_window=20, htf_window=40, position_size=1.0, 
                 stop_loss=0.005, take_profit=0.005, trailing_ratio=0.1, 
                 target=0.02, loss=-0.01, force_close=True):
        super().__init__(symbol, position_size, stop_loss, take_profit, trailing_ratio, force_close)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)
    
    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        # if self.trade_window((9, 30), (9, 30)):
        #     self.detect_regime()

        status = self.check_status(self.force_close)
        if status is not None:
            return status
        
        # self.risk_manager.daily_risk_stop()
        # if self.risk_manager.is_day_pause():
        #     return None

        if len(self.prices) < self.slow_window:
            return None
        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
            # if self.trade_window((15, 59), (15, 59)):
            #     print(self.risk_manager.pnl) #sanity check
            return None
        
        if self.position is None:
            return self.enter_trade()
        else:
            self.set_trailing_stop_safe()
            # after certain amount of holding time 
            # and price is below entry, begin moving profit and/or stop
            # donchian channel ?
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
        # normalizing for volatility to make standard across stocks
        # average volatility on past data
        # candle strength as well as direction
        # enter on low spread? high-low moving average
        # volume and volatility (np.std) confirmation?
        # avg_vol = self.compute_ma(self.volumes, self.slow_window)
        # low range should tighten stop/profit
        
        # if 0 == 0:
        #     self.stop_loss = 0.0125
        #     self.take_profit = 0.0125
        # elif 0 == 0:
        #     self.stop_loss = 0.0125
        #     self.take_profit = 0.0125
        raise NotImplementedError
    
    def detect_regime(self):  
        # consider market regime and stock regime for taking only longs/shorts respectively
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
            # self.slow_window = 20
            # self.htf_window = 40
            self.stop_loss = 0.01
            self.take_profit = 0.02
            self.trailing_ratio = 0.15
        elif regime == "TRANSITION":
            self.fast_window = 10
            # self.slow_window = 20
            # self.htf_window = 45
            self.stop_loss = 0.0125
            self.take_profit = 0.0175
            self.trailing_ratio = 0.15
        elif regime == "BEARISH":
            self.fast_window = 10
            self.slow_window = 25
            self.htf_window = 70
            self.stop_loss = 0.015
            self.take_profit = 0.015
            self.trailing_ratio = 0.15