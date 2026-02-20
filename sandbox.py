import json
import numpy as np
import pandas as pd
from itertools import combinations
import matplotlib.pyplot as plt


from symbols import SYMBOLS
from core import *
from metrics import *
from strategies import *
from models import *
from utils import *

symbols = SYMBOLS

def find_pair_corr(symbol1, symbol2, start="2024-02-03", end="2026-02-03"):
    # INTRADAY
    df1 = open_data(symbol1, start_date=start, end_date=end)
    df2 = open_data(symbol2, start_date=start, end_date=end)
    df1 = df1.set_index("timestamp").between_time("09:30", "16:00")
    df2 = df2.set_index("timestamp").between_time("09:30", "16:00")

    df_intraday = pd.concat([df1['close'], df2['close']], axis=1, join="inner")
    df_intraday.columns = ['a', 'b']

    returns_intraday = df_intraday.pct_change().dropna()
    daily_corr_intraday = returns_intraday.groupby(returns_intraday.index.date).apply(
        lambda x: x['a'].corr(x['b'])
    )
    avg_intraday_corr = daily_corr_intraday.mean()

    # DAILY
    df1 = open_data(symbol1, start_date=start, end_date=end, mode="daily")
    df2 = open_data(symbol2, start_date=start, end_date=end, mode="daily")
    df1['date'] = pd.to_datetime(df1['timestamp']).dt.date
    df2['date'] = pd.to_datetime(df2['timestamp']).dt.date

    df_daily = pd.merge(df1[['date', 'close']], df2[['date', 'close']], on='date')
    df_daily.columns = ['date', 'a', 'b']

    returns_daily = df_daily[['a','b']].pct_change().dropna()
    long_term_corr = returns_daily['a'].corr(returns_daily['b'])

    print(f"{symbol1}-{symbol2} Intraday Correlation: {avg_intraday_corr}")
    print(f"{symbol1}-{symbol2} Daily Correlation: {long_term_corr}")

def backtest_pairs(symbol1, symbol2, df1, df2, window=1000, z=1.75):
    hedge_ratio = round(df1["close"].iloc[0] / df2["close"].iloc[0], 2)
    spread = ((df1["close"] + df1["open"]) / 2) - ((df2["close"] * hedge_ratio + df2["open"] * hedge_ratio) / 2)

    roll_mean = spread.rolling(window).mean()
    roll_std = spread.rolling(window).std()

    upper_band = roll_mean + z * roll_std
    lower_band = roll_mean - z * roll_std

    in_trade = False
    trades = []
    direction = None

    for i in range(len(spread)):
        if i < window:
            continue

        s = spread.iloc[i]
        mean = roll_mean.iloc[i]
        ub = upper_band.iloc[i]
        lb = lower_band.iloc[i]

        # ENTRY
        if not in_trade:
            if s >= ub:
                direction = "sell"      # expect spread to fall toward mean
                entry_spread = s
                entry_index = spread.index[i]
                in_trade = True

            elif s <= lb:
                direction = "buy"     # expect spread to rise toward mean
                entry_spread = s
                entry_index = spread.index[i]
                in_trade = True

        # EXIT
        else:
            exit_spread = s
            exit_index = spread.index[i]
            if direction == "buy":
                if s >= mean:
                    direction = None
                    profitable = exit_spread > entry_spread
                    trades.append((entry_index, exit_index, entry_spread, exit_spread, direction, profitable))
                    in_trade = False
            else:
                if s <= mean:
                    direction = None
                    profitable = exit_spread < entry_spread
                    trades.append((entry_index, exit_index, entry_spread, exit_spread, direction, profitable))
                    in_trade = False

    plt.figure(figsize=(14, 8))

    plt.subplot(2,1,1)
    plt.plot(df1["close"], label=f"{symbol1}")
    plt.plot(df2["close"] * hedge_ratio, label=f"{symbol2}")
    plt.grid(True)
    plt.legend()

    plt.subplot(2,1,2)
    plt.plot(spread, label="Spread")
    plt.plot(roll_mean, linestyle="--", label="Mean", color="gray")
    plt.plot(upper_band, linestyle="--", label=f"+{z} Std", color="lightgray")
    plt.plot(lower_band, linestyle="--", label=f"-{z} Std", color="lightgray")

    trade_times = []
    for entry_t, exit_t, ep, xp, direction, ok in trades:
        color = "green" if ok else "red"
        plt.plot([entry_t, exit_t], [ep, xp], linewidth=2, color=color)
        trade_times.append(exit_t - entry_t)
        
    print("Average Trade Time:", np.mean(trade_times), "seconds")

    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

def find_proba(df):
    wins = 0
    losses = 0

    target = 0
    stop = 0
    for i, entry_cond in enumerate(df["entry_cond"]):
        if not entry_cond:
            continue
        if df["straddle_up"]:
            direction = 1
        elif df["straddle_down"]:
            direction = -1
        # find timestamp
        # set target to ema +/- abs(ema_straddle_target)
        # set stop to ema +/- abs(target - ema) / 2
        for j in range(i + 1, len(df)):
            high = df.loc[j, "high"]
            low = df.loc[j, "low"]

            if high >= target:
                wins += 1
                break
            elif low <= stop:
                losses += 1
                break

            if df.loc["timestamp"] == 15.59:
                break

for x, y in combinations(symbols, 2):
    find_pair_corr(x, y)

# TICK
# symbol1 = "XOM"
# symbol2 = "CVX"
# with open(f"data/{symbol1}-{symbol2}_quote.json") as f:
#     data = json.load(f)
# rows1 = []
# rows2 = []
# for row in data:
#     new_row = row.copy()
#     new_row["close"] = new_row.pop("bid")
#     new_row["open"] = new_row.pop("ask")
#     if row["symbol"] == symbol1:
#         rows1.append(new_row)
#     elif row["symbol"] == symbol2:
#         rows2.append(new_row)
# df1 = pd.DataFrame(rows1)
# df2 = pd.DataFrame(rows2)

# INTRADAY
# symbol1 = "V"
# symbol2 = "MA"
# start = "2026-02-03"
# end = "2026-02-03"
# df1 = open_data(symbol1, start_date=start, end_date=end)
# df2 = open_data(symbol2, start_date=start, end_date=end)
# df1 = df1.set_index("timestamp").between_time("09:30", "16:00")
# df2 = df2.set_index("timestamp").between_time("09:30", "16:00")

# DAILY
# symbol1 = "NVDA"
# symbol2 = "AMD"
# start = "2023-02-03"
# end = "2026-02-03"
# df1 = open_data(symbol1, start_date=start, end_date=end, mode="daily")
# df2 = open_data(symbol2, start_date=start, end_date=end, mode="daily")

# backtest_pairs(symbol1, symbol2, df1, df2, window=1000, z=1.75)