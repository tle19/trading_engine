from collections import deque

from strategies import Strategy, RiskManager
from utils import *

class MACDIndicator(Strategy):
    def __init__(self, symbol, fast_window=4, slow_window=9, signal_window=7, htf_window=50,
                 stop_loss=0.001, take_profit=0.005, position_size=1.0,
                 target=0.001, loss=-0.001):
        super().__init__(symbol, stop_loss, take_profit, position_size)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.htf_window = htf_window

        self.ema = None
        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None
        self.prev_hist = None

        self.momentum_history = deque(maxlen=5)
        self.consolodation = False
        self.breakout = False
        self.retest = False
        self.direction = None

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()
        
        self.ema = self.compute_ema(self.ema, self.prices[-1], self.htf_window)
        hist, macd_line, signal_line = self.compute_macd(self.fast_window, self.slow_window, self.signal_window)
        momentum = (macd_line + signal_line) / 2
        self.momentum_history.append(momentum)
        
        status = self.check_status()
        if status is not None:
            return status
        if not self.trade_window((9, 30), (15, 30)) and self.position is None:
            return None
        
        signal = None
        if self.position is None and self.activated:
            signal = self.enter_trade(hist, momentum)
        elif self.position is not None:
            self.breakout = False
            self.retest = False
            self.direction = None
            signal = self.exit_trade(hist)
        self.prev_hist = hist
        return signal

    def enter_trade(self, hist, momentum):
        # find consolodation range based on history?
        # ema to trade with trend
        self.consolodation = all(abs(m) < 0.1 for m in self.momentum_history)
        if self.consolodation and not self.breakout and not self.retest:
            if momentum > 0:
                if self.prev_hist < 0 and hist > 0:
                    self.breakout = True
                    self.direction = "long"
            elif momentum < 0:
                if self.prev_hist > 0 and hist < 0:
                    self.breakout = True
                    self.direction = "short"
        elif self.breakout and not self.retest:
            if momentum > 0 and self.direction == "long":
                if self.prev_hist < 0 and hist > 0:
                    self.retest = True
            elif momentum < 0 and self.direction == "short":
                if self.prev_hist > 0 and hist < 0:
                    self.retest = True
            elif (momentum < 0 and self.direction == "long") or (momentum > 0 and self.direction == "short"):
                self.breakout = False
                self.direction = None

        if not (self.breakout and self.retest):
            return None
        if self.direction == "long":
            signal = self.buy()
            self.stop_price = round(self.low * (1 - self.stop_loss), 2)
            # print(f"{self.ts} ENTRY (L): {self.entry_price}, STOP: {self.stop_price}")
            return signal
        if self.direction == "short":
            signal = self.sell()
            self.stop_price = round(self.high * (1 + self.stop_loss), 2)
            # print(f"{self.ts} ENTRY (S): {self.entry_price}, STOP: {self.stop_price}")
            return signal
        
    def exit_trade(self, hist):
        if self.position == "long" and self.prev_hist > 0 and hist < 0 and self.close > self.entry_price:
            self.stop_price = round(self.close, 2)
            # print(f"{self.ts} EXIT (L): {self.entry_price}, STOP: {self.stop_price}")
            return self.sell()
        if self.position == "short" and self.prev_hist < 0 and hist > 0 and self.close < self.entry_price:
            self.stop_price = round(self.close, 2)
            # print(f"{self.ts} EXIT (S): {self.entry_price}, STOP: {self.stop_price}")
            return self.buy()
        
    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.fast_window,
                self.slow_window,
                self.signal_window,
            ) + 1
            self.activated = len(self.prices) > required_data

    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
            self.prev_hist = None
            self.momentum_history = deque(maxlen=5)
            self.consolodation = False
            self.breakout = False
            self.retest = False
            self.direction = None
            return None
