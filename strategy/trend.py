from datetime import time
import pandas as pd
import numpy as np

class IntradayTrend:
    def __init__(self, symbol, entry_time=30, entry_cond=0.0035, stop_loss=0.01, take_profit=0.004):
        self.curr_time = 0
        self.entry_time = entry_time
        self.entry_cond = entry_cond
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.start_price = 0
        self.entry_price = 0
        self.position = None

        self.window = entry_time
        self.prices = []

        self.position_size = 0
        self.holding_time = 0
        self.sl_price = 0
        self.effective_stop_loss = self.stop_loss

    def update(self, row, k=500, trailing_ratio=0.015):
        self.curr_time += 1

        open = row["open"]
        close = row["close"]
        high = row["high"]
        low = row["low"]

        ts = row["timestamp"]
        if (ts.hour, ts.minute) < (9, 30):
            self.curr_time = 0

        if self.curr_time == 1:
            self.start_price = open

        self.prices.append(close)

        prices_window = self.prices[-self.window:]
        avg_price = np.mean(prices_window)
        vol_factor = np.std(prices_window) / avg_price
        self.position_size = np.exp(-vol_factor * k)
        self.position_size = min(max(self.position_size, 0.25), 1.0)
        # --- Entry signal ---
        if self.curr_time == self.entry_time and self.position is None:
            ret = self.entry_price / self.start_price - 1

            if ret > self.entry_cond and avg_price > self.start_price:
                self.position = "long"
                self.entry_price = close
                self.effective_stop_loss = self.stop_loss
                self.sl_price = self.entry_price * (1 - self.stop_loss)
                return 1, self.stop_loss, self.take_profit, self.position_size
            elif ret < -self.entry_cond and avg_price < self.start_price:
                self.position = "short"
                self.entry_price = close
                self.effective_stop_loss = self.stop_loss
                self.sl_price = self.entry_price * (1 + self.stop_loss)
                return -1, self.stop_loss, self.take_profit, self.position_size
            
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
            if self.holding_time >= 10:

                if self.position == "long" and close > avg_price:
                    self.sl_price = self.sl_price + trailing_ratio * (avg_price - self.sl_price)
                    self.effective_stop_loss = 1 - (self.sl_price / self.entry_price)
                elif self.position == "short" and close < avg_price:
                    self.sl_price = self.sl_price + trailing_ratio * (avg_price - self.sl_price)
                    self.effective_stop_loss = (self.sl_price / self.entry_price) - 1

                return None, self.effective_stop_loss, self.take_profit, self.position_size
        
        return None, None, None, None
