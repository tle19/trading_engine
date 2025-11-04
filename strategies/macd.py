import numpy as np
from datetime import timedelta

from strategies import Strategy, RiskManager
from utils import *

class MACDIndicator(Strategy):
    def __init__(self, symbol, fast_window=8, slow_window=15, signal_window=7,
                 stop_loss=0.005, take_profit=0.03, trailing_ratio=0.05, position_size=1.0,
                 target=0.001, loss=-0.0025, force_close=True):
        super().__init__(symbol, stop_loss, take_profit, trailing_ratio, position_size, force_close)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.signal_window = signal_window

        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None

        self.prev_rsi = 50
        self.prev_hist = 0
        self.entry_hist = 0
        self.entry_rsi = None
        self.rsi_list = []

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
        
        if not self.trade_window((9, 30), (16, 00)) and self.position is None:
            self.prev_rsi = 50
            self.prev_hist = 0
            self.entry_hist = 0
            self.entry_rsi = 0
            self.rsi_list = []
            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
            return None
        
        hist = self.compute_macd()
        rsi = self.compute_rsi(self.prices, 6)
            
        if rsi is None:
            return None
        else:
            self.rsi_list.append(rsi)

        signal = None
        if self.position is None:
            signal = self.enter_trade(hist, rsi)
        else:
            signal = self.exit_trade(hist, rsi)
        self.prev_hist = hist
        self.prev_rsi = rsi
        return signal
    
    def enter_trade(self, hist, rsi):
        # ma = self.compute_ma(self.rsi_list[:-1], 5) # rolling rsi is much greater than entry rsi dont enter
        ma = self.compute_ma(self.volumes, 5)
        vol_cond = ma * 0.75 < self.volume < ma * 1.5
        if self.prev_hist < 0 and hist > 0 and self.prev_rsi < 30 and rsi > 30 and vol_cond:
            signal = self.buy() 
            self.stop_price = round(self.low * (1 - self.stop_loss), 2)
            self.entry_rsi = self.prev_rsi
            return signal
        if self.prev_hist > 0 and hist < 0 and self.prev_rsi > 70 and rsi < 70 and vol_cond:
            signal = self.sell() 
            self.stop_price = round(self.high * (1 + self.stop_loss), 2)
            self.entry_rsi = self.prev_rsi
            return signal
            # high spread/volume wary??
            # 2x volume nono, .5x volume nono, in between volume yes
            # early in entry rate at which rsi decreaes?
                
    def exit_trade(self, hist, rsi):
        # if self.stop_price <= self.entry_price:
        #     if self.close > self.entry_price * 1.0025:
        #         self.stop_price = self.entry_price
        if self.position == "long":
            if rsi < self.entry_rsi - 1:
                self.stop_price = round(self.close, 2)
                return self.sell()
        if self.position == "short":
            if rsi > self.entry_rsi + 1:
                self.stop_price = round(self.close, 2)
                return self.buy()
    
    def stochastic_fast(arr, k_period=14, d_period=3):
        arr = np.asarray(arr, dtype=float)
        if len(arr) < k_period:
            return None, None
        lows = np.minimum.accumulate(arr[::-1])[:k_period][::-1]
        highs = np.maximum.accumulate(arr[::-1])[:k_period][::-1]
        k_values = 100 * (arr[-k_period:] - lows) / (highs - lows + 1e-9)
        k = k_values[-1]
        d = np.mean(k_values[-d_period:])
        return k, d
    
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