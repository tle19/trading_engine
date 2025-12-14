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

    # def _update_dates(self):
    #     dates = list(self.intraday_equity)
    #     self.duration = dates[-1].date() - dates[0].date()

    def update_dates(self, start_date: str, end_date: str):
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")

    def plot_equity(self, save_plot=False, overlay=False):
        intraday_equity = list(self.intraday_equity.values())
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
        plt.plot(dates, equity, label="Strategy", color="blue")

        if overlay:
            self.plot_overlay(dates, equity)

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
        if save_plot:
            os.makedirs(self.img_path, exist_ok=True)
            filename = f"{self.symbol}_{self.start_date.date()}_{self.end_date.date()}.png"
            file_path = os.path.join(self.img_path, filename)
            plt.savefig(file_path)
        else:
            plt.show()
        plt.close()

    def plot_overlay(self, dates, equity):
        df = open_data(self.symbol, self.start_date, self.end_date, start_time="9:30", end_time="16:00")

        if df.empty or "close" not in df.columns:
            print("No valid stock data to overlay.")
            return

        stock_close = df["close"].values

        min_len = min(len(stock_close), len(equity))
        stock_close = stock_close[:min_len]
        equity = equity[:min_len]
        dates = dates[:min_len]

        stock_norm = (stock_close - stock_close.min()) / (stock_close.max() - stock_close.min())
        equity_norm = (equity - equity.min()) / (equity.max() - equity.min())

        stock_scaled = stock_norm * (equity.max() - equity.min()) + equity.min()

        plt.plot(dates, stock_scaled, label=f"{self.symbol} (Normalized Price)",
                color="orange", linestyle="--", alpha=0.7)