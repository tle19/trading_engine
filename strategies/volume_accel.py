from collections import deque

from strategies import Strategy, RiskManager
from utils import *

class VolumeAccelIndicator(Strategy):
    def __init__(self, symbol, fast_window=12, slow_window=26, signal_window=9, htf_window=50,
                 rsi_period=14, vol_fast_window=14, vol_slow_window=28, rsi_accel=5, vol_accel=0.01,
                 stop_loss=0.001, take_profit=0.02, trailing_ratio=0.05, position_size=1.0,
                 target=0.001, loss=-0.001):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.htf_window = htf_window
        self.rsi_period = rsi_period
        self.rsi_accel = rsi_accel
        self.vol_fast_window = vol_fast_window
        self.vol_slow_window = vol_slow_window
        self.vol_accel = vol_accel

        self.activated = False
        self.ema = None
        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None
        self.vol_fast_ema = None
        self.vol_slow_ema = None
        self.rolling_rsi = deque(maxlen=2)
        self.rolling_vol = deque(maxlen=2)

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()

        vol = self.compute_volume_oscillator(self.volumes, self.vol_fast_window, self.vol_slow_window)
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        hist, _, _ = self.compute_macd(self.fast_window, self.slow_window, self.signal_window)
        # self.ema = self.compute_ema(self.ema, self.prices[-1], self.htf_window)
        # increasing volume osc acceleration along with rsi trend acceleration confirmation to go breakout,
        # decreasing volume osc acceleration stick with trend if rsi confirms

        if self.rolling_rsi and self.rolling_vol:
            rsi_ma = sum(self.rolling_rsi) / len(self.rolling_rsi)
            vol_ma = sum(self.rolling_vol) / len(self.rolling_vol)
        self.rolling_rsi.append(rsi)
        self.rolling_vol.append(vol)
         
        status = self.check_status()
        if status is not None:
            return status
        if not self.trade_window((9, 30), (15, 30)) and self.position is None:
            return None

        signal = None
        if self.position is None and self.activated:
            signal = self.enter_trade(vol, rsi, hist, rsi_ma, vol_ma)
        elif self.position is not None:
            signal = self.exit_trade(vol, rsi, rsi_ma, vol_ma)
        return signal

    def enter_trade(self, vol, rsi, hist, rsi_ma, vol_ma):
        vol_cond = vol < 0 and (vol - vol_ma) > self.vol_accel
        rsi_cond = abs(rsi - rsi_ma) > self.rsi_accel

        if vol_cond and rsi_cond and hist > 0:
            signal = self.buy()
            swing_point = self.compute_swing(mode="low")
            self.stop_price = round(swing_point * (1 - self.stop_loss), 2)
            print(f"{self.ts} ENTRY (L): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
            return signal
        if vol_cond and rsi_cond and hist < 0:
            signal = self.sell()
            swing_point = self.compute_swing(mode="high")
            self.stop_price = round(swing_point * (1 + self.stop_loss), 2)
            print(f"{self.ts} ENTRY (S): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
            return signal
        
    def exit_trade(self, vol, rsi, rsi_ma, vol_ma):
        # if volume decelerating and rsi does not support trend
        vol_cond = (vol - vol_ma) < 0
        
        if self.position == "long" and vol_cond and rsi < rsi_ma and self.close > self.entry_price:
            self.stop_price = round(self.close, 2)
            print(f"{self.ts} EXIT (L): {self.entry_price}, STOP: {self.stop_price}")
            return self.sell()
        if self.position == "short" and vol_cond and rsi > rsi_ma and self.close < self.entry_price:
            self.stop_price = round(self.close, 2)
            print(f"{self.ts} EXIT (S): {self.entry_price}, STOP: {self.stop_price}")
            return self.buy()
      
    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.ema = None
            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
            self.stoch_signal = None
            self.vol_fast_ema = None
            self.vol_slow_ema = None
            self.rolling_rsi = deque(maxlen=3)
            self.rolling_vol = deque(maxlen=3)
      
    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.fast_window,
                self.slow_window,
                self.signal_window,
                self.rsi_period,
                self.vol_fast_window,
                self.vol_slow_window
            ) + 1
            self.activated = len(self.prices) > required_data
    
    def compute_swing(self, mode="low", window=2, lookback=10):
        if len(self.prices) < window * 2 + 1:
            return None
        
        highs = self.highs[-lookback:]
        lows = self.lows[-lookback:]
        n = len(highs)

        if mode == "high":
            for i in range(n - window - 1, window - 1, -1):
                left = highs[i - window:i]
                right = highs[i + 1:i + 1 + window]
                if highs[i] > max(left) and highs[i] > max(right):
                    return highs[i]
            return max(highs)

        elif mode == "low":
            for i in range(n - window - 1, window - 1, -1):
                left = lows[i - window:i]
                right = lows[i + 1:i + 1 + window]
                if lows[i] < min(left) and lows[i] < min(right):
                    return lows[i]
            return min(lows)