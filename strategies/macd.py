import numpy as np
from datetime import timedelta

from strategies import Strategy, RiskManager
from utils import *

class MACDIndicator(Strategy):
    def __init__(self, symbol, fast_window=12, slow_window=26, signal_window=9, rsi_period=14,
                 stop_loss=0.005, take_profit=1.5, trailing_ratio=0.05, position_size=1.0,
                 target=0.001, loss=-0.0025, force_close=True):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, force_close)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window
        self.rsi_period = rsi_period

        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None

        self.stoch_signal = None # None, "long", "short"
        self.prev_rsi = 50

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()

        status = self.check_status()
        if status is not None:
            return status
        
        # self.risk_manager.daily_risk_target()
        # if self.risk_manager.is_day_pause():
        #     return None
        
        if not self.trade_window((9, 30), (15, 30)) and self.position is None:
            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
            self.stoch_signal = None
            self.prev_rsi = 50
            return None
        
        stoch_k, stoch_d = self.compute_stochastic(self.highs, self.lows, self.prices)
        hist = self.compute_macd(self.prices, self.fast_window, self.slow_window, self.signal_window)
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        
        signal = None
        if self.position is None and hist != 0:
            signal = self.enter_trade(stoch_k, stoch_d, rsi, hist)
        self.prev_rsi = rsi
        return signal
    
    def enter_trade(self, stoch_k, stoch_d, rsi, hist):
        # ma = self.compute_ma(self.volumes, 5)
        # vol_cond = ma * 0.75 < self.volume < ma * 1.5
        if stoch_k < 20 and stoch_d < 20:
            self.stoch_signal = "long"
        elif stoch_k > 80 and stoch_d > 80:
            self.stoch_signal = "short"
       
        if self.stoch_signal == "long" and 20 < stoch_k < 80 and 20 < stoch_d < 80 and rsi > 55 and hist > 0:
            signal = self.buy() 
            self.stop_price = round(self.low * (1 - self.stop_loss), 2)
            stop_dist = self.entry_price - self.stop_price
            self.profit_price = round(self.entry_price + (stop_dist * self.take_profit), 2)
            # print(self.ts, self.stoch_signal, self.entry_price, self.stop_price, self.profit_price)
            return signal
        if self.stoch_signal == "short" and 20 < stoch_k < 80 and 20 < stoch_d < 80 and rsi < 45 and hist < 0:
            signal = self.sell() 
            self.stop_price = round(self.high * (1 + self.stop_loss), 2)
            stop_dist = self.stop_price - self.entry_price
            self.profit_price = round(self.entry_price - (stop_dist * self.take_profit), 2)
            # print(self.ts, self.stoch_signal, self.entry_price, self.stop_price, self.profit_price)
            return signal
                
    def compute_stochastic(self, high, low, close, k_period=14, k_smooth=3, d_period=3):
        if len(close) < k_period + k_smooth + d_period - 2:
            return None, None

        k_values = []
        for i in range(k_smooth):
            h = np.max(high[-k_period - i:-i or None])
            l = np.min(low[-k_period - i:-i or None])
            k_values.append(100 * (close[-1 - i] - l) / (h - l + 1e-9))
        k = np.mean(k_values)

        d_values = []
        for i in range(d_period):
            if len(close) - i < k_period + k_smooth - 1:
                break
            sub_k = []
            for j in range(k_smooth):
                h = np.max(high[-k_period - i - j:-i - j or None])
                l = np.min(low[-k_period - i - j:-i - j or None])
                sub_k.append(100 * (close[-1 - i - j] - l) / (h - l + 1e-9))
            d_values.append(np.mean(sub_k))
        d = np.mean(d_values)

        return k, d
    
    def compute_macd(self, prices, fast_window=12, slow_window=26, signal_window=9):
        if len(prices) < slow_window + signal_window:
            return 0
        price = self.close

        if self.fast_ema is None:
            self.fast_ema = price
            self.slow_ema = price
            self.signal_ema = 0
            return 0

        alpha_fast = 2 / (fast_window + 1)
        alpha_slow = 2 / (slow_window + 1)
        alpha_signal = 2 / (signal_window + 1)

        self.fast_ema = alpha_fast * price + (1 - alpha_fast) * self.fast_ema
        self.slow_ema = alpha_slow * price + (1 - alpha_slow) * self.slow_ema

        macd = self.fast_ema - self.slow_ema
        self.signal_ema = alpha_signal * macd + (1 - alpha_signal) * self.signal_ema

        hist = macd - self.signal_ema
        return hist

    # def short_term_regime(self):
    #     if self.trade_window((9, 30), (9, 30)):
    #         end_date = self.ts.date()
    #         start_date = end_date - timedelta(days=30)
    #         df = open_data(self.symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    #         df.set_index('timestamp', inplace=True)
    #         df = df.resample('1D', offset='9h30min').agg({
    #             'open': 'first',
    #             'high': 'max',
    #             'low': 'min',
    #             'close': 'last'
    #         }).dropna()

    #         self.prev_closes = df['open'].iloc[-15:].tolist()
    #         self.prev_rsi = self.compute_rsi(self.prev_closes, 10)

    #     price_series = np.append(self.prev_closes, self.open)

    #     prev_rsi = self.prev_rsi
    #     rsi = self.compute_rsi(price_series, 10)

    #     neutral_band = 5
    #     rsi_upper = 80
    #     rsi_lower = 20
    #     if rsi >= rsi_upper:
    #         self.mode = "short"
    #     elif rsi <= rsi_lower:
    #         self.mode = "long"
    #     elif rsi > prev_rsi + neutral_band:
    #         self.mode = "long"
    #     elif rsi < prev_rsi - neutral_band:
    #         self.mode = "short"
    #     else:
    #         self.mode = "both"
        
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