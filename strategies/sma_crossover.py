from strategies import Strategy
import numpy as np

class SMACrossoverIndicator(Strategy):
    def __init__(self, symbol, short_window=20, long_window=30, stop_loss=0.01, take_profit=0.01, position_size=1.0):
        super().__init__(symbol, stop_loss, take_profit, position_size)
        self.short_window = short_window
        self.long_window = long_window
        self.prices = []
    
    def generate_signal(self, row):
        update = self.update(row)
        if update is not None:
            return update
        
        self.prices.append(self.close)
        if len(self.prices) < self.long_window:
            return None
        short_sma = np.mean(self.prices[-self.short_window:])
        long_sma = np.mean(self.prices[-self.long_window:])

        # --- Entry logic ---
        if self.position is None:
            if short_sma > long_sma:
                return self.buy()
            elif short_sma < long_sma:
                return self.sell()

        self.set_trailing_stop()
        return None