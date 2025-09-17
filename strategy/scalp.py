from datetime import time

import pandas as pd


class Scalp:
    def __init__(self, entry_spread=0.0003, stop_loss=0.0001, take_profit=0.00004):
        self.entry_spread = entry_spread
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.position = None
        self.entry_price = 0
        self.curr_ret = 0
        self.start_time = None
        self.bid = 0
        self.ask = 0
        self.last = 0

    def update(self, row):

        if row.get("bid") is not None:
            self.bid = row["bid"]
        if row.get("ask") is not None:
            self.ask = row["ask"]
        if row.get("last") is not None:
            self.last = row["last"]

        spread = self.ask - self.bid

        # --- Entry signal ---
        if self.position is None:
            if spread >= self.entry_spread:
                self.position = "long"
                self.entry_price = self.bid
                return 1, self.stop_loss, self.take_profit
            elif self.last is not None and (self.bid - self.last) >= self.entry_spread:
                self.position = "short"
                self.entry_price = self.ask
                return -1, self.stop_loss, self.take_profit
            else:
                return None

        # --- While holding ---
        if self.position == "long" and self.last is not None:
            self.curr_ret = (self.last - self.entry_price) / self.entry_price
            if self.curr_ret >= self.take_profit or self.curr_ret <= -self.stop_loss:
                self.position = None
                return 0  # exit

        elif self.position == "short" and self.last is not None:
            self.curr_ret = (self.entry_price - self.last) / self.entry_price
            if self.curr_ret >= self.take_profit or self.curr_ret <= -self.stop_loss:
                self.position = None
                return 0  # exit

        return None
