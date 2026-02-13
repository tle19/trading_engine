import os
from itertools import accumulate
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
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

    def overview(self, display=True):
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

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, gridspec_kw={'height_ratios': [3, 1]})

        self._plot_equity_and_benchmark(ax1, dates, equity)
        self._plot_drawdown(ax2, dates, equity)
        plt.tight_layout()
        os.makedirs(self.img_path, exist_ok=True)
        filename = f"{self.symbol}_{self.start_date.date()}_{self.end_date.date()}.png"
        file_path = os.path.join(self.img_path, filename)
        plt.savefig(file_path)
        if display:
            plt.show()
        plt.close()

    def _plot_equity_and_benchmark(self, ax, dates, equity):
        if self.symbol == "AGGREGATE":
            df = open_data("SPY", self.start_date, self.end_date, "daily")
            label = "S&P 500"
        else:
            df = open_data(self.symbol, self.start_date, self.end_date, "daily")
            label = f"{self.symbol}"

        benchmark_intraday = pd.Series(index=dates, dtype=float)
        daily_dates = pd.to_datetime(df["timestamp"]).dt.date.tolist()
        daily_closes = df['close'].values
        daily_idx = 0

        for ts in dates:
            ts_date = ts.date()
            if ts_date > daily_dates[daily_idx] and ts_date in daily_dates:
                daily_idx += 1
            benchmark_intraday.loc[ts] = daily_closes[daily_idx]

        shares = equity[0] / benchmark_intraday.iloc[0]
        benchmark_intraday = benchmark_intraday * shares

        ax.plot(dates, equity, label="Strategy", color="mediumseagreen", linewidth=2.0, alpha=0.8)
        ax.plot(dates, benchmark_intraday, label=label, color="gray", linewidth=2.0, alpha=0.8)
        ax.axhline(y=equity[0], color='black', linestyle='--', linewidth=1.0, alpha=0.8)
        ax.grid(True, linestyle=":", alpha=0.3)
        ax.set_title(f"Strategy Performance ({self.symbol})")
        ax.set_ylabel("Portfolio Value")
        ax.legend()
        
    def _plot_drawdown(self, ax, dates, equity):
        running_max = list(accumulate(equity, max))
        drawdown_pct = [(eq - rm) / rm * 100 for eq, rm in zip(equity, running_max)]
        ax.plot(dates, drawdown_pct, color="salmon", linewidth=2.0)
        ax.fill_between(dates, drawdown_pct, color="salmon", alpha=0.5)
        ax.grid(True, linestyle=":", alpha=0.3)
        ax.set_title("Drawdown (%)")
        ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    
    def _plot_monthly_returns(self):
        raise NotImplementedError