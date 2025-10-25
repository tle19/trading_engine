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

    def update_dates(self, start_date: str, end_date: str):
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")

    def plot_equity(self):
        if not self.intraday_equity:
            print("No equity data to plot.")
            return

        equity = self.intraday_equity
        dates = pd.date_range(self.start_date, self.end_date, periods=len(equity))

        max_points = 20000
        if len(equity) > max_points:
            step = max(1, len(equity) // max_points)
            equity = equity[::step]
            dates = dates[::step]

        plt.figure(figsize=(14, 6))
        plt.plot(dates, equity, label="Strategy", color="blue")

        months = pd.date_range(self.start_date, self.end_date, freq="MS")
        if len(months) > 12:
            step = int(np.ceil(len(months) / 12))
            months = months[::step]
        plt.xticks(months, [m.strftime("%b %Y") for m in months], rotation=45)

        plt.xlabel("Date")
        plt.ylabel("Portfolio Value")
        plt.title(f"{self.symbol} Strategy Equity ({self.start_date.date()} to {self.end_date.date()})")
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        plt.show()