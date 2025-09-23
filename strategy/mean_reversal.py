from datetime import time

import numpy as np


class MeanReversionIndicator:
    def __init__(self, entry_spread=0.00035, stop_loss=0.002125, take_profit=0.002125,
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

    def update(self, row, k = 575):
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
            spread = high - low
            if spread < avg_price * self.entry_spread:
                return None, self.stop_loss, self.take_profit, self.position_size

            # remove extreme price movement
            if rvol > 2.35 or rvol < 0.325:
                return None, self.stop_loss, self.take_profit, self.position_size
            
            # --- Candle streak update ---
            if close > open:
                self.candle_streak = 1 if self.candle_streak < 0 else self.candle_streak + 1
            elif close < open:
                self.candle_streak = -1 if self.candle_streak > 0 else self.candle_streak - 1
            else:
                self.candle_streak = 0

            if len(self.prices) >= self.window:
                vol_factor = std_price / avg_price
                self.position_size = np.exp(-vol_factor * k)
                self.position_size = min(max(self.position_size, 0.25), 1.0)
                
                streak_threshold = 2 if std_price / avg_price < 0.00145 else 3
                if self.candle_streak >= streak_threshold and close > avg_price + (1.025 * std_price): # signal inverted for better performance
                    self.position = "short"
                    self.entry_price = close
                    return -1, self.stop_loss, self.take_profit, self.position_size
                elif self.candle_streak <= -streak_threshold and close < avg_price - (1.025 * std_price): # signal inverted for better performance
                    self.position = "long"
                    self.entry_price = close
                    return 1, self.stop_loss, self.take_profit, self.position_size

            return None, self.stop_loss, self.take_profit, self.position_size

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
                return 0, self.stop_loss, self.take_profit, self.position_size

        return None, self.stop_loss, self.take_profit, self.position_size
