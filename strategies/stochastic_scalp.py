from collections import deque

from strategies import Strategy, RiskManager
from utils import *

class StochasticIndicator(Strategy):
    def __init__(self, symbol, fast_window=12, slow_window=26, signal_window=9, htf_window=50,
                 rsi_period=14, k_period=14, k_smooth=3, d_period=3, stoch_lower=20, stoch_upper=80,
                 vol_fast_window=14, vol_slow_window=28, vol_threshold=0.025, atr_window=10,
                 stop_loss=0.0075, take_profit=1.25, trailing_ratio=0.05, position_size=1.0,
                 target=0.001, loss=-0.001):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size)
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
        self.vol_fast_ema = None
        self.vol_slow_ema = None
        self.rolling_rsi = deque(maxlen=10)

        # self.hold_time = 0
        # self.local_high = 0
        # self.local_low = 0
        # self.hit_pct = False
        # self.trades = []

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        
        k, d = self.compute_stochastic(self.highs, self.lows, self.prices, self.k_period, self.k_smooth, self.d_period)
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        hist = self.compute_macd(self.fast_window, self.slow_window, self.signal_window)
        ema = self.compute_ema(self.ema, self.prices[-1], self.htf_window)
        vol = self.compute_volume_oscillator(self.volumes, self.vol_fast_window, self.vol_slow_window)
        # atr = self.compute_atr()
        
        self.compute_signal_direction(k, d)
        self.rolling_rsi.append(rsi)
             
        if not self.activated:
            self.minimum_computations()

        status = self.check_status()
        if status is not None:
            return status

        if not self.trade_window((9, 30), (15, 30)) and self.position is None:
            return None

        signal = None
        if self.position is None and self.activated:
            signal = self.enter_trade(ema, k, d, rsi, hist, vol)
        # elif self.position is not None and rsi is not None:
        #     signal = self.exit_trade(rsi, hist)
        #     self.set_trailing_stop()
        return signal

    def enter_trade(self, ema, k, d, rsi, hist, vol):
        if not (self.stoch_lower < min(k, d) and max(k, d) < self.stoch_upper):
            return None
        rsi_ma = sum(self.rolling_rsi) / len(self.rolling_rsi)

        if self.stoch_signal == "long" and rsi > 50 and rsi > rsi_ma and hist > 0:
            if self.close > ema or vol > self.vol_threshold:
                # self.local_high = self.close
                signal = self.buy()
                swing_point = self.compute_swing(mode="low")
                self.stop_price = round(swing_point * (1 - 0.0005), 2)
                stop_dist = self.entry_price -  self.stop_price
                self.profit_price = round(self.entry_price + (stop_dist * self.take_profit), 2)
                # print(f"{self.ts} ENTRY (L): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
                return signal
        if self.stoch_signal == "short" and rsi < 50 and rsi < rsi_ma and hist < 0:
            if self.close < ema or vol > self.vol_threshold:
                # self.local_low = self.close
                signal = self.sell()
                swing_point = self.compute_swing(mode="high")
                self.stop_price = round(swing_point * (1 + 0.0005), 2)
                stop_dist = self.stop_price - self.entry_price
                self.profit_price = round(self.entry_price - (stop_dist * self.take_profit), 2)
                # print(f"{self.ts} ENTRY (S): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
                return signal
        
    def exit_trade(self, rsi, hist):
        if self.position == "long":
            if self.prices[-1] > self.local_high:
                self.local_high = self.prices[-1]
                self.hold_time = 0
        elif self.position == "short":
            if self.prices[-1] < self.local_low:
                self.local_low = self.prices[-1] 
                self.hold_time = 0
        self.hold_time += 1
                
        if self.position == "long" and hist < 0 and rsi < 50 and self.close < self.local_high and self.local_high >= self.entry_price + 0.75 * (self.take_profit - self.entry_price) and self.hold_time > 30:
            self.stop_price = round(self.close, 2)
            # print(f"{self.ts} EXIT (L): {self.entry_price}, STOP: {self.stop_price}")
            return self.sell()
        if self.position == "short" and hist > 0 and rsi > 50 and self.close > self.local_low and self.local_low <= self.entry_price + 0.75 * (self.entry_price - self.take_profit) and self.hold_time > 60:
            self.stop_price = round(self.close, 2)
            # print(f"{self.ts} EXIT (S): {self.entry_price}, STOP: {self.stop_price}")
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
            self.rolling_rsi = []
      
    def minimum_computations(self):
        min_bars = max(
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
        minutes_passed = (self.ts.hour - 9) * 60 + (self.ts.minute - 30)
        self.activated = minutes_passed >= min_bars
    
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
    
    def compute_atr(self):
        # swing low/high for stop
        # adaptive sl and tp based on ATR/volatility/spread
        raise NotImplementedError
    
    def compute_swing(self, mode="low", window=2, lookback=20):
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

    # if self.entry_price is not None:
    #     if self.position == "long":
    #         self.local_high = max(self.close, self.local_high)
    #     if self.position == "short":
    #         self.local_low = min(self.close, self.local_low)

    #     total_distance = abs(self.profit_price - self.entry_price)
    #     if self.position == "long":
    #         distance_traveled = self.local_high - self.entry_price
    #     elif self.position == "short":
    #         distance_traveled = self.entry_price - self.local_low
    #     progress = (distance_traveled / total_distance)
    #     if progress >= 0.25 and not self.hit_pct:
    #         self.hit_high = self.local_high
    #         self.hit_low = self.local_low
    #         self.hit_pct = True

    # if status is not None:
    #     if self.hit_pct:
    #         if self.position == "long" and self.high > self.profit_price:
    #             self.trades.append(1)
    #         elif self.position == "short" and self.low < self.profit_price:
    #             self.trades.append(1)
    #         else:
    #             self.trades.append(0)
    #     self.hit_pct = False
    #     return status