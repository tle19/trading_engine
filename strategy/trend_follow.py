import numpy as np
import pandas as pd


class TrendFollow:
    def __init__(self):
        self.profit_ratio = 0.01
        self.rr_ratio = 2   #1:2 rr
        self.history = []
        self.in_position = False
        self.entry_price = 0
    
    def update(self, row):
        close = row['close']
        self.history.append(close)
        return
    
    def execute_order(self):

        return