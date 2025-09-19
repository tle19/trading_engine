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
        self.ret_high = 0

    def update(self, row):
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

        # --- Entry signal ---
        if self.curr_time == self.entry_time and self.position is None:
            self.entry_price = close
            ret = self.entry_price / self.start_price - 1

            if ret > self.entry_cond:
                self.position = "long"
                return 1, self.stop_loss, self.take_profit
            elif ret < -self.entry_cond:
                self.position = "short"
                return -1, self.stop_loss, self.take_profit
            
            return None, self.stop_loss, self.take_profit

        # --- Exit ---
        if self.position == "long":
            take_profit_price = self.entry_price * (1 + self.take_profit)
            stop_loss_price = self.entry_price * (1 - self.stop_loss)
            if high >= take_profit_price or low <= stop_loss_price:
                self.position = None
                return 0, self.stop_loss, self.take_profit
        elif self.position == "short":
            take_profit_price = self.entry_price * (1 - self.take_profit)
            stop_loss_price = self.entry_price * (1 + self.stop_loss)
            if low <= take_profit_price or high >= stop_loss_price:
                self.position = None
                return 0, self.stop_loss, self.take_profit

        return None, self.stop_loss, self.take_profit
