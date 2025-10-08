from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

class Plotting:
    def __init__(self, symbol):
        self.symbol = symbol
        self.intraday_equity = []
        self.start_date = None
        self.end_date = None

    def update_intraday_equity(self, equity):
        self.intraday_equity.append(equity)

    def update_dates(self, start_date="", end_date=""):
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")

    def plot_equity(self):
        df = pd.DataFrame({"equity": self.intraday_equity})

        # Create date index if start/end dates provided
        if self.start_date and self.end_date:
            df.index = pd.date_range(start=self.start_date, end=self.end_date, periods=len(df))

        plt.figure(figsize=(14,6))
        plt.plot(df.index, df["equity"], label='Strategy', color='blue')

        # X-axis ticks
        if self.start_date and self.end_date:
            months = pd.date_range(start=self.start_date, end=self.end_date, freq='MS')
            if len(months) > 12:
                step = int(np.ceil(len(months) / 12))
                months = months[::step]
            month_positions = [np.searchsorted(df.index.values, m) for m in months]
            plt.xticks(month_positions, [m.strftime('%b %Y') for m in months], rotation=45)

        plt.xlabel("Date")
        plt.ylabel("Portfolio Value")
        plt.title(f"{self.symbol} Strategy Equity ({self.start_date.date()} to {self.end_date.date()})" 
                if self.start_date and self.end_date else f"{self.symbol} Strategy Equity")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()