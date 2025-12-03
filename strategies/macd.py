from collections import deque

from strategies import Strategy, RiskManager
from utils import *

class MACDIndicator(Strategy):
    def __init__(self, symbol, fast_window_low=5, slow_window_low=8, signal_window_low=9,
                 fast_window_med=13, slow_window_med=21, signal_window_med=9,
                 fast_window_high=34, slow_window_high=144, signal_window_high=18,
                 stop_loss=0.001, take_profit=0.05, position_size=1.0,
                 target=0.001, loss=-0.001):
        super().__init__(symbol, stop_loss, take_profit, position_size)
        self.fast_window_low = fast_window_low
        self.slow_window_low = slow_window_low
        self.signal_window_low = signal_window_low
        self.fast_window_med = fast_window_med
        self.slow_window_med = slow_window_med
        self.signal_window_med = signal_window_med
        self.fast_window_high = fast_window_high
        self.slow_window_high = slow_window_high
        self.signal_window_high = signal_window_high

        self.fast_ema_low = None
        self.slow_ema_low = None
        self.signal_ema_low = None
        self.fast_ema_med = None
        self.slow_ema_med = None
        self.signal_ema_med = None
        self.fast_ema_high = None
        self.slow_ema_high = None
        self.signal_ema_high = None
        self.prev_hist_low = None
        self.prev_hist_med = None
        self.prev_hist_high = None

        self.direction = None
        self.cond_1 = False
        self.cond_2 = False
        self.cond_3 = False
        self.cond_4 = False

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()

        hist_low, macd_line_low, self.fast_ema_low, self.slow_ema_low, self.signal_ema_low = self.compute_macd(self.fast_ema_low, self.slow_ema_low, self.signal_ema_low, self.fast_window_low, self.slow_window_low, self.signal_window_low)
        hist_med, macd_line_med, self.fast_ema_med, self.slow_ema_med, self.signal_ema_med = self.compute_macd(self.fast_ema_med, self.slow_ema_med, self.signal_ema_med, self.fast_window_med, self.slow_window_med, self.signal_window_med)
        hist_high, macd_line_high, self.fast_ema_high, self.slow_ema_high, self.signal_ema_high = self.compute_macd(self.fast_ema_high, self.slow_ema_high, self.signal_ema_high, self.fast_window_high, self.slow_window_high, self.signal_window_high)
        
        status = self.check_status()
        if status is not None:
            return status
        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
            return None
        
        signal = None
        if self.position is None and self.activated:
            signal = self.enter_trade(hist_low, hist_med, hist_high)
        # elif self.position is not None and self.activated:
        #     signal = self.exit_trade(hist_low, hist_med, hist_high)
        self.prev_hist_low = hist_low
        self.prev_hist_med = hist_med
        self.prev_hist_high = hist_high
        return signal

    def enter_trade(self, hist_low, hist_med, hist_high):
        if hist_high > 0:
            if self.direction == "short":
                self.cond_1 = False
                self.cond_2 = False
                self.cond_3 = False
                self.cond_4 = False
            self.direction = "long"
        elif hist_high < 0:
            if self.direction == "long":
                self.cond_1 = False
                self.cond_2 = False
                self.cond_3 = False
                self.cond_4 = False
            self.direction = "short"

        if hist_high > 0:
            if not self.cond_1:
                self.cond_1 = hist_med > 0 and hist_med < self.prev_hist_med
            if not self.cond_2 and self.cond_1:
                if self.prev_hist_low > 0:
                    self.cond_2 = hist_low < 0
                elif self.prev_hist_low < 0:
                    self.cond_1 = False 
            if not self.cond_3 and self.cond_2 and self.cond_1:
                if hist_med > 0:
                    self.cond_3 = hist_med > self.prev_hist_med
                elif hist_med < 0:
                    self.cond_3 = hist_high > self.prev_hist_high
        elif hist_high < 0:
            if not self.cond_1:
                self.cond_1 = hist_med < 0 and hist_med > self.prev_hist_med
            if not self.cond_2 and self.cond_1:
                self.cond_2 = hist_low > 0 and self.prev_hist_low < 0
            if not self.cond_3 and self.cond_2 and self.cond_1:
                if hist_med < 0:
                    self.cond_3 = hist_med < self.prev_hist_med
                elif hist_med > 0:
                    self.cond_3 = hist_high < self.prev_hist_high

        if self.direction == "long":
            if self.cond_1 and self.cond_2 and self.cond_3: 
                signal = self.buy()
                swing_point = self.compute_swing(mode="low", lookback=10)
                self.stop_price = round(swing_point * (1 - self.stop_loss), 2)
                diff = self.close - self.stop_price
                self.profit_price = round(self.close + (1 * diff), 2)
                self.cond_1 = False
                self.cond_2 = False
                self.cond_3 = False
                self.cond_4 = False
                # print(f"{self.ts} ENTRY (L): {self.entry_price}, STOP: {self.stop_price}")
                return signal
        if self.direction == "short":
            if self.cond_1 and self.cond_2 and self.cond_3: 
                signal = self.sell()
                swing_point = self.compute_swing(mode="high", lookback=10)
                self.stop_price = round(swing_point * (1 + self.stop_loss), 2)
                diff = self.stop_price - self.close
                self.profit_price = round(self.close - (1 * diff), 2)
                self.cond_1 = False
                self.cond_2 = False
                self.cond_3 = False
                self.cond_4 = False
                # print(f"{self.ts} ENTRY (S): {self.entry_price}, STOP: {self.stop_price}")
                return signal
        
    def exit_trade(self, hist_low, hist_med, hist_high):
        if self.position == "long" and hist_low < 0 and hist_med < 0:
            self.stop_price = round(self.close, 2)
            print(f"{self.ts} EXIT (L): {self.entry_price}, STOP: {self.stop_price}")
            return self.sell()
        if self.position == "short" and hist_low > 0 and hist_med > 0:
            self.stop_price = round(self.close, 2)
            print(f"{self.ts} EXIT (S): {self.entry_price}, STOP: {self.stop_price}")
            return self.buy()
        
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
                self.slow_window_high, # delete?
                self.signal_window_high,
            ) + 1
            self.activated = len(self.prices) > required_data

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
            self.prev_hist_low = None
            self.prev_hist_med = None
            self.prev_hist_high = None
            self.direction = None
            self.cond_1 = False
            self.cond_2 = False
            self.cond_3 = False
            self.cond_4 = False
            return None

    def compute_macd(self, fast_ema, slow_ema, signal_ema, fast_window, slow_window, signal_window):
        price = self.prices[-1]

        fast_ema = self.compute_ema(fast_ema, price, fast_window)
        slow_ema = self.compute_ema(slow_ema, price, slow_window)

        macd = fast_ema - slow_ema
        signal_ema = self.compute_ema(signal_ema, macd, signal_window)
        hist = macd - signal_ema

        return hist, macd, fast_ema, slow_ema, signal_ema