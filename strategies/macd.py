import numpy as np
from datetime import timedelta

from strategies import Strategy, RiskManager
from utils import *

class MACDIndicator(Strategy):
    def __init__(self, symbol, fast_window=8, slow_window=15, signal_window=7,
                 stop_loss=0.005, take_profit=0.02, trailing_ratio=0.05, position_size=1.0,
                 target=0.03, loss=-0.0025, force_close=True):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, force_close)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window

        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None

        self.prev_hist = 0
        self.hist_length = 0

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()

        status = self.check_status()
        if status is not None:
            return status
        
        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
            self.prev_hist = 0
            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
            return None
        
        hist = self.compute_macd()

        if hist < 0:
            self.hist_length += 1
        elif hist > 0 and self.hist_length <= 5:
            self.hist_length = 0

        signal = None
        if self.position is None:
            signal = self.enter_trade(hist)
        elif self.position == "long":
            signal = self.exit_trade(hist)
        self.prev_hist = hist
        return signal
    
    def enter_trade(self, hist):
        if self.prev_hist < 0 and hist > 0:
            if self.hist_length > 5:
                self.hist_length = 0
                return self.buy()
                
    def exit_trade(self, hist):
        # if self.stop_price <= self.entry_price:
        #     if self.close > self.entry_price * 1.005:
        #         self.stop_price = self.entry_price * 1.0025
        if self.prev_hist > 0 and hist < 0:
            self.stop_price = round(self.close, 2)
            return self.sell()

    def compute_macd(self):
        if len(self.prices) < self.slow_window + self.signal_window:
            return 0
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

    def short_term_regime(self):
        if self.trade_window((9, 30), (9, 30)):
            end_date = self.ts.date()
            start_date = end_date - timedelta(days=30)
            df = open_data(self.symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            df.set_index('timestamp', inplace=True)
            df = df.resample('1D', offset='9h30min').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last'
            }).dropna()

            self.prev_closes = df['open'].iloc[-15:].tolist()
            self.prev_rsi = self.compute_rsi(self.prev_closes, 10)

        price_series = np.append(self.prev_closes, self.open)

        prev_rsi = self.prev_rsi
        rsi = self.compute_rsi(price_series, 10)

        neutral_band = 5
        rsi_upper = 80
        rsi_lower = 20
        if rsi >= rsi_upper:
            self.mode = "short"
        elif rsi <= rsi_lower:
            self.mode = "long"
        elif rsi > prev_rsi + neutral_band:
            self.mode = "long"
        elif rsi < prev_rsi - neutral_band:
            self.mode = "short"
        else:
            self.mode = "both"

        
    # def compute_macd(self):
    #     arr = np.array(self.prices)
    #     fast_ema = self.compute_ema(arr, self.fast_window)
    #     slow_ema = self.compute_ema(arr, self.slow_window)

    #     macd = fast_ema - slow_ema
    #     signal = self.compute_ema(macd, self.signal_window)

    #     hist = macd[-1] - signal[-1]
    #     return hist
    
    # def compute_ema(self, data, window):
    #     alpha = 2 / (window + 1)
    #     ema = np.zeros_like(data)
    #     ema[0] = data[0]
    #     for i in range(1, len(data)):
    #         ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
    #     return ema