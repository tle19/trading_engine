import pandas as pd

class MeanReversionIndicator:
    def __init__(self, window=20, threshold=0.01):
        self.window = window
        self.threshold = threshold
        self.history = []
        self.in_position = False  # track if we are long

    def update(self, row):
        close = row['close']
        self.history.append(close)

        if len(self.history) > 1000:
            self.history.pop(0)

        if len(self.history) < self.window:
            return 0  # not enough data

        ma = sum(self.history[-self.window:]) / self.window

        # Buy signal only if not already long
        if close < ma * (1 - self.threshold) and not self.in_position:
            self.in_position = True
            return 1  # buy

        # Exit signal only if in position
        elif close >= ma and self.in_position:
            self.in_position = False
            return 0  # exit

        return 0  # hold / no action

