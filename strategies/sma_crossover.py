from strategies import Strategy
import numpy as np

class SMACrossoverIndicator(Strategy):
    def __init__(self, symbol, short_window=10, long_window=20, 
                 stop_loss=0.005, take_profit=0.015, position_size=1.0):
        super().__init__(symbol, stop_loss, take_profit, position_size)
        self.short_window = short_window
        self.long_window = long_window
        self.prices = []
    
    def generate_signal(self, row):
        update = self.update(row)
        self.reset_data()
        self.prices.append(self.close) # (self.close + self.high + self.low) / 3
        if update is not None:
            return update
        
        if len(self.prices) < self.long_window:
            return None
            
        short_sma = self.compute_sma(self.short_window)
        long_sma = self.compute_sma(self.long_window)

        # --- Entry logic ---
        if self.position is None:
            if short_sma > long_sma:
                return self.buy()
            elif short_sma < long_sma:
                return self.sell()

        self.set_trailing_stop()
        return None
    
    def compute_sma(self, window):
        return np.mean(self.prices[-window:])
    
    def reset_data(self):
        if (self.ts.hour, self.ts.minute) <= (9, 30):
            self.prices = []