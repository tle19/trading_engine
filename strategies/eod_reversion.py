from collections import deque
import pandas as pd
import numpy as np

from strategies import Strategy
from models import *
from utils import *

class EODReversion(Strategy):
    def __init__(self, symbol, orb_window=1, fast_window=10, slow_window=20, atr_diff=0.2, adx_diff=5,
                 stop_loss=0.01, take_profit=0.01, position_size=1.0, trailing_ratio=0.05, pyramid=True, force_close=True,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=1, drawdown_max=0.20):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid, force_close,
                         pnl_target, pnl_loss, trade_max, drawdown_max)
        self.orb_window = orb_window
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.atr_diff = atr_diff
        self.adx_diff = adx_diff

        self.upper_support = None
        self.lower_support = None
        self.fast_ema = None
        self.slow_ema = None

        self.weighted_pressure = []
        self.rolling_atr = []
        self.rolling_adx = []
        self.prev_day_atr_mean = 0.0
        self.prev_day_adx_mean = 0.0

        self.prev_day_close = None
        self.regime_ema = None
        self.adx = None
        self.atr = None

        self.model = XGBModel(symbol=symbol, live=True)
        if not self.model.initialize():
            self.model = None

    def generate_signal(self, row, _=None):
        self.update(row)
        self.backfill_data()
        self.reset_data()
        self.reset_day()
        self.reset_indicators()
        self.minimum_computations()
        
        self.compute_indicators()

        if self.risk_manager._day_pause:
            return None

        if not self.trade_window((15, 00), (15, 45)) and not self.position_manager.in_trade():
            return None
        
        signal = None
        if self.activated:
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade()
        return signal
    
    def enter_trade(self):
        signal = None

        self.atr_cond = np.mean(self.rolling_atr) - self.prev_day_atr_mean < self.atr_diff
        # self.adx_cond = np.mean(self.rolling_adx) - self.prev_day_adx_mean < self.adx_diff

        if self.atr_cond and not self.position_manager.in_trade():
            if self.close < self.lower_support:
                if self.pressure < 0 and self.close < self.fast_ema: # and self.compute_ma(self.weighted_pressure, 3) > self.compute_ma(self.weighted_pressure, 5)
                    signal, _ = self.buy()
                    self.prev_day_atr_mean = np.mean(self.rolling_atr)
                    # self.prev_day_adx_mean = np.mean(self.rolling_adx)
            if self.close > self.upper_support:
                if self.pressure > 0 and self.close > self.fast_ema: # and self.compute_ma(self.weighted_pressure, 3) < self.compute_ma(self.weighted_pressure, 3)
                    signal, _ = self.sell()
                    self.prev_day_atr_mean = np.mean(self.rolling_atr)
                    # self.prev_day_adx_mean = np.mean(self.rolling_adx)
        return signal
    
    # def exit_trade(self):
    #     for leg in self.position_manager.legs:
    #         diff = leg.target_price - leg.entry_price
    #         if leg.direction == 1:
    #             if self.price >= leg.entry_price + 0.75 * diff:
    #                 leg.stop_price = leg.entry_price + 0.25 * diff
    #         elif leg.direction == -1:
    #             if self.price <= leg.entry_price + 0.75 * diff:
    #                 leg.stop_price = leg.entry_price + 0.25 * diff
    #     return self.exit()
    
    def compute_indicators(self):
        self.fast_ema = self.compute_ema(self.fast_ema, self.prices[-1], self.fast_window)
        self.slow_ema = self.compute_ema(self.slow_ema, self.prices[-1], self.slow_window)
        self.weighted_pressure.append((self.close - self.open) * self.volume)
        self.rolling_atr.append(self.compute_atr(self.highs, self.lows, self.closes))
        # self.rolling_adx.append(self.compute_adx(self.highs, self.lows, self.closes))
        self.rolling_adx.append(1)
        self.pressure = sum(self.weighted_pressure)

    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.upper_support = None
            self.lower_support = None
            self.fast_ema = None
            self.slow_ema = None

            if self.d_closes:
                self.prev_day_close = self.d_closes[-1]
                self.regime_ema = self.compute_ma(self.d_closes, window=50)
                self.prev_day_adx_mean = np.mean(self.rolling_adx)
                # self.prev_day_atr_mean = np.mean(self.rolling_atr)
                self.adx = self.compute_adx(self.d_highs, self.d_lows, self.d_closes)
                self.atr = self.compute_atr(self.d_highs, self.d_lows, self.d_closes)

            self.weighted_pressure = []
            self.rolling_atr = []
            self.rolling_adx = []

    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.orb_window,
                self.fast_window,
                self.slow_window,
            ) + 1
            self.upper_support, self.lower_support = self.donchian_channel(self.orb_window)
            self.activated = len(self.prices) > required_data

    def backfill_data(self):
        if not self.back_filled:
            df = open_data(self.symbol, start_time="9:30", end_time="15:00")
            df = df[df['timestamp'] < self.ts]
            last_trading_day = df['timestamp'].dt.date.max()
            df = df[df['timestamp'].dt.date == last_trading_day]
            if not df.empty:
                atr = self.compute_atr(df['high'], df['low'], df['close'])
                adx = self.compute_adx(df['high'], df['low'], df['close'])
                self.prev_day_atr_mean = np.mean(atr)
                self.prev_day_adx_mean = np.mean(adx)
            else:
                self.prev_day_atr_mean = 0.25
                self.prev_day_adx_mean = 3
            self.back_filled = True
    
    def predict_trade(self, threshold=0.4):
        df = pd.DataFrame([self.features])
        self.model.prepare_features(df)
        proba = self.model.get_proba()

        if self.pressure < 0 and self.close < self.lower_support and self.close < self.fast_ema and self.atr_cond:
            if proba > threshold:
                self.position_size = 1.0
            else:
                self.position_size = 0.75
            signal, leg = self.buy() 
        elif self.pressure > 0 and self.close > self.upper_support and self.close > self.fast_ema and self.atr_cond:
            if proba > threshold:
                self.position_size = 1.0
            else:
                self.position_size = 0.75
            signal, leg = self.sell() 

        # if self.pressure < 0 and self.close < self.lower_support and self.close < self.fast_ema and self.atr_cond:
        #     if proba > threshold:
        #         signal, leg = self.buy() 
        #         confidence = proba
        #     else:
        #         signal, leg = self.sell() 
        #         confidence = 1 - proba
        # elif self.pressure > 0 and self.close > self.upper_support and self.close > self.fast_ema and self.atr_cond:
        #     if proba > threshold:
        #         signal, leg = self.sell()
        #         confidence = proba
        #     else:
        #         signal, leg = self.buy() 
        #         confidence = 1 - proba

        # self.position_size = 0.25 + 0.75 * confidence     
        return signal, leg
            
    def add_features(self, direction, stop_price, target_price):
        self.features = {
            "direction": direction,
            "entry_time": self.ts.isoformat(),
            "entry_price": self.price,
            "stop_price": stop_price,
            "target_price": target_price,
            "session_open": self.opens[0],
            "session_low": min(self.lows),
            "session_high": max(self.highs),
            "open_volume": sum(self.volumes[0:15]),
            "prev_day_close": self.prev_day_close,
            "ema": self.regime_ema,
            "adx": self.adx,
            "atr": self.atr,
            "upper_support": self.upper_support,
            "lower_support": self.lower_support,
            "pressure": self.pressure,
            "curr_day_atr_mean": np.mean(self.rolling_atr), 
            "prev_day_atr_mean": self.prev_day_atr_mean,
            "curr_day_adx_mean": np.mean(self.rolling_adx), 
            "prev_day_adx_mean": self.prev_day_adx_mean,
            "original_dir": 1 if self.pressure < 0 else -1
        }

    def param_grid(self):
        params = {
            "orb_window": [1], # 1, 2, 3, 4, 5, 10, 15, 30, 45, 60
            "fast_window": [5, 8, 10, 15, 20, 25, 30], # 5, 8, 10
            "slow_window": [7, 8, 9, 10, 11, 12], # 10, 15, 20, 25
            "atr_diff": [0.20], # 0.05, 0.10, 0.15, 0.20, 0.25, 0.30
            "stop_loss": [0.01], # 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015
            "take_profit": [0.01], # 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015
            "drawdown_max": [0.20]
        }
        return params