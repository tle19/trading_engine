from datetime import time

import numpy as np


class VolatilityIndicator:
    def __init__(self, entry_spread=0.0005, stop_loss=0.002125, take_profit=0.002125,
                 window=20):
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.entry_spread = entry_spread
        self.position = None
        self.entry_price = 0
        self.curr_time = 0
        self.candle_streak = 0

        self.window = window
        self.prices = []
        self.volume = []

        self.position_size = 0
        self.holding_time = 0
        self.sl_price = 0
        self.effective_stop_loss = self.stop_loss

    def update(self, row, trailing_ratio=0.5075, k=500):
        self.curr_time += 1
        
        open = row["open"]
        close = row["close"]
        high = row["high"]
        low = row["low"]
        volume = row["volume"]

        ts = row["timestamp"]
        if not ((10, 15) <= (ts.hour, ts.minute) <= (15, 00)):
            self.curr_time = 0

        self.prices.append(close)
        self.volume.append(volume)

        prices_window = self.prices[-self.window:]
        avg_price = np.mean(prices_window)
        std_price = np.std(prices_window)

        volume_window = self.volume[-self.window:]
        avg_vol = np.mean(volume_window)
        rvol = volume / avg_vol

        # --- Entry signal ---
        if self.position is None and self.curr_time != 0:
            
            # remove extreme price movement
            spread = high - low
            if spread < avg_price * self.entry_spread:
                return None, None, None, None
            if rvol > 2.35 or rvol < 0.325:
                return None, None, None, None
                
            volatility_gate = std_price / avg_price < 0.0014
            low_vol_gate  = std_price / avg_price > 0.001

            if len(self.prices) >= self.window:
                vol_factor = std_price / avg_price
                self.position_size = np.exp(-vol_factor * k)
                self.position_size = min(max(self.position_size, 0.25), 1.0)

                if volatility_gate:
                    self.position = "short"
                    self.entry_price = close
                    self.effective_stop_loss = self.stop_loss
                    self.sl_price = self.entry_price * (1 + self.stop_loss)
                    return -1, self.stop_loss, self.take_profit, self.position_size
                # elif self.prices[-1] < self.prices[-2]:
                #     self.position = "long"
                #     self.entry_price = close
                #     self.effective_stop_loss = self.stop_loss
                #     self.sl_price = self.entry_price * (1 - self.stop_loss)
                #     return 1, self.stop_loss, self.take_profit, self.position_size

            return None, None, None, None
        
        # --- Holding ---
        if self.position is not None: 
            # --- Exit ---
            if self.position == "long":
                tp_price = self.entry_price * (1 + self.take_profit)
                exit_condition = high >= tp_price or low <= self.sl_price
            elif self.position == "short":
                tp_price = self.entry_price * (1 - self.take_profit)
                exit_condition = low <= tp_price or high >= self.sl_price

            if exit_condition:
                self.position = None
                self.holding_time = 0
                return 0, self.effective_stop_loss, self.take_profit, self.position_size
        
            # --- Trailing Stop ---
            self.holding_time += 1
            if self.holding_time >= 4:
                if self.position == "long" and close > avg_price:
                    self.sl_price = self.sl_price + trailing_ratio * (avg_price - self.sl_price)
                    self.effective_stop_loss = 1 - (self.sl_price / self.entry_price)
                elif self.position == "short" and close < avg_price:
                    self.sl_price = self.sl_price - trailing_ratio * (avg_price - self.sl_price)
                    self.effective_stop_loss = (self.sl_price / self.entry_price) - 1
                
                return None, self.effective_stop_loss, self.take_profit, self.position_size
            # consider adaptive stop loss and take profit
        return None, None, None, None

