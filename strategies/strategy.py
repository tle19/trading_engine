import numpy as np

LONG = 1
SHORT = -1
EXIT = 0
HOLD = None

class Strategy:
    def __init__(self, symbol, position_size=1.0, 
                 stop_loss=0.01, take_profit=0.02, trailing_ratio=0.5):
        self.symbol = symbol
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trailing_ratio = trailing_ratio
        self.position_size = position_size

        self.position = None
        self.trailing = False
        self.trailing_stop_loss = None
        self.entry_price = None
        self.stop_price = None
        self.profit_price = None

        self.open = None
        self.close = None
        self.high = None
        self.low = None
        self.volume = None
        self.ts = None

        self.prices = []
        self.volumes = []

        self.risk = 0
        self.pause = False
        self.pause_timer = 0
        
     
    def generate_signal(self, row=None):
        self.update(row)
        return HOLD
    
    def update(self, row=None): 
        if row is not None:
            self.open = row["open"]
            self.close = row["close"]
            self.high = row["high"]
            self.low = row["low"]
            self.volume = row["volume"]
            self.ts = row["timestamp"]

        #self.prices.append((self.close + self.high + self.low) / 3)
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
        self.position = None
        self.trailing = False
        self.trailing_stop_loss = None
        self.entry_price = None
        self.stop_price = None
        self.profit_price = None

    def set_trailing_stop(self, trailing_ratio):
        self.trailing = True
        self.trailing_stop_loss = self.stop_loss
        adjustment = trailing_ratio * abs(self.stop_price - self.close)

        if self.position == "long" and self.close > self.entry_price:
            new_stop = self.stop_price + adjustment
            self.stop_price = new_stop
            self.trailing_stop_loss = 1 - (self.stop_price / self.entry_price)

        elif self.position == "short" and self.close < self.entry_price:
            new_stop = self.stop_price - adjustment
            self.stop_price = new_stop
            self.trailing_stop_loss = (self.stop_price / self.entry_price) - 1

    def set_trailing_stop_safe(self, stability_window=20, min_dist_ratio=0.00075):
        avg_price = self.compute_ma(stability_window)
        distance = abs(self.stop_price - self.close)
        min_distance = avg_price * min_dist_ratio

        if distance < min_distance:
            return

        max_ratio = 1 - (min_distance / distance)
        trailing_ratio = min(self.trailing_ratio, max_ratio)
        
        self.set_trailing_stop(trailing_ratio)

    def reset_data(self):
        if (self.ts.hour, self.ts.minute) == (9, 30):
            self.prices = []
            self.volumes = []

    def trade_window(self, start, end):
        return start <= (self.ts.hour, self.ts.minute) <= end
        
    def check_pnl(self, pnl):
        if pnl < 0:
            self.risk += 1
        elif pnl > 0:
            self.risk -= 1
        self.risk = max(0, min(7, self.risk))

    def check_risk(self):
        if self.risk >= 5:
            self.pause = True

    def risk_timer(self):
        if self.pause_timer < 5:
            self.pause_timer += 1
        else:
            self.risk = 0
            self.pause = False
            self.pause_timer = 0

    def compute_ma(self, window):
        return np.mean(self.prices[-window:])

    def is_trailing(self):
        return self.trailing
    
    def get_stop_loss(self):
        return self.trailing_stop_loss if self.is_trailing() else self.stop_loss
    
    def get_take_profit(self):
        return self.take_profit
    
    def get_position(self):
        return self.position
    
    def get_position_size(self):
        return self.position_size
    
    def get_entry_price(self):
        return self.entry_price
    
    def update_entry_price(self, entry_price):
        self.entry_price = entry_price
    