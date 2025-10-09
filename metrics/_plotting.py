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
        if start_date and end_date:
            self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
            self.end_date = datetime.strptime(end_date, "%Y-%m-%d")

    def plot_equity(self):
        if not self.intraday_equity:
            print("No equity data to plot.")
            return

        df = pd.DataFrame({"equity": self.intraday_equity})

        # Create date index if dates provided
        if self.start_date and self.end_date:
            df.index = pd.date_range(self.start_date, self.end_date, periods=len(df))

        # Plot
        plt.figure(figsize=(14, 6))
        plt.plot(df.index, df["equity"], label="Strategy", color="blue")

        # Format x-axis ticks
        if self.start_date and self.end_date:
            months = pd.date_range(self.start_date, self.end_date, freq="MS")
            if len(months) > 12:  # cap to ~12 ticks
                months = months[::int(np.ceil(len(months) / 12))]
            plt.xticks(months, [m.strftime("%b %Y") for m in months], rotation=45)

        plt.xlabel("Date")
        plt.ylabel("Portfolio Value")
        title = f"{self.symbol} Strategy Equity"
        if self.start_date and self.end_date:
            title += f" ({self.start_date.date()} to {self.end_date.date()})"
        plt.title(title)

        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        plt.show()