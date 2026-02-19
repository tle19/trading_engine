import json
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


from symbols import SYMBOLS
from core import *
from metrics import *
from strategies import *
from models import *
from utils import *

symbols = SYMBOLS

def plot_dist(df, col):
    x = df[col].dropna()
    lo, hi = x.quantile([0.001, 0.999])
    x_clip = x.clip(lo, hi)
    mu = x.mean()
    sigma = x.std()
    print(f"±1σ: {round(mu + sigma, 5)}")
    print(f"±2σ: {round(mu + 2*sigma, 5)}")
    print(f"±3σ: {round(mu + 3*sigma, 5)}")
    plt.figure(figsize=(10, 6))
    plt.hist(x_clip, bins=100, color="lightgray", edgecolor="black")
    plt.axvspan(mu - sigma,   mu + sigma,   color="green",  alpha=0.15, label="68% (±1σ)")
    plt.axvspan(mu - 2*sigma, mu + 2*sigma, color="yellow", alpha=0.15, label="95% (±2σ)")
    plt.axvspan(mu - 3*sigma, mu + 3*sigma, color="red",    alpha=0.15, label="99.7% (±3σ)")
    plt.axvline(mu, color="blue", linestyle="--", linewidth=2, label="Mean")
    plt.title(f"{col} (0.1-99.9% clipped)")
    plt.xlabel(col)
    plt.ylabel("Frequency")
    plt.legend()
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

# ema_window = 50
# lookback = 15
# df = open_data("GOOG", start_date="2024-01-01", end_date="2026-01-01")
# df["ema"] = df["close"].ewm(span=ema_window, adjust=False).mean()
# df["straddle_up"] = (df["close"] > df["ema"]) & (df["open"] < df["ema"])
# df["straddle_down"] = (df["close"] < df["ema"]) & (df["open"] > df["ema"])
# df["ema_max_last5_pct"] = (df["high"].rolling(lookback, min_periods=1).max() - df["ema"]) / df["ema"]
# df["ema_min_last5_pct"] = (df["low"].rolling(lookback, min_periods=1).min() - df["ema"]) / df["ema"]
# df["ema_straddle_target"] = np.where(df["straddle_up"], df["ema_min_last5_pct"],
#     np.where(df["straddle_down"], df["ema_max_last5_pct"], np.nan)
# )

# col = "ema_straddle_target"
# x = df[col].dropna()
# mu = x.mean()
# sigma = x.std()
# df["entry_cond"] = (df[col] >= mu - 2*sigma) | (df[col] <= mu + 2*sigma)

# plot_dist(df, "ema_straddle_target")

symbol1 = "GOOG"
symbol2 = "GOOGL"
start = "2026-02-03"
end = "2026-02-03"

df1 = open_data(symbol1, start_date=start, end_date=end)
df2 = open_data(symbol2, start_date=start, end_date=end)
df1 = df1.set_index("timestamp")
df2 = df2.set_index("timestamp")
df1 = df1.between_time("09:30", "16:00")
df2 = df2.between_time("09:30", "16:00")

# Spread
spread = ((df1["close"] + df1["open"]) / 2) - ((df2["close"] + df2["open"]) / 2)

# Rolling statistics
window = 15
roll_mean = spread.rolling(window).mean()
roll_std = spread.rolling(window).std()

z = 1.75
upper_band = roll_mean + z * roll_std
lower_band = roll_mean - z * roll_std

in_trade = False
trades = []

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
            direction = "long"      # expect spread to fall toward mean
            entry_spread = s
            entry_index = spread.index[i]
            in_trade = True

        elif s <= lb:
            direction = "short"     # expect spread to rise toward mean
            entry_spread = s
            entry_index = spread.index[i]
            in_trade = True

    # EXIT WHEN SPREAD CROSSES MEAN
    else:
        if np.sign(s - mean) != np.sign(entry_spread - mean) or abs(s - mean) < 1e-12:
            exit_spread = s
            exit_index = spread.index[i]

            # PROFIT LOGIC (FINAL):
            if direction == "long":
                profitable = exit_spread < entry_spread   # downward slope
            else: # short
                profitable = exit_spread > entry_spread   # upward slope

            trades.append((entry_index, exit_index, entry_spread, exit_spread, direction, profitable))
            in_trade = False

plt.figure(figsize=(14, 8))

plt.subplot(2,1,1)
plt.plot(df1["close"], label=symbol1)
plt.plot(df2["close"], label=symbol2)
plt.grid(True)
plt.legend()

plt.subplot(2,1,2)
plt.plot(spread, label="Spread")
plt.plot(roll_mean, linestyle="--", label="Mean", color="gray")
plt.plot(upper_band, linestyle="--", label=f"+{z} Std", color="lightgray")
plt.plot(lower_band, linestyle="--", label=f"-{z} Std", color="lightgray")

for entry_t, exit_t, ep, xp, direction, ok in trades:
    color = "green" if ok else "red"
    plt.plot([entry_t, exit_t], [ep, xp], linewidth=2, color=color)

plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()