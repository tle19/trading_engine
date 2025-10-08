from strategies import Strategy
import pandas as pd
import numpy as np

class MomentumSMAIndicator(Strategy):
    def __init__(self, symbol, window=20, stop_loss=0.01, take_profit=0.01, position_size=1.0):
        super().__init__(symbol, stop_loss, take_profit, position_size)
        self.window = window
        self.prices = []
    
    def generate_signal(self, row):
        update = self.update(row)
        if update is not None:
            return update
        
        self.prices.append(self.close)
        if len(self.prices) < self.window:
            return None
        prices_window = self.prices[-self.window:]
        avg_price = np.mean(self.prices)
        sma = np.mean(prices_window)
        
        # --- Entry logic ---
        if self.position is None:
            if sma > avg_price:
                return self.buy()
            elif sma < avg_price:
                return self.sell()

        self.set_trailing_stop()
        return None