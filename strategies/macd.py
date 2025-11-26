from collections import deque

from strategies import Strategy, RiskManager
from utils import *

class MACDIndicator(Strategy):
    def __init__(self, symbol, fast_window1=6, slow_window1=13, signal_window1=5,
                 fast_window2=12, slow_window2=26, signal_window2=9,
                 fast_window3=24, slow_window3=52, signal_window3=18,
                 stop_loss=0.001, take_profit=0.05, position_size=1.0,
                 target=0.001, loss=-0.001):
        super().__init__(symbol, stop_loss, take_profit, position_size)
        self.fast_window1 = fast_window1
        self.slow_window1 = slow_window1
        self.signal_window1 = signal_window1
        self.fast_window2 = fast_window2
        self.slow_window2 = slow_window2
        self.signal_window2 = signal_window2
        self.fast_window3 = fast_window3
        self.slow_window3 = slow_window3
        self.signal_window3 = signal_window3

        self.fast_ema1 = None
        self.slow_ema1 = None
        self.signal_ema1 = None
        self.fast_ema2 = None
        self.slow_ema2 = None
        self.signal_ema2 = None
        self.fast_ema3 = None
        self.slow_ema3 = None
        self.signal_ema3 = None
        self.prev_hist1 = None
        self.prev_hist2 = None
        self.prev_hist3 = None

        self.orb_window = 15
        self.upper_support = None
        self.lower_support = None
        self.direction = None

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()

        hist1, macd_line1, self.fast_ema1, self.slow_ema1, self.signal_ema1 = self.compute_macd(self.fast_ema1, self.slow_ema1, self.signal_ema1, self.fast_window1, self.slow_window1, self.signal_window1)
        hist2, macd_line2, self.fast_ema2, self.slow_ema2, self.signal_ema2 = self.compute_macd(self.fast_ema2, self.slow_ema2, self.signal_ema2, self.fast_window2, self.slow_window2, self.signal_window2)
        hist3, macd_line3, self.fast_ema3, self.slow_ema3, self.signal_ema3 = self.compute_macd(self.fast_ema3, self.slow_ema3, self.signal_ema3, self.fast_window3, self.slow_window3, self.signal_window3)
        
        if self.close > self.upper_support:
            self.direction = "long"
        elif self.close < self.lower_support:
            self.direction = "short"
        else:
            self.direction = None

        status = self.check_status()
        if status is not None:
            return status
        if not self.trade_window((9, 30), (14, 00)) and self.position is None:
            return None
        
        signal = None
        if self.position is None and self.activated:
            signal = self.enter_trade(hist1, hist2, hist3)
        elif self.position is not None and self.activated:
            signal = self.exit_trade(hist1, hist2, hist3)
        self.prev_hist1 = hist1
        self.prev_hist2 = hist2
        self.prev_hist3 = hist3
        return signal

    def enter_trade(self, hist1, hist2, hist3):
        vol_osc = self.compute_volume_oscillator(self.volumes)
        vol_avg = self.compute_ma(self.volumes, 3)
        if hist1 > 0 and hist2 > 0 and hist3 > 0 and self.prev_hist1 < hist1 and self.prev_hist2 < hist2:
            if self.direction == "long":
                signal = self.buy()
                swing_point = self.compute_swing(mode="low", lookback=10)
                self.stop_price = round(swing_point * (1 - self.stop_loss), 2)
                self.stop_price = round(self.low * (1 - self.stop_loss), 2)
                print(f"{self.ts} ENTRY (L): {self.entry_price}, STOP: {self.stop_price}")
                return signal
        if hist1 < 0 and hist2 < 0 and hist3 < 0 and self.prev_hist1 > hist1 and self.prev_hist2 > hist2:
            if self.direction == "short":
                signal = self.sell()
                swing_point = self.compute_swing(mode="high", lookback=10)
                self.stop_price = round(swing_point * (1 + self.stop_loss), 2)
                self.stop_price = round(self.high * (1 + self.stop_loss), 2)
                print(f"{self.ts} ENTRY (S): {self.entry_price}, STOP: {self.stop_price}")
                return signal
        
    def exit_trade(self, hist1, hist2, hist3):
        if self.position == "long" and hist1 < 0 and hist2 < 0:
            self.stop_price = round(self.close, 2)
            print(f"{self.ts} EXIT (L): {self.entry_price}, STOP: {self.stop_price}")
            return self.sell()
        if self.position == "short" and hist1 > 0 and hist2 > 0:
            self.stop_price = round(self.close, 2)
            print(f"{self.ts} EXIT (S): {self.entry_price}, STOP: {self.stop_price}")
            return self.buy()
        
    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.fast_window1,
                self.slow_window1,
                self.signal_window1,
                self.fast_window2,
                self.slow_window2,
                self.signal_window2,
                self.fast_window3,
                self.slow_window3,
                self.signal_window3,
            ) + 1
            self.upper_support, self.lower_support = self.donchian_channel(self.orb_window)
            self.activated = len(self.prices) > required_data

    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.fast_ema1 = None
            self.slow_ema1 = None
            self.signal_ema1 = None
            self.fast_ema2 = None
            self.slow_ema2 = None
            self.signal_ema2 = None
            self.fast_ema3 = None
            self.slow_ema3 = None
            self.signal_ema3 = None
            self.prev_hist1 = None
            self.prev_hist2 = None
            self.prev_hist3 = None
            return None

    def compute_macd(self, fast_ema, slow_ema, signal_ema, fast_window, slow_window, signal_window):
        price = self.prices[-1]

        fast_ema = self.compute_ema(fast_ema, price, fast_window)
        slow_ema = self.compute_ema(slow_ema, price, slow_window)

        macd = fast_ema - slow_ema
        signal_ema = self.compute_ema(signal_ema, macd, signal_window)
        hist = macd - signal_ema

        return hist, macd, fast_ema, slow_ema, signal_ema