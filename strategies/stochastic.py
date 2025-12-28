from collections import deque
import pandas as pd

from models import XGBModel
from strategies import Strategy
from utils import *

class StochasticIndicator(Strategy):
    def __init__(self, symbol, fast_window=12, slow_window=26, signal_window=9,
                 rsi_period=14, k_period=14, k_smooth=3, d_period=3, stoch_lower=20, stoch_upper=80,
                 vol_fast_window=14, vol_slow_window=28, vol_threshold=0.0, atr_window=14, adx_window=14,
                 stop_loss=0.01, take_profit=0.01, position_size=1.0, trailing_ratio=0.05, pyramid=False,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=2):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid,
                         pnl_target, pnl_loss, trade_max)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.rsi_period = rsi_period
        self.k_period = k_period
        self.k_smooth = k_smooth
        self.d_period = d_period
        self.stoch_lower = stoch_lower
        self.stoch_upper = stoch_upper
        self.vol_fast_window = vol_fast_window
        self.vol_slow_window = vol_slow_window
        self.vol_threshold = vol_threshold
        self.atr_window = atr_window
        self.adx_window = adx_window

        self.ema = None
        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None
        self.stoch_signal = None

        self.rolling_rsi = deque(maxlen=10)
        self.rolling_vol = deque(maxlen=10)

        df = open_data(self.symbol, start_date="2023-11-01", end_date="2025-11-01")
        self.history = resample_data(df)
        self.rolling_adx = deque(maxlen=10)
        self.rolling_atr = deque(maxlen=10)
        
        self.model = XGBModel(live=True)
        if not self.model.initialize():
            self.model = None

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()

        k, d, rsi, hist, vol = self.compute_indicators()
        
        # if self.risk_manager._day_pause: 
        #     return None
        if not self.trade_window((9, 30), (15, 30)) and not self.position_manager.in_trade():
            return None
        
        signal = None
        if self.activated:
            self.compute_signal_direction(k, d)
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade(rsi, hist, vol)
        self.prev_hist = hist
        return signal
    
    def enter_trade(self, rsi, hist, vol):
        signal = None
        rsi_ma = sum(self.rolling_rsi) / len(self.rolling_rsi)
        vol_ma = sum(self.rolling_vol) / len(self.rolling_vol)
        
        if self.stoch_signal == 1 and rsi > 55 and rsi > rsi_ma and hist > 0 and vol > self.vol_threshold:
            signal, _ = self.buy()
            # signal, _ = self.sell()
        if self.stoch_signal == -1 and rsi < 45 and rsi < rsi_ma and hist < 0 and vol > self.vol_threshold:
            signal, _ = self.sell()
            # signal, _ = self.buy()
        return signal

    def compute_indicators(self):
        self.k, self.d = self.compute_stochastic(self.highs, self.lows, self.closes, self.k_period, self.k_smooth, self.d_period)
        self.rsi = self.compute_rsi(self.prices, self.rsi_period)
        self.hist, _, _ = self.compute_macd(self.fast_window, self.slow_window, self.signal_window)
        vol = self.compute_volume_oscillator(self.volumes, self.vol_fast_window, self.vol_slow_window)

        self.rolling_rsi.append(self.rsi)
        self.rolling_vol.append(vol)

        return self.k, self.d, self.rsi, self.hist, vol

    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.ema = None
            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
            self.stoch_signal = None
            self.rolling_rsi = deque(maxlen=10)
            self.rolling_vol = deque(maxlen=10)
            
            history = self.history.loc[self.history.index < self.ts.normalize()].tail(20)
            highs = history["high"].values
            lows = history["low"].values
            closes = history["close"].values
            atr = self.compute_atr(highs, lows, closes, self.atr_window)
            adx = self.compute_adx(highs, lows, closes, self.adx_window)
            self.rolling_atr.append(atr)
            self.rolling_adx.append(adx)
      
    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.fast_window,
                self.slow_window,
                self.signal_window,
                self.rsi_period,
                self.k_period,
                self.k_smooth,
                self.d_period,
                self.vol_fast_window,
                self.vol_slow_window
            ) + 1
            self.activated = len(self.prices) > required_data
    
    def compute_signal_direction(self, k, d):
        if k and d:
            lower, upper = self.stoch_lower, self.stoch_upper

            if k < lower and d < lower:
                self.stoch_signal = 1
            elif k > upper and d > upper:
                self.stoch_signal = -1
            elif self.stoch_signal == 1 and (k > upper or d > upper):
                self.stoch_signal = None
            elif self.stoch_signal == -1 and (k < lower or d < lower):
                self.stoch_signal = None
    
    def predict_trade(self, threshold=0.5):
        df = pd.DataFrame({k: [v] for k, v in self.features.items()})
        self.model.prepare_features(df)
        proba = self.model.get_proba(self.model.df)
        if self.stoch_signal == 1:
            if proba > threshold:
                signal, leg = self.buy() 
                confidence = proba
            else:
                signal, leg = self.sell() 
                confidence = 1 - proba
        elif self.stoch_signal == -1:
            if proba > threshold:
                signal, leg = self.sell()
                confidence = proba
            else:
                signal, leg = self.buy() 
                confidence = 1 - proba

        # self.position_size = 0.25 + 0.75 * confidence       
        return signal, leg

    def add_features(self, direction, stop_price, target_price):
        history = self.history.loc[self.history.index < self.ts.normalize()].tail(1)
        self.features = {
            "direction": direction,
            "entry_time": self.ts.isoformat(),
            "entry_price": self.price,
            "stop_price": stop_price,
            "target_price": target_price,
            "session_open": self.opens[0],
            "session_low": min(self.lows),
            "session_high": max(self.highs),
            "prev_day_close": history["close"].values[0],
            "adx": self.rolling_adx[-1],
            "adx_ma_3": self.compute_ma(self.rolling_adx, window=3),
            "atr": self.rolling_atr[-1],
            "atr_ma_3": self.compute_ma(self.rolling_atr, window=3),
            "open_volume": sum(self.volumes[0:5])
        }