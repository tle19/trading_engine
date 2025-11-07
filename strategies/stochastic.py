import numpy as np
from datetime import timedelta

from strategies import Strategy, RiskManager
from utils import *

class StochasticIndicator(Strategy):
    def __init__(self, symbol, fast_window=12, slow_window=26, signal_window=9, htf_window=50,
                 rsi_period=14, k_period=14, k_smooth=3, d_period=3, stoch_lower=20, stoch_upper=80,
                 vol_fast_window=14, vol_slow_window=28, vol_threshold=0.025,
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

        self.ema = None
        self.fast_ema = None
        self.slow_ema = None
        self.signal_ema = None
        self.stoch_signal = None # None, "long", "short"
        self.rolling_rsi = []

        # self.df = open_data(self.symbol)

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        # adaptive sl and tp based on ATR/volatility/spread

        status = self.check_status()
        if status is not None:
            return status
        
        if not self.trade_window((9, 30), (15, 30)) and self.position is None:
            self.ema = None
            self.fast_ema = None
            self.slow_ema = None
            self.signal_ema = None
            self.stoch_signal = None
            self.vol_fast_ema = None
            self.vol_slow_ema = None
            self.rolling_rsi = []
            return None
        
        ema = self.compute_ema(self.ema, self.prices[-1], self.htf_window)
        stoch_k, stoch_d = self.compute_stochastic(self.highs, self.lows, self.prices, self.k_period, self.k_smooth, self.d_period)
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        hist = self.compute_macd(self.fast_window, self.slow_window, self.signal_window)
        vol = self.compute_volume_oscillator(self.volumes, self.vol_fast_window, self.vol_slow_window)
        if rsi is not None:
            self.rolling_rsi.append(rsi)

        if stoch_k and stoch_d:
            if stoch_k < self.stoch_lower and stoch_d < self.stoch_lower:
                self.stoch_signal = "long"
            elif stoch_k > self.stoch_upper and stoch_d > self.stoch_upper:
                self.stoch_signal = "short"
            elif self.stoch_signal == "long" and (stoch_k > self.stoch_upper or stoch_d > self.stoch_upper):
                self.stoch_signal = None
            elif self.stoch_signal == "short" and (stoch_k < self.stoch_lower or stoch_d < self.stoch_lower):
                self.stoch_signal = None
        
        signal = None
        if self.position is None and len(self.prices) > self.slow_window and rsi is not None:
            signal = self.enter_trade(ema, stoch_k, stoch_d, rsi, hist, vol)
        # elif self.position is not None and rsi is not None:
        #     self.set_trailing_stop()
        # elif self.position is not None and rsi is not None:
        #     signal = self.exit_trade(rsi, hist)
        return signal

    def enter_trade(self, ema, stoch_k, stoch_d, rsi, hist, vol):
        if not (self.stoch_lower < min(stoch_k, stoch_d) and max(stoch_k, stoch_d) < self.stoch_upper):
            return None
        rsi_ma = self.compute_ma(self.rolling_rsi, 10)

        if self.stoch_signal == "long" and rsi > 55 and rsi > rsi_ma and hist > 0 and rsi_ma < 50:
            if self.close > ema or vol > self.vol_threshold:
                signal = self.buy() 
                self.stop_price = round(self.low * (1 - self.stop_loss), 2)
                stop_dist = self.entry_price -  self.stop_price
                self.profit_price = round(self.entry_price + (stop_dist * self.take_profit), 2)
                # print(f"{self.ts} ENTRY (L): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
                return signal
        if self.stoch_signal == "short" and rsi < 45 and rsi < rsi_ma and hist < 0 and rsi_ma > 50:
            if self.close < ema or vol > self.vol_threshold:
                signal = self.sell() 
                self.stop_price = round(self.high * (1 + self.stop_loss), 2)
                stop_dist = self.stop_price - self.entry_price
                self.profit_price = round(self.entry_price - (stop_dist * self.take_profit), 2)
                # print(f"{self.ts} ENTRY (S): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
                return signal
        
    def exit_trade(self, rsi, hist):
        if self.position == "long" and rsi < 45 and hist < 0:
            self.stop_price = round(self.close, 2)
            # print(f"{self.ts} EXIT (L): {self.entry_price}, STOP: {self.stop_price}")
            return self.sell()
        if self.position == "short" and rsi > 55 and hist > 0:
            self.stop_price = round(self.close, 2)
            # print(f"{self.ts} EXIT (S): {self.entry_price}, STOP: {self.stop_price}")
            return self.buy()
        
    def regime_filter(self): # implement to be called directly with for loop of symbols
        if self.trade_window((9, 30), (9, 30)):
            end_date = self.ts.date()
            start_date = end_date - timedelta(days=50)
            mask = (self.df['timestamp'].dt.date >= pd.to_datetime(start_date).date()) & \
                (self.df['timestamp'].dt.date <= pd.to_datetime(end_date).date())
            df = self.df.loc[mask].copy()
            df.set_index('timestamp', inplace=True)
            df = df.resample('1D', offset='9h30min').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                "volume": 'sum'
            }).dropna()

            prev_opens = df['open'].iloc[-30:].tolist()
            prev_rsi = self.compute_rsi(prev_opens[:-1], 14)
            curr_rsi = self.compute_rsi(np.append(prev_opens, self.open), 14)

            volatility = None #calculate implied volatility

            if volatility == "very_high":
                self.position_size = 1.0
            elif volatility == "high":
                self.position_size = 0.75
            elif volatility == "medium":
                self.position_size = 0.5
            elif volatility == "low":
                self.position_size = 0.5