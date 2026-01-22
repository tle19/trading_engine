from collections import deque

from strategies import Strategy
from utils import *

class MACDIndicator(Strategy):
    def __init__(self, symbol, fast_window_low=5, slow_window_low=8, signal_window_low=9,
                 fast_window_med=13, slow_window_med=21, signal_window_med=9,
                 fast_window_high=34, slow_window_high=144, signal_window_high=9, 
                 htf_window=50, ma_threshold=0.001,
                 stop_loss=0.005, take_profit=0.01, position_size=0.25, trailing_ratio=0.15, pyramid=True, force_close=True,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=20):
        super().__init__(symbol, stop_loss, take_profit, position_size, trailing_ratio, pyramid, force_close,
                         pnl_target, pnl_loss, trade_max)
        self.fast_window_low = fast_window_low
        self.slow_window_low = slow_window_low
        self.signal_window_low = signal_window_low
        self.fast_window_med = fast_window_med
        self.slow_window_med = slow_window_med
        self.signal_window_med = signal_window_med
        self.fast_window_high = fast_window_high
        self.slow_window_high = slow_window_high
        self.signal_window_high = signal_window_high
        self.htf_window = htf_window
        self.ma_threshold = ma_threshold

        self.fast_ema_low = None
        self.slow_ema_low = None
        self.signal_ema_low = None
        self.fast_ema_med = None
        self.slow_ema_med = None
        self.signal_ema_med = None
        self.fast_ema_high = None
        self.slow_ema_high = None
        self.signal_ema_high = None
        self.ema = None
        
        self.prev_hist_low = None
        self.prev_hist_med = None
        self.prev_hist_high = None

        self.cond_1 = False
        self.cond_2 = False
        self.cond_3 = False
        self.cond_4 = False

        self.rolling_adx = deque(maxlen=10)
        self.rolling_ema = deque(maxlen=10)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()

        hist_low, _, self.fast_ema_low, self.slow_ema_low, self.signal_ema_low = self.compute_macd(self.fast_ema_low, self.slow_ema_low, self.signal_ema_low, self.fast_window_low, self.slow_window_low, self.signal_window_low)
        hist_med, _, self.fast_ema_med, self.slow_ema_med, self.signal_ema_med = self.compute_macd(self.fast_ema_med, self.slow_ema_med, self.signal_ema_med, self.fast_window_med, self.slow_window_med, self.signal_window_med)
        hist_high, _, self.fast_ema_high, self.slow_ema_high, self.signal_ema_high = self.compute_macd(self.fast_ema_high, self.slow_ema_high, self.signal_ema_high, self.fast_window_high, self.slow_window_high, self.signal_window_high)
        self.ema = self.compute_ema(self.ema, self.price, self.htf_window)
        adx = self.compute_adx(self.highs, self.lows, self.prices)

        self.rolling_adx.append(adx)
        self.rolling_ema.append(self.ema)
        # adx slope strength
        # big price move within single candle (volume may or may not support?)
        # check for final agreement with lower timeframe macd
        # if move more than 50% towards profit, move stop to breakeven
        # ema slope strength

        # if self.risk_manager._day_pause: 
        #     return None
        if not self.trade_window((9, 30), (15, 00)) and not self.position_manager.in_trade():
            return None

        self.condition_check(hist_low, hist_med, hist_high)
        signal = None
        if self.activated:
            signal = self.exit_trade()
            if signal is None:
                signal = self.enter_trade(hist_low, hist_med, hist_high, adx)
        self.prev_hist_low = hist_low
        self.prev_hist_med = hist_med
        self.prev_hist_high = hist_high
        return signal

    def enter_trade(self, hist_low, hist_med, hist_high, adx):
        if self.cond_1 and self.cond_2 and self.cond_3:
            signal = None
            adx_ma = sum(self.rolling_adx) / len(self.rolling_adx)
            adx_cond = (adx > adx_ma and adx > 30) or ((adx < adx_ma and adx > 40))
            
            if hist_high > 0 and self.close > self.ema:
                swing_low = self.compute_swing(mode="low", lookback=10)
                stop_in_band = min(self.low, swing_low) > self.ema * (1 + self.ma_threshold)
                if stop_in_band:
                    signal, pos_leg = self.buy()
                    if pos_leg is not None:
                        pos_leg.stop_price = round(max(swing_low * (1 - 0.0001), pos_leg.stop_price), 2)
                        diff = self.close - pos_leg.stop_price
                        pos_leg.target_price = round(self.close + (diff * self.take_profit * 100), 2)
                # swing_low = self.compute_swing(mode="low", lookback=10)
                # swing_high = self.compute_swing(mode="high", lookback=10)
                # stop_in_band = min(self.low, swing_low) > self.ema * (1 + self.ma_threshold)
                # if stop_in_band:
                #     signal, pos_leg = self.sell()
                #     if pos_leg is not None:
                #         pos_leg.stop_price = round(min(self.high * (1 + 0.0005), pos_leg.stop_price), 2)
                #         diff = pos_leg.stop_price - self.close
                #         pos_leg.target_price = round(self.close - (diff * self.take_profit * 100), 2)
            
            if hist_high < 0 and self.close < self.ema:
                swing_high = self.compute_swing(mode="high", lookback=10)
                stop_in_band = max(self.high, swing_high) < self.ema * (1 - self.ma_threshold)
                if stop_in_band:
                    signal, pos_leg = self.sell()
                    if pos_leg is not None:
                        pos_leg.stop_price = round(min(swing_high * (1 + 0.0001), pos_leg.stop_price), 2)
                        diff = pos_leg.stop_price - self.close
                        pos_leg.target_price = round(self.close - (diff * self.take_profit * 100), 2)
                # swing_low = self.compute_swing(mode="low", lookback=10)
                # swing_high = self.compute_swing(mode="high", lookback=10)
                # stop_in_band = max(self.high, swing_high) < self.ema * (1 - self.ma_threshold)
                # if stop_in_band:
                #     signal, pos_leg = self.buy()
                #     if pos_leg is not None:
                #         pos_leg.stop_price = round(max(self.low * (1 - 0.0005), pos_leg.stop_price), 2)
                #         diff = self.close - pos_leg.stop_price
                #         pos_leg.target_price = round(self.close + (diff * self.take_profit * 100), 2)

            self.cond_1 = False
            self.cond_2 = False
            self.cond_3 = False
            self.cond_4 = False
            return signal
        
    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.fast_ema_low = None
            self.slow_ema_low = None
            self.signal_ema_low = None
            self.fast_ema_med = None
            self.slow_ema_med = None
            self.signal_ema_med = None
            self.fast_ema_high = None
            self.slow_ema_high = None
            self.signal_ema_high = None
            self.ema = None

            self.prev_hist_low = None
            self.prev_hist_med = None
            self.prev_hist_high = None

            self.cond_1 = False
            self.cond_2 = False
            self.cond_3 = False
            self.cond_4 = False

            self.rolling_adx = deque(maxlen=10)
            self.rolling_ema = deque(maxlen=10)
        
    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.fast_window_low,
                self.slow_window_low,
                self.signal_window_low,
                self.fast_window_med,
                self.slow_window_med,
                self.signal_window_med,
                self.fast_window_high,
                self.signal_window_high,
                self.htf_window
            ) + 1
            self.activated = len(self.prices) > required_data

    def condition_check(self, hist_low, hist_med, hist_high):
        if (hist_high > 0 and self.prev_hist_high < 0) or (hist_high < 0 and self.prev_hist_high > 0):
            self.cond_1 = False
            self.cond_2 = False
            self.cond_3 = False
            self.cond_4 = False

        if hist_high > 0:
            if not self.cond_1:
                self.cond_1 = hist_med > 0 and hist_med < self.prev_hist_med
            elif not self.cond_2 and self.cond_1:
                if self.prev_hist_low > 0:
                    self.cond_2 = hist_low < 0
                elif self.prev_hist_low < 0:
                    self.cond_1 = False 
            elif not self.cond_3 and self.cond_2 and self.cond_1:
                if hist_med > 0:
                    self.cond_3 = hist_med > self.prev_hist_med
                elif hist_med < 0:
                    self.cond_3 = hist_high > self.prev_hist_high
        elif hist_high < 0:
            if not self.cond_1:
                self.cond_1 = hist_med < 0 and hist_med > self.prev_hist_med
            elif not self.cond_2 and self.cond_1:
                if self.prev_hist_low < 0:
                    self.cond_2 = hist_low > 0
                elif self.prev_hist_low > 0:
                    self.cond_1 = False 
            elif not self.cond_3 and self.cond_2 and self.cond_1:
                if hist_med < 0:
                    self.cond_3 = hist_med < self.prev_hist_med
                elif hist_med > 0:
                    self.cond_3 = hist_high < self.prev_hist_high

    def compute_macd(self, fast_ema, slow_ema, signal_ema, fast_window, slow_window, signal_window):
        price = self.price

        fast_ema = self.compute_ema(fast_ema, price, fast_window)
        slow_ema = self.compute_ema(slow_ema, price, slow_window)

        macd = fast_ema - slow_ema
        signal_ema = self.compute_ema(signal_ema, macd, signal_window)
        hist = macd - signal_ema

        return hist, macd, fast_ema, slow_ema, signal_ema