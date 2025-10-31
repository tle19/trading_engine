import numpy as np
from strategies import Strategy, RiskManager

class MACDIndicator(Strategy):
    def __init__(self, symbol, fast_window=8, slow_window=15, signal_window=8,
                 stop_loss=0.01, take_profit=0.03, trailing_ratio=0.05, position_size=1.0,
                 target=0.03, loss=-0.0025, force_close=True):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, force_close)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window

        self.prev_hist = None
        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()

        status = self.check_status()
        if status is not None:
            return status
        if len(self.prices) < self.slow_window + self.signal_window:
            return None
        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
            return None
        
        hist = self.compute_macd()
        # hist *= -1
        if self.prev_hist is None:
            self.prev_hist = hist
            return None
        
        signal = None
        if self.position is None:
            signal = self.enter_trade(hist)
        elif self.position == "long":
            signal = self.exit_trade(hist)
        self.prev_hist = hist
        return signal
    
    def enter_trade(self, hist):
        if self.prev_hist < 0 and hist > 0:
            return self.buy()
        
    def exit_trade(self, hist):
        # if self.stop_price <= self.entry_price:
        #     if self.close > self.entry_price * 1.0025:
        #         self.stop_price = self.entry_price * 0.9975
        if self.prev_hist > 0 and hist < 0:
            self.stop_price = self.close
            return self.sell()
    
    def compute_macd(self):
        arr = np.array(self.prices)
        fast_ema = self.compute_ema(arr, self.fast_window)
        slow_ema = self.compute_ema(arr, self.slow_window)

        macd = fast_ema - slow_ema
        signal = self.compute_ema(macd, self.signal_window)

        hist = macd[-1] - signal[-1]
        return hist

    def compute_macd(self):
        price = self.close

        if self.fast_ema is None:
            self.fast_ema = price
            self.slow_ema = price
            self.signal_ema = 0
            return 0

        alpha_fast = 2 / (self.fast_window + 1)
        alpha_slow = 2 / (self.slow_window + 1)
        alpha_signal = 2 / (self.signal_window + 1)

        self.fast_ema = alpha_fast * price + (1 - alpha_fast) * self.fast_ema
        self.slow_ema = alpha_slow * price + (1 - alpha_slow) * self.slow_ema

        macd = self.fast_ema - self.slow_ema

        self.signal_ema = alpha_signal * macd + (1 - alpha_signal) * self.signal_ema

        hist = macd - self.signal_ema
        return hist

    def compute_ema(self, data, window):
        alpha = 2 / (window + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
        return ema