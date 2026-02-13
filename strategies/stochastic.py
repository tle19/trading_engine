from collections import deque
import pandas as pd

from strategies import Strategy
from models import *
from utils import *

class StochasticIndicator(Strategy):
    def __init__(self, symbol, fast_window=12, slow_window=26, signal_window=9,
                 rsi_period=14, k_period=14, k_smooth=3, d_period=3, stoch_lower=20, stoch_upper=80,
                 vol_fast_window=14, vol_slow_window=28,
                 stop_loss=0.01, take_profit=0.01, position_size=1.0, trailing_ratio=0.05, pyramid=False, force_close=True, swing=False,
                 pnl_target=0.01, pnl_loss=-0.02, trade_max=10):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid, force_close, swing,
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

        self.ema = None
        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None
        self.stoch_signal = None
        self.rolling_rsi = deque(maxlen=10)
        self.rolling_vol = deque(maxlen=10)

        self.prev_day_close = None
        self.regime_ema = None
        self.adx = None
        self.atr = None
        
        self.model = XGBModel(symbol=symbol, live=True)
        if not self.model.initialize():
            self.model = None

    def generate_signal(self, row, _=None):
        self.update(row)
        self.reset_data()
        self.reset_day()
        self.reset_indicators()
        self.minimum_computations()

        k, d, rsi, hist, vol = self.compute_indicators()
        
        if self.risk_manager._day_pause: 
            return None
        
        if not self.trade_window((9, 30), (15, 30)) and not self.position_manager.in_trade():
            return None
        
        signal = None
        if self.activated:
            self.compute_signal_direction(k, d)
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade(rsi, hist, vol)
        return signal
    
    def enter_trade(self, rsi, hist, vol):
        signal = None
        rsi_ma = sum(self.rolling_rsi) / len(self.rolling_rsi)
        
        if self.stoch_signal == 1 and rsi > 55 and rsi > rsi_ma and hist > 0 and vol > 0.025:
            if self.symbol in ("META", "ABBV", "AXP", "MRK", "CAT"):
                signal, _ = self.sell()
            else:
                signal, _ = self.buy()
        if self.stoch_signal == -1 and rsi < 45 and rsi < rsi_ma and hist < 0 and vol > 0.025:
            if self.symbol in ("META", "ABBV", "AXP", "MRK", "CAT"):
                signal, _ = self.buy()
            else:
                signal, _ = self.sell()
        return signal

    def compute_indicators(self):
        self.k, self.d = self.compute_stochastic(self.highs, self.lows, self.closes, self.k_period, self.k_smooth, self.d_period)
        self.rsi = self.compute_rsi(self.closes, self.rsi_period)
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

            if self.d_closes:
                self.prev_day_close = self.d_closes[-1]
                self.regime_ema = self.compute_ma(self.d_closes, window=50)
                self.adx = self.compute_adx(self.d_highs, self.d_lows, self.d_closes)
                self.atr = self.compute_atr(self.d_highs, self.d_lows, self.d_closes)
        
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
            self.activated = len(self.closes) > required_data
    
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
    
    def predict_trade(self, threshold=0.4):
        df = pd.DataFrame([self.features])
        self.model.prepare_features(df)
        proba = self.model.get_proba()

        if self.stoch_signal == 1:
            if proba > threshold:
                self.position_size = 1.0
            else:
                self.position_size = 0.5
            signal, leg = self.buy() 
        elif self.stoch_signal == -1:
            if proba > threshold:
                self.position_size = 1.0
            else:
                self.position_size = 0.5
            signal, leg = self.sell() 

        # if self.stoch_signal == 1:
        #     if proba > threshold:
        #         signal, leg = self.buy() 
        #         confidence = proba
        #     else:
        #         signal, leg = self.sell() 
        #         confidence = 1 - proba
        # elif self.stoch_signal == -1:
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
            "original_dir": self.stoch_signal
        }

