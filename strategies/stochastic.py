from collections import deque

from strategies import Strategy, RiskManager
from utils import *

class StochasticIndicator(Strategy):
    def __init__(self, symbol, fast_window=12, slow_window=26, signal_window=9, htf_window=20,
                 rsi_period=14, k_period=14, k_smooth=3, d_period=3, stoch_lower=20, stoch_upper=80,
                 vol_fast_window=14, vol_slow_window=28, vol_threshold=0.025, atr_window=10,
                 stop_loss=0.01, take_profit=0.01, trailing_ratio=0.05,
                 target=0.001, loss=-0.001):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.htf_window = htf_window
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

        self.activated = False
        self.ema = None
        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None
        self.stoch_signal = None
        self.current_atr = None
        self.regime = None
        self.rolling_rsi = deque(maxlen=10)
        self.rolling_vol = deque(maxlen=5)

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()
        
        k, d = self.compute_stochastic(self.highs, self.lows, self.prices, self.k_period, self.k_smooth, self.d_period)
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        hist, _, _ = self.compute_macd(self.fast_window, self.slow_window, self.signal_window)
        # self.ema = self.compute_ema(self.ema, self.prices[-1], self.htf_window)
        vol = self.compute_volume_oscillator(self.volumes, self.vol_fast_window, self.vol_slow_window)
        # atr = self.compute_atr()
        # adaptive sl and tp based on ATR/volatility/spread
        # clamp sl (0.005, 0.015) and tp (0.005, 0.015) in predetermined range

        self.compute_signal_direction(k, d)
        self.rolling_rsi.append(rsi)
        self.rolling_vol.append(vol)

        status = self.check_status()
        if status is not None:
            return status
        if not self.trade_window((9, 30), (15, 30)) and self.position is None:
            return None

        signal = None
        if self.position is None and self.activated:
            signal = self.enter_trade(k, d, rsi, hist, vol)
        return signal

    def enter_trade(self, k, d, rsi, hist, vol):
        if not (self.stoch_lower < min(k, d) and max(k, d) < self.stoch_upper):
            return None
        rsi_ma = sum(self.rolling_rsi) / len(self.rolling_rsi)
        vol_ma = sum(self.rolling_vol) / len(self.rolling_vol)
        
        if self.stoch_signal == "long" and rsi > 55 and rsi > rsi_ma and hist > 0:
            if vol > self.vol_threshold: #and vol > vol_ma
                signal = self.buy() 
                return signal
        if self.stoch_signal == "short" and rsi < 45 and rsi < rsi_ma and hist < 0:
            if vol > self.vol_threshold:
                signal = self.sell() 
                return signal

    # def enter_trade(self, k, d, rsi, hist, vol): # original version
    #     if not (self.stoch_lower < min(k, d) and max(k, d) < self.stoch_upper):
    #         return None

    #     if self.stoch_signal == "long" and rsi > 50 and hist > 0:
    #         if vol > self.vol_threshold:
    #             signal = self.buy() 
    #             swing_point = self.compute_swing(mode="low", lookback=10)
    #             self.stop_price = round(swing_point * (1 - self.stop_loss), 2)
    #             diff = self.close - self.stop_price
    #             self.profit_price = round(self.close + (1 * diff), 2)
    #             return signal
    #     if self.stoch_signal == "short" and rsi < 50 and hist < 0:
    #         if vol > self.vol_threshold:
    #             signal = self.sell() 
    #             swing_point = self.compute_swing(mode="high", lookback=10)
    #             self.stop_price = round(swing_point * (1 + self.stop_loss), 2)
    #             diff = self.stop_price - self.close
    #             self.profit_price = round(self.close - (1 * diff), 2)
    #             return signal
        
    # def exit_trade(self, rsi, hist):
    #     if self.position == "long":
    #         if self.prices[-1] > self.local_high:
    #             self.local_high = self.prices[-1]
    #             self.hold_time = 0
    #     elif self.position == "short":
    #         if self.prices[-1] < self.local_low:
    #             self.local_low = self.prices[-1] 
    #             self.hold_time = 0
    #     self.hold_time += 1
                
    #     if self.position == "long" and hist < 0 and rsi < 50 and self.close < self.local_high and self.local_high >= self.entry_price + 0.75 * (self.take_profit - self.entry_price) and self.hold_time > 30:
    #         self.stop_price = round(self.close, 2)
    #         return self.sell()
    #     if self.position == "short" and hist > 0 and rsi > 50 and self.close > self.local_low and self.local_low <= self.entry_price + 0.75 * (self.entry_price - self.take_profit) and self.hold_time > 60:
    #         self.stop_price = round(self.close, 2)
    #         return self.buy()
      
    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.ema = None
            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
            self.stoch_signal = None
            self.current_atr = None
            self.regime = None
            self.rolling_rsi = deque(maxlen=10)
            self.rolling_vol = deque(maxlen=3)

      
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
                self.stoch_signal = "long"
            elif k > upper and d > upper:
                self.stoch_signal = "short"
            elif self.stoch_signal == "long" and (k > upper or d > upper):
                self.stoch_signal = None
            elif self.stoch_signal == "short" and (k < lower or d < lower):
                self.stoch_signal = None