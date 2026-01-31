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
# df = open_data("GOOG", start_date="2024-01-01", end_date="2026-01-01", start_time="10:00", end_time="15:59")
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

with open("trade_logs.json", "r") as f:
    data = json.load(f)
trade_history = data.get("trade_history", [])
df = pd.json_normalize(trade_history, sep="_")
df["abs_atr_change"] = abs(df["features_curr_day_atr_mean"] - df["features_prev_day_atr_mean"])
plt.figure(figsize=(8,6))
sns.scatterplot(x="abs_atr_change", y="pnl_pct", data=df)
plt.xlabel("Absolute ATR Change (curr - prev)")
plt.ylabel("PnL %")
plt.title("Distribution of ATR Change vs PnL %")
plt.grid(True)
plt.show()