import numpy as np


class MeanReversionIndicator:
    def __init__(self, window=20, risk_pct=0.01, rr_ratio=3): #WIP
        self.window = window
        self.risk_pct = risk_pct
        self.rr_ratio = rr_ratio
        self.history = []
        self.in_position = False
        self.entry_price = 0

    def update(self, row):
        close = row['close']
        self.history.append(close)

        if len(self.history) < self.window:
            return 0

        ma = np.mean(self.history[-self.window:])
        diff = ma - close

        if not self.in_position and diff > 0:
            self.in_position = True
            self.entry_price = close
            return 1

        if self.in_position:
            take_profit = self.entry_price * (1 + self.risk_pct * self.rr_ratio)
            stop_loss = self.entry_price * (1 - self.risk_pct)
            if close >= take_profit or close <= stop_loss:
                self.in_position = False
                return -1

        return 0
