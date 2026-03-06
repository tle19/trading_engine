import json
import pandas as pd
import re
import numpy as np
from itertools import combinations
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import coint

from zoneinfo import ZoneInfo

from symbols import SYMBOLS, PAIRS
from core import *
from metrics import *
from strategies import *
from models import *
from utils import *

timezone = ZoneInfo("America/New_York")
symbols = SYMBOLS
pairs = PAIRS

def compute_share_split(price1, price2, min_pct=0.85, cash=25000, top_n=5):
    cash = cash / 2
    max_s1 = int(cash // price1)
    max_s2 = int(cash // price2)
    min_s1 = int(max_s1 * min_pct)
    min_s2 = int(max_s2 * min_pct)

    best_combos = []

    for s1 in range(min_s1, max_s1 + 1):
        cash1 = s1 * price1
        for s2 in range(min_s2, max_s2 + 1):
            cash2 = s2 * price2
            diff = abs(cash1 - cash2)
            best_combos.append((diff, s1, s2))

    best_combos.sort(key=lambda x: x[0])

    top_combos = best_combos[:top_n]

    print(f"Top {top_n} share splits (closest to dollar-neutral):")
    for i, (diff, s1, s2) in enumerate(top_combos, start=1):
        val1 = s1 * price1
        val2 = s2 * price2
        print(f"{i}. Symbol1: {s1} (${val1:.2f}), Symbol2: {s2} (${val2:.2f}), $ Diff = {diff:.2f}")
    
    return best_combos

def dca_plan(price1, price2, min_pct=0.85, cash=30000):
    top_combos = compute_share_split(price1, price2, min_pct=min_pct, cash=cash)
    shares1, shares2 = top_combos[0][1], top_combos[0][2]

    plan = []
    max_steps = max(1, int(1 / 0.10))
    num_passes = min(max_steps, min(shares1, shares2))

    for _ in range(num_passes):
        plan.append([1, 1])

    rem1 = shares1 - num_passes
    rem2 = shares2 - num_passes

    for i in range(rem1):
        plan[i % num_passes][0] += 1
    for i in range(rem2):
        plan[i % num_passes][1] += 1

    plan.reverse()
    plan = [tuple(p) for p in plan]

    print(f"DCA Plan: {plan}")
    return plan

def find_pair_stats(symbol1, symbol2, start="2024-02-03", end="2026-02-03"):
    # INTRADAY CORRELATION
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

    # DAILY CORRELATION
    df1 = open_data(symbol1, start_date=start, end_date=end, mode="daily")
    df2 = open_data(symbol2, start_date=start, end_date=end, mode="daily")
    df1['date'] = pd.to_datetime(df1['timestamp']).dt.date
    df2['date'] = pd.to_datetime(df2['timestamp']).dt.date

    df_daily = pd.merge(df1[['date', 'close']], df2[['date', 'close']], on='date')
    df_daily.columns = ['date', 'a', 'b']

    returns_daily = df_daily[['a','b']].pct_change().dropna()
    long_term_corr = returns_daily['a'].corr(returns_daily['b'])

    # DAILY COINTEGRATION
    score, pvalue, _ = coint(df_daily['a'], df_daily['b'])

    print(f"{symbol1}-{symbol2} Intraday Correlation: {avg_intraday_corr:.4f}")
    print(f"{symbol1}-{symbol2} Daily Correlation: {long_term_corr:.4f}")
    print(f"{symbol1}-{symbol2} Cointegration p-value: {pvalue:.4f}")

    return avg_intraday_corr, long_term_corr, pvalue

def find_pair_corr_combos():
    pair_corrs = []
    for x, y in combinations(symbols, 2):
        avg_intraday_corr, long_term_corr, pvalue = find_pair_stats(x, y)
        pair_corrs.append({
            "symbol1": x,
            "symbol2": y,
            "avg_intraday_corr": avg_intraday_corr,
            "long_term_corr": long_term_corr,
            "coint_pvalue": pvalue
        })

    with open("pair_correlations.json", "w") as f:
        json.dump(pair_corrs, f, indent=4)

def check_packet_sync(symbol1, symbol2, log_file="market_logs_2026-03-02.jsonl"):
    with open(log_file) as f:
        trade_history = [json.loads(line) for line in f]

    time_diffs = []
    synced_packets = 0
    unsynced_packets = 0

    for packet in trade_history:
        symbol_timestamps = {}
        for quote in packet:
            match = re.search(r"\[(\w+)\].*timestamp=(\d+)", quote)
            if match:
                symbol, ts = match.group(1), int(match.group(2))
                if symbol in (symbol1, symbol2):
                    symbol_timestamps[symbol] = ts

        if symbol1 in symbol_timestamps and symbol2 in symbol_timestamps:
            diff_ms = abs(symbol_timestamps[symbol1] - symbol_timestamps[symbol2])
            time_diffs.append(diff_ms)
            synced_packets += 1
        else:
            unsynced_packets += 1

    total_packets = synced_packets + unsynced_packets

    print(f"Synced packets: {synced_packets} ({synced_packets / total_packets:.2%})")
    print(f"Unsynced packets: {unsynced_packets} ({unsynced_packets / total_packets:.2%})")
    print(f"Average difference: {np.mean(time_diffs):.0f} ms")
    print(f"Min difference: {min(time_diffs)} ms") 
    print(f"Max difference: {max(time_diffs)} ms") 

def visualize_bid_ask_spread(symbol):
    try:
        df = open_data(symbol, mode="quote")
    except FileNotFoundError:
        return

    spread = df["ask"] - df["bid"]
    
    print(f"Average bid-ask spread: {spread.mean():.4f}")
    print(f"Min bid-ask spread: {max(0, min(spread)):.4f}") 
    print(f"Max bid-ask spread: {max(spread):.4f}")   

    plt.figure(figsize=(10, 5))
    plt.hist(spread, bins=30, edgecolor='black')
    plt.title(f"{symbol} Bid-Ask Spread Distribution")
    plt.xlabel("Bid-Ask Spread")
    plt.ylabel("Count")
    plt.show()

def visualize_latency(symbol1, symbol2):
    try:
        df1 = open_data(symbol1, mode="quote")
        df2 = open_data(symbol2, mode="quote")
    except FileNotFoundError:
        return
    
    df1['timestamp'] = pd.to_datetime(df1['timestamp'], unit='ms', utc=True).dt.tz_convert(timezone) 
    df2['timestamp'] = pd.to_datetime(df2['timestamp'], unit='ms', utc=True).dt.tz_convert(timezone)

    df1 = df1.sort_values("timestamp")
    df2 = df2.sort_values("timestamp")
    
    df2 = df2.rename(columns={"timestamp": "timestamp_2"})
    # df_merged = pd.merge_asof(df1, df2, on='timestamp', direction='nearest', tolerance=5000, suffixes=(f'_{symbol1}',f'_{symbol2}'))
    merged = pd.merge_asof(
        df1,
        df2,
        left_on="timestamp",
        right_on="timestamp_2",
        direction="nearest"
    )

    latency = (merged["timestamp"] - merged["timestamp_2"]).abs()
    latency_ms = latency.dt.total_seconds() * 1000

    print(f"Mean Latency: {latency_ms.mean():.0f} ms")
    print(f"95th percentile latency: {latency_ms.quantile(0.95):.0f} ms")

    plt.figure(figsize=(10, 5))
    plt.hist(latency_ms, bins=30, edgecolor="black")
    plt.title(f"Latency Distribution ({symbol1} vs {symbol2})")
    plt.xlabel("Milliseconds")
    plt.ylabel("Count")
    plt.show()

def visualize_spread(symbol1, symbol2, window=1000, z=2):
    with open(f"{symbol1}-{symbol2}_spread.json", "r") as f:
        spread = json.load(f)

    spread = pd.Series(spread)
    roll_mean = spread.rolling(window).mean()
    roll_std = spread.rolling(window).std()
    upper_band = roll_mean + z * roll_std
    lower_band = roll_mean - z * roll_std

    plt.figure(figsize=(10, 5))
    plt.plot(spread, label="Spread")
    plt.plot(roll_mean, linestyle="--", label="Mean", color="gray")
    plt.plot(upper_band, linestyle="--", label=f"+{z} Std", color="lightgray")
    plt.plot(lower_band, linestyle="--", label=f"-{z} Std", color="lightgray")
    plt.legend()
    plt.show()



# symbols = ["SPY", "QQQ", "GLD", "SLV", "XLE", "VDE", "IBIT", "ETHA"]


# compute_share_split(687.12, 602.37, min_pct=0.85, cash=25000, top_n=5)
# dca_plan(687.12, 602.37, min_pct=0.85, cash=30000)

# find_pair_stats("XLE", "VDE")
# find_pair_corr_combos()

# check_packet_sync("XLE", "VDE", log_file="market_logs_2026-03-04.jsonl")
# visualize_bid_ask_spread("GLD")
# visualize_latency("GLD", "SLV")
# visualize_spread("GLD", "SLV")
