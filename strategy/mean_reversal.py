from datetime import time

import numpy as np


class MeanReversionIndicator:
    def __init__(self, entry_spread=0.0005, stop_loss=0.00065, take_profit=0.0005,
                 window=20, k=25):
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.entry_spread_pct = entry_spread
        self.entry_spread = 422 * entry_spread # force set
        self.position = None
        self.entry_price = 0
        self.curr_time = 0
        self.candle_streak = 0
        self.k = k

        self.window = window
        self.prices = []

    def update(self, row):
        self.curr_time += 1

        open = row["open"]
        close = row["close"]
        high = row["high"]
        low = row["low"]

        ts = row["timestamp"]
        if (ts.hour, ts.minute) == (9, 30):
            self.entry_spread = open * self.entry_spread_pct
        if not ((10, 30) <= (ts.hour, ts.minute) <= (14, 30)):
            self.curr_time = 0

        self.prices.append(close)

        # --- Entry signal ---
        if self.position is None and self.curr_time != 0:
            # spread = abs(close - open)
            spread = high - low

            if spread < self.entry_spread:
                return None, self.stop_loss, self.take_profit
            
            # if spread < self.entry_spread and spread > self.entry_spread * 2:
            #     return None, self.stop_loss, self.take_profit
            # optimize candle entry (check if better!!!)
            # optimize on  >triple downs/ups eating profits
            # probability after 2 same candles
            # rnn classification on two candles (volkume, spread, body)
            # what iondicates push through stop loss on following candle
            # consider VOLUME

            # --- Candle streak update ---

            if close > open:
                self.candle_streak = 1 if self.candle_streak < 0 else self.candle_streak + 1
            elif close < open:
                self.candle_streak = -1 if self.candle_streak > 0 else self.candle_streak - 1
            else:
                self.candle_streak = 0

            if len(self.prices) >= self.window:  
                ma = np.mean(self.prices[-self.window:])
                distance_factor = (ma * self.take_profit) / self.k
                if self.candle_streak >= 2 and close > ma * (1 + distance_factor): # signal inverted for better performance
                    self.position = "short"
                    self.entry_price = close
                    return -1, self.stop_loss, self.take_profit
                elif self.candle_streak <= -2 and close < ma * (1 - distance_factor): # signal inverted for better performance
                    self.position = "long"
                    self.entry_price = close
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
