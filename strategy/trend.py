from datetime import time
import pandas as pd

class IntradayTrend:
    def __init__(self, entry_time=30, entry_cond=0.003, 
                 stop_loss=0.01, take_profit=0.004):
        self.curr_time = 0
        self.entry_time = entry_time
        self.entry_cond = entry_cond
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.start_price = 0
        self.entry_price = 0
        self.curr_ret = 0
        self.position = None

    def update(self, row):
        self.curr_time += 1
        if row['timestamp'].time().strftime("%H:%M") < "9:00":
            self.curr_time = 0

        if self.curr_time == 1:
            self.start_price = row['open']

        # --- Entry signal ---
        if self.curr_time == self.entry_time and self.position is None:
            self.entry_price = row['close']
            ret = self.entry_price / self.start_price - 1

            if ret > self.entry_cond:
                self.position = "long"
                return 1
            elif ret < -self.entry_cond:
                self.position = "short"
                return -1
            else:
                return None

        # --- While holding ---
        if self.position == "long":
            self.curr_ret = row['close'] / self.entry_price - 1
        elif self.position == "short":
            self.curr_ret = self.entry_price / row['close'] - 1

        # --- Exit ---
        if self.position is not None:
            if self.curr_ret >= self.take_profit:  # hit TP
                self.position = None
                return 0
            elif self.curr_ret <= -self.stop_loss:  # hit SL
                self.position = None
                return 0

        return None
