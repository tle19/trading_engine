import os
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from utils import *

class Plotting:
    def __init__(self, symbol, img_path="plots"):
        self.symbol = symbol
        self.img_path = img_path
        
        self.intraday_equity = {}
        self.start_date = None
        self.end_date = None

    def update_data(self, intraday_equity):
        self.intraday_equity = intraday_equity.copy()
        dates = sorted(intraday_equity)
        self.start_date = dates[0]
        self.end_date = dates[-1]

    def plot_equity(self, display=True):
        intraday_equity = [v for k, v in sorted(self.intraday_equity.items())]
        if not intraday_equity:
            print("No equity data to plot.")
            return

        equity = np.array(intraday_equity)
        dates = pd.date_range(self.start_date, self.end_date, periods=len(equity))

        max_points = 20000
        if len(equity) > max_points:
            step = max(1, len(equity) // max_points)
            equity = equity[::step]
            dates = dates[::step]

        plt.figure(figsize=(14, 6))
        plt.plot(dates, equity, label="Strategy", color="seagreen")

        self.plot_benchmark(dates, equity)
        self.plot_drawdown(dates, equity)

        plt.xlabel("Date")
        plt.ylabel("Portfolio Value")
        plt.title(f"{self.symbol} Strategy Equity ({self.start_date.date()} to {self.end_date.date()})")
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        os.makedirs(self.img_path, exist_ok=True)
        filename = f"{self.symbol}_{self.start_date.date()}_{self.end_date.date()}.png"
        file_path = os.path.join(self.img_path, filename)
        plt.savefig(file_path)
        if display:
            plt.show()
        plt.close()

    def plot_benchmark(self, dates, equity):
        if self.symbol == "AGGREGATE":
            df = open_data("SPY", self.start_date, self.end_date, "daily")
            label = "S&P 500 (Buy & Hold)"
            dates_naive = dates.tz_localize(None)
            spy_series = pd.Series(df["close"].values, index=pd.to_datetime(df.index))
            spy_intraday = spy_series.reindex(dates_naive, method="ffill")
            stock_scaled = spy_intraday.values / spy_intraday.values[0] * equity[0]
            plt.plot(dates, stock_scaled, label=label, color="gray", linestyle="--", alpha=0.7)
        else:
            df = open_data(self.symbol, self.start_date, self.end_date)
            label = f"{self.symbol} (Buy & Hold)"
            stock_close = df["close"].values
            min_len = min(len(stock_close), len(equity))
            stock_close = stock_close[:min_len]
            equity = equity[:min_len]
            dates = dates[:min_len]

            stock_scaled = stock_close / stock_close[0] * equity[0]
            plt.plot(dates, stock_scaled, label=label, color="gray", linestyle="--", alpha=0.7)
        
    def plot_drawdown(self, dates, equity):
        peak = equity[0]
        peak_idx = 0
        drawdown_segments = []

        for i in range(1, len(equity)):
            if equity[i] > peak:
                if peak_idx != i - 1:
                    drawdown_segments.append((peak_idx, i - 1, peak))
                peak = equity[i]
                peak_idx = i

        if peak_idx < len(equity) - 1:
            drawdown_segments.append((peak_idx, len(equity) - 1, peak))

        for start, end, peak_val in drawdown_segments:
            plt.hlines(y=peak_val, xmin=dates[start], xmax=dates[end], color="red", linewidth=1, alpha=0.5)
            plt.fill_between(dates[start:end + 1], equity[start:end + 1], peak_val, 
                            color="red", alpha=0.1)