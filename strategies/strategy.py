import numpy as np

from utils import *

LONG = 1
SHORT = -1
EXIT = 0
HOLD = None

class Strategy:
    def __init__(self, symbol, stop_loss=0.01, take_profit=0.02, trailing_ratio=0.15,  
                 position_size=1.0, tf=1):
        self.symbol = symbol
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trailing_ratio = trailing_ratio
        self.default_position_size = position_size
        self.position_size = position_size
        self.tf = tf

        self.position = None
        self.trailing_stop = False
        self.entry_price = None
        self.stop_price = None
        self.profit_price = None

        self.open = None
        self.close = None
        self.high = None
        self.low = None
        self.volume = None
        self.ts = None

        self.highs = []
        self.lows = []
        self.prices = []
        self.volumes = [] 

        self.risk_manager = RiskManager()
        
    def generate_signal(self, row):
        raise NotImplementedError
    
    def enter_trade(self):
        raise NotImplementedError
    
    def exit_trade(self):
        raise NotImplementedError
    
    def update(self, row=None): 
        if row is not None:
            self.open = round(row.open, 2)
            self.close = round(row.close, 2)
            self.high = round(row.high, 2)
            self.low = round(row.low, 2)
            self.volume = row.volume
            self.ts = row.timestamp

        self.prices.append(self.close)
        # self.prices.append((self.close + self.high + self.low) / 3)
        self.highs.append(self.high)
        self.lows.append(self.low)
        self.volumes.append(self.volume)

    def check_status(self):
        if self.position == "long":
            if self.stop_price >= self.profit_price:
                raise ValueError("Invalid long: stop >= profit")
            if self.low <= self.stop_price or self.high >= self.profit_price:
                return self.sell()
            elif not self.trade_window((9, 30), (15, 57)):
                return self.sell()
        elif self.position == "short":
            if self.stop_price <= self.profit_price:
                raise ValueError("Invalid short: stop <= profit")
            if self.high >= self.stop_price or self.low <= self.profit_price:
                return self.buy()
            elif not self.trade_window((9, 30), (15, 57)):
                return self.buy()
            
    def buy(self):
        if self.position is None:
            self.position = "long"
            self.entry_price = self.close
            self.stop_price = round(self.entry_price * (1 - self.stop_loss), 2)
            self.profit_price = round(self.entry_price * (1 + self.take_profit), 2)
            return LONG
        elif self.position == "short":
            return EXIT
    
    def sell(self):
        if self.position is None:
            self.position = "short"
            self.entry_price = self.close
            self.stop_price = round(self.entry_price * (1 + self.stop_loss), 2)
            self.profit_price = round(self.entry_price * (1 - self.take_profit), 2)
            return SHORT
        elif self.position == "long":
            return EXIT

    def flatten(self):
        self.position_size = self.default_position_size
        self.position = None
        self.trailing_stop = False
        self.entry_price = None
        self.entry_price = None
        self.stop_price = None
        self.profit_price = None

    def set_trailing_stop(self):
        self.trailing_stop = False
        if not self.in_safe_range():
            return None
        
        trailing_ratio = self.get_trailing_ratio(self.stop_price)
        adjustment = trailing_ratio * abs(self.stop_price - self.close)

        if self.position == "long" and self.close > self.entry_price:
            self.stop_price = round(self.stop_price + adjustment, 2)
            self.trailing_stop = True

        elif self.position == "short" and self.close < self.entry_price:
            self.stop_price = round(self.stop_price - adjustment, 2)
            self.trailing_stop = True

    def get_trailing_ratio(self, price):
        min_distance = self.compute_min_distance()
        distance = abs(price - self.close)

        max_ratio = 1 - (min_distance / distance)
        trailing_ratio = min(self.trailing_ratio, max_ratio)

        return trailing_ratio
    
    def compute_min_distance(self, min_dist_ratio=0.5):
        spread = self.compute_spread()
        min_dist = spread * min_dist_ratio
        return min_dist
    
    def compute_spread(self, stability_window=10):
        if len(self.prices) < stability_window:
            return None

        spread = self.compute_ma(self.highs, stability_window) - self.compute_ma(self.lows, stability_window)
        return spread
    
    def in_safe_range(self):
        min_distance = self.compute_min_distance()
        stop_distance = abs(self.stop_price - self.close)
        profit_distance = abs(self.profit_price - self.close)

        if min_distance is None:
            return False
        elif stop_distance > min_distance and profit_distance > min_distance:
            return True

    def compute_ma(self, data, window):
        return np.mean(data[-window:])
    
    def compute_ema(self, prev_ema, new_value, window):
        if prev_ema is None:
            return new_value
        alpha = 2.0 / (window + 1.0)
        return alpha * new_value + (1.0 - alpha) * prev_ema
    
    def compute_rsi(self, prices, period=14, mode="wilder"):
        p = np.asarray(prices, dtype=float)
        if p.size < period + 1:
            return None

        deltas = np.diff(p)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        if gains.size < period:
            return None

        seed_gain = gains[:period].mean()
        seed_loss = losses[:period].mean()

        if mode == "simple":
            avg_gain = gains[-period:].mean()
            avg_loss = losses[-period:].mean()
        else:
            avg_gain = seed_gain
            avg_loss = seed_loss
            if mode == "wilder":
                for g, l in zip(gains[period:], losses[period:]):
                    avg_gain = (avg_gain * (period - 1) + g) / period
                    avg_loss = (avg_loss * (period - 1) + l) / period
            elif mode == "exponential":
                alpha = 2.0 / (period + 1)
                for g, l in zip(gains[period:], losses[period:]):
                    avg_gain = (1 - alpha) * avg_gain + alpha * g
                    avg_loss = (1 - alpha) * avg_loss + alpha * l
            else:
                raise ValueError("mode must be 'simple','wilder' or 'exponential'")

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
    
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
    
    def compute_macd(self, fast_window=12, slow_window=26, signal_window=9):
        price = self.prices[-1]
        self.fast_ema = self.compute_ema(self.fast_ema, price, fast_window)
        self.slow_ema = self.compute_ema(self.slow_ema, price, slow_window)

        macd = self.fast_ema - self.slow_ema
        self.signal_ema = signal = self.compute_ema(self.signal_ema, macd, signal_window)

        hist = macd - signal
        return hist
    
    def compute_volume_oscillator(self, data, fast_window=7, slow_window=12):
        vol_fast_ma = self.compute_ma(data, fast_window)
        vol_slow_ma = self.compute_ma(data, slow_window)

        if vol_slow_ma == 0 or vol_slow_ma is None:
            return 0.0
        return (vol_fast_ma - vol_slow_ma) / vol_slow_ma
    
    def donchian_channel(self, window):
        upper_band = max(self.highs[-window:])
        lower_band = min(self.lows[-window:])
        return upper_band, lower_band
    
    def trade_window(self, start, end):
        return start <= (self.ts.hour, self.ts.minute) <= end
           
    def reset_data(self):
        if self.trade_window((9, 30), (9, 30)):
            self.prices = [self.prices[-1]]
            self.highs = [self.highs[-1]]
            self.lows = [self.lows[-1]]
            self.volumes = [self.volumes[-1]]
            self.risk_manager.reset_risk()

    def is_trailing_stop(self):
        return self.trailing_stop
    
    def get_stop_price(self):
        return self.stop_price
    
    def get_profit_price(self):
        return self.profit_price
    
    def get_position(self):
        return self.position
    
    def get_position_size(self):
        return self.position_size
    
    def get_entry_price(self):
        return self.entry_price

    def get_risk_manager(self):
        return self.risk_manager
    
    def get_tf(self):
        return self.tf
       
    def update_entry_price(self, fill_price):
        self.entry_price = float(fill_price)

class RiskManager:
    def __init__(self, risk_threshold=3, pause_duration=5, pnl_target=0.02, pnl_loss=-0.001):
        self.risk_threshold = risk_threshold
        self.pause_duration = pause_duration
        self.pnl_target = pnl_target
        self.pnl_loss = pnl_loss
        self.start_cash = 0
        self.pnl = 0
        self.risk = 0
        self.day_pause = False
        self.pause = False
        self._pause_counter = 0

    def set_start_cash(self, cash):
        self.start_cash = cash

    def check_risk(self, pnl):
        self.pnl += pnl
        if not self.is_trade_pause():
            if pnl < 0:
                self.risk += 1
            elif pnl > 0:
                self.risk = max(0, self.risk - 1)

    def intraday_risk(self):
        if self.risk >= self.risk_threshold:
            self.pause = True

    def tick(self):
        if self.is_trade_pause():
            self._pause_counter += 1
            if self._pause_counter >= self.pause_duration:
                self.risk = 0
                self.pause = False
                self._pause_counter = 0

    def daily_risk_target(self):
        target = self.pnl / self.start_cash
        if target >= self.pnl_target:
            self.day_pause = True

    def daily_risk_stop(self):
        stop = self.pnl / self.start_cash
        if stop <= self.pnl_loss:
            self.day_pause = True
    
    def dynamic_position_sizing(self, position_size):
        if self.pnl >= self.pnl_target:
            ratio = self.pnl / self.pnl_target
            scale = 0.5 / ratio
            return position_size * scale
        return position_size

    def reset_risk(self):
        self.pnl = 0
        self.risk = 0
        self.day_pause = False
        self.pause = False
        self._pause_counter = 0

    def is_trade_pause(self):
        return self.pause
    
    def is_day_pause(self):
        return self.day_pause
