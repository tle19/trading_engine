from get_data import DataHandler

import numpy as np
import pandas as pd

class SwingMAIndicator:
    def __init__(self, symbol, stop_loss=0.1, take_profit=0.01, window=10):
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.sl_price = 0
        self.tp_price = 0
        self.position = None
        self.entry_price = None
        self.symbol = symbol
        self.prices = []
        self.window = window

        self.dh = DataHandler()
        self.df_history = None
        self.df_today = None
        self.initialized = False

    def _load_history_up_to(self, current_date):
        self.df_history = self.dh.open_data(
            self.symbol, 
            start_date='2023-01-01', 
            end_date=current_date.date()) # change to fetch previous data live
        self.initialized = True

    def update(self, row):

        ts = row["timestamp"]
        if not self.initialized:
            self._load_history_up_to(ts)

        close = row["close"]
        
        if (ts.hour, ts.minute) == (9, 30):
            self.df_today = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'timestamp'])
        if (ts.hour, ts.minute) == (16, 0):
            self.df_history = pd.concat([self.df_history, self.df_today], ignore_index=True)

        self.df_today.loc[len(self.df_today)] = [
            row['open'], row['high'], row['low'], row['close'], row['volume'], row['timestamp']
        ]
        
        daily_avg = self.df_history.groupby(self.df_history["timestamp"].dt.date).agg(
            {'high': 'max', 'low': 'min', 'close': 'last'}
        )
        daily_prices = (daily_avg['high'] + daily_avg['low'] + daily_avg['close']) / 3

        curr_snap = daily_prices[-self.window:]
        moving_average = np.mean(curr_snap)
        moving_std = np.std(curr_snap)

        entry_level = moving_average + 2 * moving_std

        # --- Entry ---
        if self.position is None:
            if close < entry_level: 
                self.position = "long"
                self.entry_price = close
                self.sl_price = close * (1 - self.stop_loss)
                self.tp_price = close * (1 + self.take_profit)
                return 1, self.stop_loss, self.take_profit, 0.8
            
        # if self.position is None:
        #     if ma10 > ma15 > ma20 and close < ma10:  
        #         self.position = "long"
        #         self.entry_price = close
        #         self.sl_price = close * (1 - self.stop_loss)
        #         self.tp_price = close * (1 + self.take_profit)
        #         return 1, self.stop_loss, self.take_profit, 0.8

        # --- Exit ---
        elif self.position == "long":
            if close <= self.sl_price or close >= self.tp_price:
                self.position = None
                return 0, self.stop_loss, self.take_profit, 0.8

        return None, None, None, 0.8