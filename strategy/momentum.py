import numpy as np
import pandas as pd


class Momentum:
    def __init__(self):
        self.profit_ratio = 0.01
        self.rr_ratio = 2   #1:2 rr
        self.history = []
        self.in_position = False
        self.entry_price = 0
    
    def update(self, row):
        close = row['close']
        self.history.append(close)

        # if not self.in_position:

        return
    
    def execute_order(self):
        return
    
    def premarket_prob(self):
        return
    
    def weekday_prob(self):
        return
    
    def mean_reversion(self):
        return
    
    def break_of_structure(self):
        return
    
    def rsi(self):
        return
    
    def fibonacci(self):
        return