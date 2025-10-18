from datetime import datetime, timedelta
import numpy as np

from utils import *

LONG = 1
SHORT = -1
EXIT = 0
HOLD = None

class Strategy:
    def __init__(self, symbol, position_size=1.0,
                 stop_loss=0.01, take_profit=0.02, trailing_ratio=0.15, force_close=False):
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
        self.trailing_stop_loss = stop_loss
        self.trailing_take_profit = take_profit
        self.entry_price = None
        self.stop_price = None
        self.profit_price = None
        self.sl_change = False
        self.tp_change = False

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
        self.update(row)
        self.reset_data() # optional
        status = self.check_status()
        if status is not None:
            return status
        return self.enter_trade()
    
    def enter_trade(self):
        raise NotImplementedError
    
    def update(self, row=None): 
        if row is not None:
            self.open = row["open"]
            self.close = row["close"]
            self.high = row["high"]
            self.low = row["low"]
            self.volume = row["volume"]
            self.ts = row["timestamp"]

        self.prices.append(self.close)
        # self.prices.append((self.close + self.high + self.low) / 3)
        self.highs.append(self.high)
        self.lows.append(self.low)
        # self.volumes.append(self.volume)

    def check_status(self, force_close=False):
        if self.position == "long":
            if self.high >= self.profit_price or self.low <= self.stop_price:
                return self.sell()
            if force_close and not self.trade_window((9, 30), (15, 57)):
                return self.sell()
        elif self.position == "short":
            if self.low <= self.profit_price or self.high >= self.stop_price:
                return self.buy()
            if force_close and not self.trade_window((9, 30), (15, 57)):
                return self.buy()
            
    def buy(self):
        if self.position is None:
            self.position = "long"
            self.entry_price = self.close
            self.stop_price = self.entry_price * (1 - self.stop_loss)
            self.profit_price = self.entry_price * (1 + self.take_profit)
            return LONG
        elif self.position == "short":
            self.flatten()
            return EXIT
    
    def sell(self):
        if self.position is None:
            self.position = "short"
            self.entry_price = self.close
            self.stop_price = self.entry_price * (1 + self.stop_loss)
            self.profit_price = self.entry_price * (1 - self.take_profit)
            return SHORT
        elif self.position == "long":
            self.flatten()
            return EXIT

    def flatten(self):
        self.position_size = self.default_position_size
        self.position = None
        self.trailing_stop = False
        self.trailing_profit = False
        self.trailing_stop_loss = self.stop_loss
        self.trailing_take_profit = self.take_profit
        self.entry_price = None
        self.stop_price = None
        self.profit_price = None
        self.sl_change = False
        self.tp_change = False

    def set_trailing_stop(self, trailing_ratio):
        self.trailing_stop = True
        adjustment = trailing_ratio * abs(self.stop_price - self.close)

        if self.position == "long" and self.close > self.entry_price:
            self.stop_price += adjustment
            self.trailing_stop_loss = 1 - (self.stop_price / self.entry_price)
            self.sl_change = True

        elif self.position == "short" and self.close < self.entry_price:
            self.stop_price -= adjustment
            self.trailing_stop_loss = (self.stop_price / self.entry_price) - 1
            self.sl_change = True

    def set_trailing_stop_safe(self):
        if not self.in_safe_range():
            self.sl_change = False
            return None

        min_distance = self.compute_min_distance()
        stop_distance = abs(self.stop_price - self.close)

        max_ratio = 1 - (min_distance / stop_distance)
        trailing_ratio = min(self.trailing_ratio, max_ratio)
        
        self.set_trailing_stop(trailing_ratio)
        # print("EN", self.entry_price, "SL", self.stop_price, "TP", self.profit_price) #sanity check

    def set_trailing_profit(self, trailing_ratio):
        self.trailing_profit = True
        adjustment = trailing_ratio * abs(self.profit_price - self.close)
        
        if self.position == "long" and self.close > self.entry_price:
            self.profit_price += adjustment
            self.trailing_take_profit = 1 - (self.profit_price / self.entry_price)
            self.tp_change = True

        elif self.position == "short" and self.close < self.entry_price:
            self.profit_price -= adjustment
            self.trailing_take_profit = (self.profit_price / self.entry_price) - 1
            self.tp_change = True
    
    def set_trailing_profit_safe(self):
        if not self.in_safe_range():
            self.tp_change = False
            return None

        min_distance = self.compute_min_distance()
        profit_distance = abs(self.profit_price - self.close)

        max_ratio = 1 - (min_distance / profit_distance)
        trailing_ratio = min(self.trailing_ratio, max_ratio)

        self.set_trailing_profit(trailing_ratio)
    
    def compute_min_distance(self, min_dist_ratio=0.5):
        spread = self.compute_spread()
        min_dist = spread * min_dist_ratio
        return min_dist

    def in_safe_range(self):
        min_distance = self.compute_min_distance()
        stop_distance = abs(self.stop_price - self.close)
        profit_distance = abs(self.profit_price - self.close)

        if min_distance is None:
            return False
        elif stop_distance > min_distance and profit_distance > min_distance:
            return True
 
    def trade_window(self, start, end):
        return start <= (self.ts.hour, self.ts.minute) <= end
           
    def reset_data(self):
        if self.trade_window((9, 30), (9, 30)):
            self.prices = []
            self.volumes = []
            self.risk_manager.reset_risk()

    def compute_ma(self, items, window):
        return np.mean(items[-window:])
    
    def compute_spread(self, stability_window=10): #consider more reactive =5
        if len(self.prices) < stability_window:
            return None

        recent_highs = np.array(self.highs[-stability_window:])
        recent_lows = np.array(self.lows[-stability_window:])
        spread = np.mean(recent_highs - recent_lows)
        return spread
    
    def is_force_close(self):
        return self.force_close
    
    def stop_loss_changed(self):
        return self.sl_change
    
    def take_profit_changed(self):
        return self.tp_change

    def is_trailing_stop(self):
        return self.trailing_stop
  
    def is_trailing_profit(self):
        return self.trailing_profit
      
    def get_stop_loss(self):
        return self.trailing_stop_loss if self.is_trailing_stop() else self.stop_loss
    
    def get_take_profit(self):
        return self.trailing_take_profit if self.is_trailing_profit() else self.take_profit
    
    def get_position(self):
        return self.position
    
    def get_position_size(self):
        return self.position_size
    
    def get_entry_price(self):
        return self.entry_price

    def get_risk_manager(self):
        return self.risk_manager
       
    def update_entry_price(self, entry_price):
        self.entry_price = entry_price

    def update_prices(self, entry, stop, profit):
        self.entry_price = float(entry)
        self.stop_price = float(stop)
        self.profit_price = float(profit)

class RiskManager:
    def __init__(self, risk_threshold=5, pause_duration=5, pnl_target=0.02, pnl_loss=-0.001):
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

    def get_start_cash(self, cash):
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
    
    # self.risk_manager.intraday_risk()
    # self.risk_manager.daily_risk_stop()
    # self.position_size = self.risk_manager.dynamic_position_sizing(self.default_position_size)
    # if self.risk_manager.is_day_pause():
    #     return None
    # if self.risk_manager.is_trade_pause():
    #     self.risk_manager.tick()
    #     return None