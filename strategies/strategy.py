import numpy as np

LONG = 1
SHORT = -1
EXIT = 0
HOLD = None

class Strategy:
    def __init__(self, symbol, position_size=1.0,
                 stop_loss=0.01, take_profit=0.02, trailing_ratio=0.2):
        self.symbol = symbol
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trailing_ratio = trailing_ratio
        self.default_position_size = position_size
        self.position_size = position_size

        self.position = None
        self.trailing_stop = False
        self.trailing_profit = False
        self.trailing_stop_loss = None
        self.trailing_take_profit = None
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

        self.prices = []
        self.volumes = [] 


        self.current_date = None

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

        # self.prices.append((self.close + self.high + self.low) / 3)
        self.prices.append(self.close)
        self.volumes.append(self.volume)

    def check_status(self, force_close=True):
        if self.position == "long":
            if self.high >= self.profit_price or self.low <= self.stop_price:
                return self.sell()
            if force_close and (self.ts.hour, self.ts.minute) >= (15, 58):
                return self.sell()
        elif self.position == "short":
            if self.low <= self.profit_price or self.high >= self.stop_price:
                return self.buy()
            if force_close and (self.ts.hour, self.ts.minute) >= (15, 58):
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
        self.trailing_stop_loss = None
        self.trailing_take_profit = None
        self.entry_price = None
        self.stop_price = None
        self.profit_price = None
        self.sl_change = False
        self.tp_change = False

    def set_trailing_stop(self, trailing_ratio):
        self.trailing_stop = True
        self.sl_change = False
        self.trailing_stop_loss = self.stop_loss
        adjustment = trailing_ratio * abs(self.stop_price - self.close)

        if self.position == "long" and self.close > self.entry_price:
            new_stop = self.stop_price + adjustment
            self.stop_price = new_stop
            self.trailing_stop_loss = 1 - (self.stop_price / self.entry_price)
            self.sl_change = True

        elif self.position == "short" and self.close < self.entry_price:
            new_stop = self.stop_price - adjustment
            self.stop_price = new_stop
            self.trailing_stop_loss = (self.stop_price / self.entry_price) - 1
            self.sl_change = True

    def set_trailing_stop_safe(self):
        if not self.in_safe_range():
            return None

        min_distance = self.compute_min_distance()
        stop_distance = abs(self.stop_price - self.close)

        max_ratio = 1 - (min_distance / stop_distance)
        trailing_ratio = min(self.trailing_ratio, max_ratio)
        
        self.set_trailing_stop(trailing_ratio)

    def set_trailing_profit(self, trailing_ratio):
        self.trailing_profit = True
        self.tp_change = False
        self.trailing_take_profit = self.take_profit
        adjustment = trailing_ratio * abs(self.profit_price - self.close)
        
        if self.position == "long" and self.close > self.entry_price:
            new_profit = self.profit_price + adjustment
            self.profit_price = new_profit
            self.trailing_take_profit = 1 - (self.profit_price / self.entry_price)
            self.tp_change = True

        elif self.position == "short" and self.close < self.entry_price:
            new_profit = self.profit_price - adjustment
            self.profit_price = new_profit
            self.trailing_take_profit = (self.profit_price / self.entry_price) - 1
            self.tp_change = True
    
    def set_trailing_profit_safe(self):
        if not self.in_safe_range():
            return None

        min_distance = self.compute_min_distance()
        profit_distance = abs(self.profit_price - self.close)

        max_ratio = 1 - (min_distance / profit_distance)
        trailing_ratio = min(self.trailing_ratio, max_ratio)

        self.set_trailing_profit(trailing_ratio)
    
    def compute_min_distance(self, stability_window=10, min_dist_ratio=0.00075):
        if len(self.prices) < stability_window:
            return None
        avg_price = self.compute_ma(self.prices, stability_window)
        min_distance = avg_price * min_dist_ratio
        return min_distance

    def in_safe_range(self):
        min_distance = self.compute_min_distance()
        stop_distance = abs(self.stop_price - self.close)
        profit_distance = abs(self.profit_price - self.close)

        if min_distance is None:
            return False
        elif stop_distance > min_distance and profit_distance > min_distance:
            return True
        
    def reset_data(self):
        if (self.ts.hour, self.ts.minute) == (9, 30):
            self.prices = []
            self.volumes = []

    def trade_window(self, start, end):
        return start <= (self.ts.hour, self.ts.minute) <= end

    def compute_ma(self, items, window):
        return np.mean(items[-window:])
    
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
    
    def update_entry_price(self, entry_price):
        self.entry_price = entry_price

    def get_risk_manager(self):
        return self.risk_manager


class RiskManager:
    def __init__(self, risk_threshold=5, pause_duration=5, pnl_target=200, pnl_loss=200):
        self.risk_threshold = risk_threshold
        self.pause_duration = pause_duration
        self.pnl_target = pnl_target
        self.pnl_loss = pnl_loss
        self.pnl = 0
        self.day_pause = False
        self.risk = 0
        self.pause = False
        self._pause_counter = 0

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

    def daily_risk_target(self):     #percentage based daily stops !!!!!
        if self.pnl >= self.pnl_target:
            self.day_pause = True

    def daily_risk_stop(self):       #percentage based daily stops !!!!!
        if self.pnl <= -self.pnl_loss:
            self.day_pause = True
    
    def dynamic_position_sizing(self, position_size):
        if self.pnl >= self.pnl_target:
            ratio = self.pnl / self.pnl_target
            scale = 0.5 / ratio
            return position_size * scale
        return position_size

    def reset_risk(self):
        self.pnl = 0
        self.day_pause = False
        self.risk = 0
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