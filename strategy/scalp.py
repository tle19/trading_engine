from datetime import time

import pandas as pd


class Scalp:
    def __init__(self, entry_spread=0.0005, stop_loss=0.00065, take_profit=0.0005):
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.entry_spread_pct = entry_spread
        self.entry_spread = 0
        self.position = None
        self.entry_price = 0
        self.curr_time = 0
        self.candle_streak = 0

    def update(self, row):
        self.curr_time += 1

        open = row["open"]
        close = row["close"]
        high = row["high"]
        low = row["low"]

        ts = pd.to_datetime(row.name)
        if (ts.hour, ts.minute) == (9, 30):
            self.entry_spread = open * self.entry_spread_pct

        if not ((10, 30) <= (ts.hour, ts.minute) <= (14, 30)):
            self.curr_time = 0

        # --- Entry signal ---
        if self.position is None and self.curr_time != 0:
            spread = high - low

            if spread < self.entry_spread:
                return None, self.stop_loss, self.take_profit
            
            # if spread < self.entry_spread and spread > self.entry_spread * 2:
            #     return None, self.stop_loss, self.take_profit
            
            if close > open:
                self.candle_streak = 1 if self.candle_streak < 0 else self.candle_streak + 1
            elif close < open:
                self.candle_streak = -1 if self.candle_streak > 0 else self.candle_streak - 1
            else:
                self.candle_streak = 0

            if close > open and self.candle_streak >= 2: # signal inverted for better performance
                self.position = "short"
                self.entry_price = close
                self.candle_streak = 0
                return -1, self.stop_loss, self.take_profit
            elif close < open and self.candle_streak <= -2: # signal inverted for better performance
                self.position = "long"
                self.entry_price = close
                self.candle_streak = 0
                return 1, self.stop_loss, self.take_profit

            return None, self.stop_loss, self.take_profit

        # --- Exit ---
        if self.position is not None:
            if self.position == "long":
                tp_price = self.entry_price * (1 + self.take_profit)
                sl_price = self.entry_price * (1 - self.stop_loss)
                exit_condition = high >= tp_price or low <= sl_price
            elif self.position == "short":
                tp_price = self.entry_price * (1 - self.take_profit)
                sl_price = self.entry_price * (1 + self.stop_loss)
                exit_condition = low <= tp_price or high >= sl_price

            if exit_condition:
                self.position = None
                return 0, self.stop_loss, self.take_profit

        return None, self.stop_loss, self.take_profit
