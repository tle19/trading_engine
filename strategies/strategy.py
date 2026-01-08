import numpy as np
import pickle

from utils import *

LONG = 1
SHORT = -1
ADJUST = 9
EXIT = 0
HOLD = None

class Strategy:
    def __init__(self, symbol, stop_loss=0.01, take_profit=0.02, 
                 position_size=1.0, trailing_ratio=0.15, pyramid=False,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=5):
        self.symbol = symbol
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.position_size = position_size
        self.trailing_ratio = trailing_ratio
        self.pyramid = pyramid

        self.open = None
        self.close = None
        self.high = None
        self.low = None
        self.volume = None
        self.ts = None

        self.prices = []
        self.opens = []
        self.closes = []
        self.highs = []
        self.lows = []
        self.volumes = [] 

        self.activated = False
        self.model = None
        self.features = {}

        self.position_manager = PositionManager(pyramid)
        self.risk_manager = RiskManager(pnl_target=pnl_target, pnl_loss=pnl_loss, trade_max=trade_max)

    def generate_signal(self, row):
        raise NotImplementedError
    
    def enter_trade(self):
        raise NotImplementedError
    
    def exit_trade(self):
        return self.exit()

    def compute_indicators(self):
        raise NotImplementedError
    
    def reset_indicators(self):
        raise NotImplementedError
        
    def minimum_computations(self):
        raise NotImplementedError
    
    def add_features(self, direction, stop_price, target_price):
        self.features = {}
    
    def predict_trade(self, threshold=0.5):
        raise NotImplementedError
    
    def update(self, row=None): 
        if row is not None:
            self.open = row.open
            self.close = row.close
            self.high = row.high
            self.low = row.low
            self.volume = row.volume
            self.ts = row.timestamp

        self.price = self.close  # (self.close + self.open + self.high) / 3
        self.prices.append(self.price)
        self.opens.append(self.open)
        self.closes.append(self.close)
        self.highs.append(self.high)
        self.lows.append(self.low)
        self.volumes.append(self.volume)
        self.features = {}
                   
    def reset_data(self):
        if self.trade_window((9, 30), (9, 30)):
            self.prices = [self.price]
            self.opens = [self.open]
            self.closes = [self.close]
            self.highs = [self.high]
            self.lows = [self.low]
            self.volumes = [self.volume]
            self.position_manager.flatten()
            self.risk_manager.reset()
            self.activated = False
            self.features = {}

    def trade_window(self, start, end):
        return start <= (self.ts.hour, self.ts.minute) <= end
        
    def buy(self):
        direction = self.position_manager.direction()
        if direction in (1, 0):
            entry_price = round(self.price, 2)
            stop_price = round(entry_price * (1 - self.stop_loss), 2)
            target_price = round(entry_price * (1 + self.take_profit), 2)

            pos_leg = PositionLeg(
                direction=1,
                timestamp=self.ts,
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                position_size=self.position_size,
                cash=self.risk_manager.start_cash
            )

            if self.model and not self.features:
                self.add_features(1, stop_price, target_price)
                return self.predict_trade()
            if self.position_manager.add_leg(pos_leg):
                self.add_features(1, stop_price, target_price)
                return (LONG, pos_leg)
            return (HOLD, None)
        elif direction == -1:
            return HOLD, None
        
    def sell(self):
        direction = self.position_manager.direction()
        if direction in (-1, 0):
            entry_price = round(self.price, 2)
            stop_price = round(entry_price * (1 + self.stop_loss), 2)
            target_price = round(entry_price * (1 - self.take_profit), 2)

            pos_leg = PositionLeg(
                direction=-1,
                timestamp=self.ts,
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                position_size=self.position_size,
                cash=self.risk_manager.start_cash
            )

            if self.model and not self.features:
                self.add_features(-1, stop_price, target_price)
                return self.predict_trade()
            if self.position_manager.add_leg(pos_leg):
                self.add_features(-1, stop_price, target_price)
                return (SHORT, pos_leg)
            return (HOLD, None)
        elif direction == 1:
            return HOLD, None
          
    def exit(self): # implement non-static exits
        for leg in self.position_manager.legs:
            if leg.check_exit(self.ts, self.low, self.high) == EXIT:
                return EXIT
        return HOLD
    
    def set_trailing_stop(self):
        if not self.in_safe_range():
            return None
        
        trailing_ratio = self.compute_trailing_ratio(self.stop_price)
        adjustment = trailing_ratio * abs(self.stop_price - self.price)

        if self.position == 1 and self.price > self.entry_price:
            self.stop_price = round(self.stop_price + adjustment, 2)

        elif self.position == -1 and self.price < self.entry_price:
            self.stop_price = round(self.stop_price - adjustment, 2)

    def compute_trailing_ratio(self, price):
        min_distance = self.compute_min_distance()
        distance = abs(price - self.price)

        max_ratio = 1 - (min_distance / distance)
        trailing_ratio = min(self.trailing_ratio, max_ratio)

        return trailing_ratio
    
    def compute_min_distance(self, min_dist_ratio=0.5):
        spread = self.compute_spread()
        min_dist = spread * min_dist_ratio
        return min_dist
    
    def in_safe_range(self):
        min_distance = self.compute_min_distance()
        stop_distance = abs(self.stop_price - self.price)
        target_distance = abs(self.target_price - self.price)

        if min_distance is None:
            return False
        elif stop_distance > min_distance and target_distance > min_distance:
            return True

    def compute_ma(self, data, window=10):
        data = np.array(data)
        return np.mean(data[-window:])
    
    def compute_ema(self, prev_ema, new_value, window=10):
        if prev_ema is None:
            return new_value
        alpha = 2.0 / (window + 1.0)
        return alpha * new_value + (1.0 - alpha) * prev_ema
    
    def compute_spread(self, window=5):
        spread = self.compute_ma(self.highs, window) - self.compute_ma(self.lows, window)
        return spread
       
    def compute_rsi(self, prices, period=14):
        p = np.asarray(prices, dtype=float)
        if len(p) < 2:
            return 50.0

        deltas = np.diff(p)
        gains = np.maximum(deltas, 0.0)
        losses = np.maximum(-deltas, 0.0)

        actual_period = min(period, len(p) - 1)
        avg_gain = gains[:actual_period].mean()
        avg_loss = losses[:actual_period].mean()

        for g, l in zip(gains[actual_period:], losses[actual_period:]):
            avg_gain = (avg_gain * (period - 1) + g) / period
            avg_loss = (avg_loss * (period - 1) + l) / period

        if avg_loss == 0:
            return 100.0
        if avg_gain == 0:
            return 0.0

        rs = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + rs)
    
    def compute_stochastic(self, high, low, close, k_period=14, k_smooth=3, d_period=3):
        n = len(close)
        if n == 0:
            return 50.0, 50.0

        def compute_k(end_idx):
            start_idx = max(0, end_idx - k_period)
            window_h = high[start_idx:end_idx]
            window_l = low[start_idx:end_idx]
            if len(window_h) == 0:
                return 50.0
            h = max(window_h)
            l = min(window_l)
            return 50.0 if h == l else 100.0 * (close[end_idx - 1] - l) / (h - l)

        k_values = [compute_k(n - i) for i in range(k_smooth)]
        k = sum(k_values) / len(k_values) if k_values else 50.0

        d_values = [sum(compute_k(n - i - j) for j in range(k_smooth)) / k_smooth
                    for i in range(d_period)]
        d = sum(d_values) / len(d_values) if d_values else 50.0

        return k, d
    
    def compute_macd(self, fast_window=12, slow_window=26, signal_window=9):
        self.fast_ema = self.compute_ema(self.fast_ema, self.price, fast_window)
        self.slow_ema = self.compute_ema(self.slow_ema, self.price, slow_window)

        macd = self.fast_ema - self.slow_ema
        self.signal_ema = self.compute_ema(self.signal_ema, macd, signal_window)
        hist = macd - self.signal_ema
        
        return hist, macd, self.signal_ema
    
    def compute_volume_oscillator(self, data, fast_window=14, slow_window=28):
        vol_fast_ma = self.compute_ma(data, fast_window)
        vol_slow_ma = self.compute_ma(data, slow_window)

        return (vol_fast_ma - vol_slow_ma) / vol_slow_ma
    
    def donchian_channel(self, period):
        upper_band = max(self.highs[-period:])
        lower_band = min(self.lows[-period:])
        return upper_band, lower_band
        
    def compute_atr(self, highs, lows, closes, period=14):
        highs = np.array(highs)
        lows = np.array(lows)
        closes = np.array(closes)

        if len(closes) < 2:
            return 2.5

        tr = np.maximum.reduce([
            highs[1:] - lows[1:],
            np.abs(highs[1:] - closes[:-1]),
            np.abs(lows[1:]  - closes[:-1])
        ])
        
        atr = np.mean(tr[:period])
        for t in tr[period:]:
            atr = (atr * (period - 1) + t) / period 

        return atr
    
    def compute_adx(self, highs, lows, closes, period=14):
        highs = np.array(highs)
        lows = np.array(lows)
        closes = np.array(closes)

        n = len(highs)
        if n < 2:
            return 20.0

        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]
        plus_dm  = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        tr = np.maximum.reduce([
            highs[1:] - lows[1:],
            np.abs(highs[1:] - closes[:-1]),
            np.abs(lows[1:]  - closes[:-1])
        ])

        actual_period = min(period, len(tr))
        tr_sum = tr[:actual_period].sum()
        plus_dm_sum = plus_dm[:actual_period].sum()
        minus_dm_sum = minus_dm[:actual_period].sum()

        dx_vals = []
        pdi = (plus_dm_sum / tr_sum * 100) if tr_sum > 0 else 0
        mdi = (minus_dm_sum / tr_sum * 100) if tr_sum > 0 else 0
        dx_vals.append(abs(pdi - mdi) / (pdi + mdi + 1e-9) * 100)

        for i in range(actual_period, len(tr)):
            tr_sum = tr_sum - tr_sum / period + tr[i]
            plus_dm_sum = plus_dm_sum - plus_dm_sum / period + plus_dm[i]
            minus_dm_sum = minus_dm_sum - minus_dm_sum / period + minus_dm[i]

            pdi = plus_dm_sum / tr_sum * 100
            mdi = minus_dm_sum / tr_sum * 100
            dx_vals.append(abs(pdi - mdi) / (pdi + mdi + 1e-9) * 100)

        adx = np.mean(dx_vals[:actual_period])
        for d in dx_vals[actual_period:]:
            adx = (adx * (period - 1) + d) / period

        return adx
    
    def compute_swing(self, mode="high", lookback=10): # fix swing
        arr = self.highs[-lookback:] if mode == "high" else self.lows[-lookback:]
        c = self.price
        n = len(arr)

        if n < 3:
            return max(arr) if mode == "high" else min(arr)
        
        for i in range(n-2, 0, -1):
            a = arr[i]
            l = arr[i-1]
            r = arr[i+1]

            if mode == "high":
                if ((a > l and a >= r) or (a >= l and a > r)) and a > c:
                    return a
            elif mode == "low":
                if ((a < l and a <= r) or (a <= l and a < r)) and a < c:
                    return a

        return max(arr) if mode == "high" else min(arr)

class PositionLeg:
    __slots__ = ("entry_time", "direction", "_entry_price", "stop_price", "target_price", "position_size", "shares")
    
    def __init__(self, timestamp, direction, entry_price, stop_price, target_price, position_size, cash):
        self.entry_time = timestamp
        self.direction = direction
        self._entry_price = entry_price
        self.stop_price = stop_price
        self.target_price = target_price
        self.position_size = position_size
        self.shares = (cash * position_size) // entry_price

        if direction not in (1, -1):
            raise ValueError(f"Invalid direction: {direction}")
        if self.direction == 1:
            if not (0 < self.stop_price < self.entry_price < self.target_price):
                raise ValueError(f"Invalid long leg: stop={self.stop_price}, entry={self.entry_price}, target={self.target_price}")
        elif self.direction == -1:
            if not (0 < self.target_price < self.entry_price < self.stop_price):
                raise ValueError(f"Invalid short leg: stop={self.stop_price}, entry={self.entry_price}, target={self.target_price}")
     
    def check_exit(self, ts, low, high):
        if self.direction == 1:
            if self.stop_price >= self.target_price:
                raise ValueError("Invalid long: stop >= target")
            if low <= self.stop_price or high >= self.target_price:
                return EXIT
            if (ts.hour, ts.minute) >= (15, 58):
                return EXIT
        elif self.direction == -1:
            if self.stop_price <= self.target_price:
                raise ValueError("Invalid short: stop <= target")
            if high >= self.stop_price or low <= self.target_price:
                return EXIT
            if (ts.hour, ts.minute) >= (15, 58):
                return EXIT
        return HOLD
    
    @property
    def entry_price(self):
        return self._entry_price

    @entry_price.setter
    def entry_price(self, value):
        if value <= 0:
            raise ValueError("entry_price must be positive")
        self._entry_price = float(value)
            
class PositionManager:
    def __init__(self, pyramid):
        self.pyramid = pyramid
        self.legs = [] # list of PositionLeg

    def add_leg(self, leg: PositionLeg):
        if not self.pyramid and self.legs:
            return False
        
        if 0.0 < self.total_size() + leg.position_size <= 1.0:
            self.legs.append(leg)
            return True

    def remove_leg(self, leg):
        self.legs.remove(leg)

    def direction(self):
        return self.legs[0].direction if self.legs else 0

    def total_size(self):
        return sum(l.position_size for l in self.legs)  

    def flatten(self):
        self.legs = []
    
    def in_trade(self):
        return bool(self.legs)

class RiskManager:
    def __init__(self, pnl_target=0.02, pnl_loss=-0.01, trade_max=3):
        self.pnl_target = pnl_target
        self.pnl_loss = pnl_loss
        self.trade_max = trade_max
        
        self._start_cash = 0
        self.trades = 0
        self.pnl = 0
        self._day_pause = False

    def update_trade(self, pnl):
        self.pnl += pnl
        self.trades += 1

        if self.trades >= self.trade_max:
            self._day_pause = True

        if self.pnl / self.start_cash >= self.pnl_target:
            self._day_pause = True

        if self.pnl / self.start_cash <= self.pnl_loss:
            self._day_pause = True

    def reset(self):
        self.trades = 0
        self.pnl = 0
        self._day_pause = False
    
    def get_curr_cash(self):
        return self.start_cash + self.pnl

    @property
    def start_cash(self):
        return self._start_cash

    @start_cash.setter
    def start_cash(self, cash):
        if cash < 0:
            raise ValueError("start_cash must be positive")
        self._start_cash = round(cash, 2)