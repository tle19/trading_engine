from collections import deque

from strategies import Strategy, RiskManager
from utils import *

class MACDIndicator(Strategy):
    def __init__(self, symbol, fast_window_low=5, slow_window_low=8, signal_window_low=9,
                 fast_window_med=13, slow_window_med=21, signal_window_med=9,
                 fast_window_high=34, slow_window_high=144, signal_window_high=18,
                 stop_loss=0.0001, take_profit=0.02, multiple_pos=True,
                 target=0.001, loss=-0.001):
        super().__init__(symbol, stop_loss, take_profit, multiple_pos)
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

        self.cond_1 = False
        self.cond_2 = False
        self.cond_3 = False
        self.cond_4 = False

        self.rolling_adx = deque(maxlen=10)

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()

        hist_low, macd_line_low, self.fast_ema_low, self.slow_ema_low, self.signal_ema_low = self.compute_macd(self.fast_ema_low, self.slow_ema_low, self.signal_ema_low, self.fast_window_low, self.slow_window_low, self.signal_window_low)
        hist_med, macd_line_med, self.fast_ema_med, self.slow_ema_med, self.signal_ema_med = self.compute_macd(self.fast_ema_med, self.slow_ema_med, self.signal_ema_med, self.fast_window_med, self.slow_window_med, self.signal_window_med)
        hist_high, macd_line_high, self.fast_ema_high, self.slow_ema_high, self.signal_ema_high = self.compute_macd(self.fast_ema_high, self.slow_ema_high, self.signal_ema_high, self.fast_window_high, self.slow_window_high, self.signal_window_high)
        adx = self.compute_adx()

        self.rolling_adx.append(adx)
        # adx slope strength
        # big price move within single candle (volume may or may not support?)
        # ema for multiple confluence in determing direction

        status = self.check_status()
        if status is not None:
            return status
        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
            return None
        
        signal = None
        if self.activated:
            signal = self.enter_trade(hist_low, hist_med, hist_high, adx)
        # elif self.position is not None and self.activated:
        #     signal = self.exit_trade(hist_low, hist_med, hist_high)
        self.prev_hist_low = hist_low
        self.prev_hist_med = hist_med
        self.prev_hist_high = hist_high
        return signal

    def enter_trade(self, hist_low, hist_med, hist_high, adx):
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

        if self.cond_1 and self.cond_2 and self.cond_3:
            signal = None
            adx_ma = sum(self.rolling_adx) / len(self.rolling_adx)
            if hist_high > 0 and (adx > adx_ma and adx > 20):
                print(self.ts, 'buy')
            elif hist_high < 0 and (adx > adx_ma and adx > 20):
                print(self.ts, 'sell')
            if (adx > adx_ma and adx > 20) and self.position is None:
                if hist_high > 0:
                    signal = self.buy()
                    swing_point = self.compute_swing(mode="low", lookback=10)
                    diff = self.close - max(swing_point, self.stop_price)
                    self.stop_price = max(swing_point * (1 - 0.0001), self.stop_price)
                    self.stop_price = round(self.stop_price, 2)
                    self.profit_price = round(self.close + ((self.take_profit * 100) * diff), 2)
                    print(f"{self.ts} ENTRY (L): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
                if hist_high < 0:
                    signal = self.sell()
                    swing_point = self.compute_swing(mode="high", lookback=10)
                    diff = min(swing_point, self.stop_price) - self.close
                    self.stop_price = min(swing_point * (1 + 0.0001), self.stop_price)
                    self.stop_price = round(self.stop_price, 2)
                    self.profit_price = round(self.close - ((self.take_profit * 100) * diff), 2)
                    print(f"{self.ts} ENTRY (S): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
            self.cond_1 = False
            self.cond_2 = False
            self.cond_3 = False
            self.cond_4 = False
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

            self.cond_1 = False
            self.cond_2 = False
            self.cond_3 = False
            self.cond_4 = False

            self.rolling_adx = deque(maxlen=10)
            return None

    def compute_macd(self, fast_ema, slow_ema, signal_ema, fast_window, slow_window, signal_window):
        price = self.prices[-1]

        fast_ema = self.compute_ema(fast_ema, price, fast_window)
        slow_ema = self.compute_ema(slow_ema, price, slow_window)

        macd = fast_ema - slow_ema
        signal_ema = self.compute_ema(signal_ema, macd, signal_window)
        hist = macd - signal_ema

        return hist, macd, fast_ema, slow_ema, signal_ema