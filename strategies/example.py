import os
from datetime import datetime
from collections import deque
import pandas as pd
import numpy as np

from strategies import Strategy
from models import *
from utils import *

class SMACrossover(Strategy):
    def __init__(self, symbol, fast_window=10, slow_window=20, htf_window=50, 
                 stop_loss=0.01, take_profit=0.02, position_size=1.0, trailing_ratio=0.15, pyramid=False, force_close=True,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=3):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid, force_close,
                         pnl_target, pnl_loss, trade_max)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.htf_window = htf_window

        self.ema = None

        # open historical data (implement live backfill)
        df = open_data(self.symbol, start_date="2024-01-01", end_date="2026-01-01")
        self.history = resample_data(df)

        # meta labeling models
        self.model = XGBModel(symbol=symbol, live=True)
        if not self.model.initialize():
            self.model = None
        self.model2 = RFModel(symbol=symbol, live=True)
        if not self.model2.initialize():
            self.model2 = None
        self.model3 = KNNModel(symbol=symbol, live=True)
        if not self.model3.initialize():
            self.model3 = None
    
    def generate_signal(self, row, _=None):
        self.update(row)  # store OHLCV
        self.backfill_data() # backfill data if needed
        self.reset_data() # intraday data reset
        self.reset_day() # reset position manager and risk manager
        self.reset_indicators()
        self.minimum_computations() # ensure enough data for indicators
        
        # compute indicators
        slow_ma, htf_ma = self.compute_indicators()

        # end day after pnl target/loss
        if self.risk_manager._day_pause: 
            return None

        # set trading window
        if not self.trade_window((9, 30), (15, 59)) and not self.position_manager.in_trade():
            return None
        
        # enter/exit positions
        signal = None
        if self.activated:
            signal = self.exit_trade(slow_ma)
            if signal is None:
                signal = self.enter_trade(slow_ma, htf_ma)
        return signal
    
    def enter_trade(self, slow_ma, htf_ma):
        signal = None
        if self.ema > slow_ma >= htf_ma:
            signal, _ = self.buy()
        if self.ema < slow_ma <= htf_ma:
            signal, _ = self.sell()
        return signal
        
    def exit_trade(self, slow_ma):
        direction = self.position_manager.direction()
        # set trailing stop (optional)
        if direction == 1 and self.close > self.open or direction == -1 and self.close < self.open:
            self.set_trailing_stop()
        if direction == 1 and self.ema < slow_ma:
            return self.exit()
        if direction == -1 and self.ema > slow_ma:
            return self.exit()
        
    def compute_indicators(self):
        arr = np.array(self.closes)
        self.ema = self.compute_ema(self.ema, self.close, self.fast_window)
        slow_ma = self.compute_ma(arr, self.slow_window)
        htf_ma = self.compute_ma(arr, self.htf_window)
        
        return slow_ma, htf_ma

    def reset_indicators(self, reset_time=(9, 30)):
        if self.trade_window(reset_time, reset_time):
            self.ema = None
            
            if self.d_closes:
                self.prev_day_close = self.d_closes[-1]
                self.regime_ema = self.compute_ma(self.d_closes, window=50)
                self.adx = self.compute_adx(self.d_highs, self.d_lows, self.d_closes)
                self.atr = self.compute_atr(self.d_highs, self.d_lows, self.d_closes)
                
    def backfill_data(self):
        if not self.back_filled:
            df = open_data(self.symbol, start_time="9:30", end_time="15:59")
            df = df[df['timestamp'] < self.ts]
            last_trading_day = df['timestamp'].dt.date.max()
            df = df[df['timestamp'].dt.date == last_trading_day]
            if not df.empty:
                print("No Backfill")
            else:
                print("Backfilled")
            self.back_filled = True

    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.fast_window,
                self.slow_window,
                self.htf_window
            ) + 1
            self.activated = len(self.closes) > required_data

    def predict_trade(self, threshold=0.4):
        df = pd.DataFrame(self.features)
        self.model.prepare_features(df)
        proba = self.model.get_proba()

        if self.signal == 1:
            if proba > threshold:
                self.position_size = 1.0
            else:
                self.position_size = 0.5
            signal, leg = self.buy() 
        elif self.signal == -1:
            if proba > threshold:
                self.position_size = 1.0
            else:
                self.position_size = 0.5
            signal, leg = self.sell() 

        return signal, leg

    def add_features(self, direction, stop_price, target_price):
        self.features = {
            "direction": direction,
            "entry_time": self.ts.isoformat(),
            "entry_price": self.close,
            "stop_price": stop_price,
            "target_price": target_price,
            "session_open": self.opens[0],
            "session_low": min(self.lows),
            "session_high": max(self.highs),
            "open_volume": sum(self.volumes[0:5]),
            "prev_day_close": self.prev_day_close,
            "ema": self.regime_ema,
            "adx": self.adx,
            "atr": self.atr,
        }