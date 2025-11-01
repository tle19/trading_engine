import numpy as np

from utils import *

LONG = 1
SHORT = -1
EXIT = 0
HOLD = None

class Strategy:
    def __init__(self, symbol, stop_loss=0.01, take_profit=0.02, trailing_ratio=0.15,  
                 position_size=1.0, force_close=False):
        self.symbol = symbol
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trailing_ratio = trailing_ratio
        self.default_position_size = position_size
        self.position_size = position_size
        self.force_close = force_close

        self.position = None
        self.trailing_stop = False
        self.trailing_profit = False
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
            self.open = row.open
            self.close = row.close
            self.high = row.high
            self.low = row.low
            self.volume = row.volume
            self.ts = row.timestamp

        self.prices.append(self.close)
        # self.prices.append((self.close + self.high + self.low) / 3)
        self.highs.append(self.high)
        self.lows.append(self.low)
        self.volumes.append(self.volume)

    def check_status(self):
        if self.position == "long":
            if self.low <= self.stop_price or self.high >= self.profit_price:
                return self.sell()
            elif self.force_close and not self.trade_window((9, 30), (15, 57)):
                return self.sell()
        elif self.position == "short":
            if self.high >= self.stop_price or self.low <= self.profit_price:
                return self.buy()
            elif self.force_close and not self.trade_window((9, 30), (15, 57)):
                return self.buy()
            
    def buy(self):
        if self.position is None:
            self.position = "long"
            self.entry_price = round(self.close, 2)
            self.stop_price = round(self.entry_price * (1 - self.stop_loss), 2)
            self.profit_price = round(self.entry_price * (1 + self.take_profit), 2)
            return LONG
        elif self.position == "short":
            return EXIT
    
    def sell(self):
        if self.position is None:
            self.position = "short"
            self.entry_price = round(self.close, 2)
            self.stop_price = round(self.entry_price * (1 + self.stop_loss), 2)
            self.profit_price = round(self.entry_price * (1 - self.take_profit), 2)
            return SHORT
        elif self.position == "long":
            return EXIT

    def flatten(self):
        self.position_size = self.default_position_size
        self.position = None
        self.trailing_stop = False
        self.trailing_profit = False
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

    def set_trailing_profit(self):
        self.trailing_profit = False
        if not self.in_safe_range():
            return None
        
        trailing_ratio = self.get_trailing_ratio(self.profit_price)
        adjustment = trailing_ratio * abs(self.profit_price - self.close)
        
        if self.position == "long" and self.close > self.entry_price:
            self.profit_price = round(self.profit_price + adjustment, 2)
            self.trailing_profit = True

        elif self.position == "short" and self.close < self.entry_price:
            self.profit_price = round(self.profit_price - adjustment, 2)
            self.trailing_profit = True

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

    def compute_ma(self, items, window):
        return np.mean(items[-window:])
    
    def compute_rsi(self, arr, period):
        if len(arr) < period + 1:
            return None

        deltas = np.diff(arr[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = gains.mean()
        avg_loss = losses.mean()

        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
        
    def donchian_channel(self, window):
        upper_band = max(self.highs[-window:])
        lower_band = min(self.lows[-window:])
        return upper_band, lower_band
    
    def trade_window(self, start, end):
        return start <= (self.ts.hour, self.ts.minute) <= end
           
    def reset_data(self):
        if self.trade_window((9, 30), (9, 30)):
            self.prices = []
            self.highs = []
            self.lows = []
            self.volumes = []
            self.risk_manager.reset_risk()

    def is_force_close(self):
        return self.force_close

    def is_trailing_stop(self):
        return self.trailing_stop
  
    def is_trailing_profit(self):
        return self.trailing_profit
    
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
