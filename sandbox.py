import json
import pandas as pd
import re
from itertools import combinations
import matplotlib.pyplot as plt

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

    # List of tuples: (diff, shares1, shares2)
    best_combos = []

    for s1 in range(min_s1, max_s1 + 1):
        cash1 = s1 * price1
        for s2 in range(min_s2, max_s2 + 1):
            cash2 = s2 * price2
            diff = abs(cash1 - cash2)
            best_combos.append((diff, s1, s2))

    # Sort by smallest difference
    best_combos.sort(key=lambda x: x[0])

    # Keep top_n
    top_combos = best_combos[:top_n]

    print(f"Top {top_n} share splits (closest to dollar-neutral):")
    for i, (diff, s1, s2) in enumerate(top_combos, start=1):
        val1 = s1 * price1
        val2 = s2 * price2
        print(f"{i}. Symbol1: {s1} (${val1:.2f}), Symbol2: {s2} (${val2:.2f}), $ Diff = {diff:.2f}")
    
    return top_combos[0][1], top_combos[0][2]

def dca_plan(price1, price2, min_pct=0.85, cash=30000):
    shares1, shares2 = compute_share_split(price1, price2, min_pct=min_pct, cash=cash, top_n=5)

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

    print(shares1, shares2)
    print(plan)
    return plan

def packet_sync_check():
    for pair in pairs:
        symbol1 = pair[0]
        symbol2 = pair[1]
        with open("market_logs_2026-03-02.jsonl") as f:
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

        print(pair)
        print(f"Synced packets: {synced_packets}")
        print(f"Unsynced packets: {unsynced_packets}")
        print(f"Average synced timestamp difference: {np.mean(time_diffs):.0f} ms")
        print(f"Min difference: {min(time_diffs)} ms, Max difference: {max(time_diffs)} ms")

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
    return avg_intraday_corr, long_term_corr

def find_pair_corr_combos():
    pair_corrs = []
    for x, y in combinations(symbols, 2):
        avg_intraday_corr, long_term_corr = find_pair_corr(x, y)
        pair_corrs.append({
            "symbol1": x,
            "symbol2": y,
            "avg_intraday_corr": avg_intraday_corr,
            "long_term_corr": long_term_corr
        })

    with open("pair_correlations.json", "w") as f:
        json.dump(pair_corrs, f, indent=4)

def bid_ask_spread():
    for symbol in symbols:
        try:
            df = open_data(symbol, mode="quote")
        except FileNotFoundError:
            continue
            
        spread = abs(df["bid"] - df["ask"])
        print(f"{symbol}: {round(spread.mean(), 5)}")
        print(f"Datapoints: {len(df)}")
        
def spread_dist():
    for symbol in symbols:
        try:
            df = open_data(symbol, mode="quote")
        except FileNotFoundError:
            continue

        spread = abs(df["ask"] - df["bid"])
        lower = spread.quantile(0.20)
        upper = spread.quantile(0.80)
        spread_filtered = spread[(spread >= lower) & (spread <= upper)]

        print(f"{symbol}: mean spread = {round(spread_filtered.mean(), 5)}, datapoints = {len(spread_filtered)}")

        plt.figure(figsize=(12, 6))
        plt.hist(spread_filtered, bins=30, edgecolor='black', color='skyblue')
        plt.title(f"{symbol} Bid-Ask Spread Distribution (5% trimmed)")
        plt.xlabel("Spread")
        plt.ylabel("Count")
        plt.show()

def time_dist(symbol1, symbol2):
    df1 = open_data(symbol1, mode="quote")
    df2 = open_data(symbol2, mode="quote")
    df1['timestamp'] = pd.to_datetime(df1['timestamp'], unit='ms', utc=True).dt.tz_convert(timezone) 
    df2['timestamp'] = pd.to_datetime(df2['timestamp'], unit='ms', utc=True).dt.tz_convert(timezone) 
    all_timestamps = pd.concat([df1['timestamp'], df2['timestamp']]).drop_duplicates().sort_values()

    time_diffs = all_timestamps.diff().dropna()
    time_diffs_seconds = time_diffs.dt.total_seconds()
    total_gaps = len(time_diffs_seconds)

    below_1s = (time_diffs_seconds < 1).sum()
    below_2s = (time_diffs_seconds < 2).sum()

    pct_below_1s = below_1s / total_gaps * 100
    pct_below_2s = below_2s / total_gaps * 100

    print(f"Percentage of gaps < 1 second: {pct_below_1s:.2f}%")
    print(f"Percentage of gaps < 2 seconds: {pct_below_2s:.2f}%")

    plt.figure(figsize=(10, 5))
    plt.hist(time_diffs_seconds, bins=50, color='skyblue', edgecolor='black')
    plt.title('Distribution of Timestamp Differences (seconds)')
    plt.xlabel('Seconds between consecutive timestamps')
    plt.ylabel('Count')
    plt.show()

def backtest_pairs(symbol1, symbol2, df1, df2, window=1000, z=1.75):
    df1 = df1.sort_values('timestamp')
    df2 = df2.sort_values('timestamp')
    hedge_ratio = round(df1["close"].iloc[0] / df2["close"].iloc[0], 1)
    df_merged = pd.merge_asof(df1, df2, on='timestamp', direction='nearest', tolerance=pd.Timedelta('5000ms'), suffixes=('_1','_2'))
    df_merged['spread'] = ((df_merged['close_1'] + df_merged['open_1']) / 2) - ((df_merged['close_2'] * hedge_ratio + df_merged['open_2'] * hedge_ratio) / 2)
    x = df_merged['timestamp']

    df_merged['roll_mean'] = df_merged['spread'].rolling(window).mean()
    df_merged['roll_std'] = df_merged['spread'].rolling(window).std()

    df_merged['upper_band'] = df_merged['roll_mean'] + z * df_merged['roll_std']
    df_merged['lower_band'] = df_merged['roll_mean'] - z * df_merged['roll_std']

    in_trade = False
    trades = []
    direction = None
    above_ub = 0
    below_lb = 0

    for row in df_merged.itertuples():
        # Skip first 'window' rows
        if row.Index < window:
            continue

        s = row.spread
        mean = row.roll_mean
        ub = row.upper_band
        lb = row.lower_band

        if s >= ub:
            above_ub += 1
        if s <= lb:
            below_lb += 1

        # ENTRY
        if not in_trade:
            if s >= ub:
                direction = "sell"      # expect spread to fall toward mean
                entry_spread = s
                entry_index = row.Index
                in_trade = True
            elif s <= lb:
                direction = "buy"       # expect spread to rise toward mean
                entry_spread = s
                entry_index = row.Index
                in_trade = True

        # EXIT
        else:
            exit_spread = s
            exit_index = row.Index
            if direction == "buy" and s >= mean:
                profitable = exit_spread > entry_spread
                trades.append((entry_index, exit_index, entry_spread, exit_spread, direction, profitable))
                in_trade = False
            elif direction == "sell" and s <= mean:
                profitable = exit_spread < entry_spread
                trades.append((entry_index, exit_index, entry_spread, exit_spread, direction, profitable))
                in_trade = False

    plt.figure(figsize=(14, 8))

    plt.subplot(2,1,1)
    plt.plot(df1['timestamp'], df1["close"], label=f"{symbol1}")
    plt.plot(df2['timestamp'], df2["close"] * hedge_ratio, label=f"{symbol2}")
    plt.grid(True)
    plt.legend()

    plt.subplot(2,1,2)
    plt.plot(x, df_merged['spread'], label="Spread")
    plt.plot(x, df_merged['roll_mean'], linestyle="--", label="Mean", color="gray")
    plt.plot(x, df_merged['upper_band'], linestyle="--", label=f"+{z} Std", color="lightgray")
    plt.plot(x, df_merged['lower_band'], linestyle="--", label=f"-{z} Std", color="lightgray")
    
    pos_trades = []
    neg_trades = []
    for entry_index, exit_index, ep, xp, direction, ok in trades:
        distance = abs(xp - ep)
        hold_time = xp - ep  # or compute based on timestamps
        if ok:
            pos_trades.append(distance)
        else:
            neg_trades.append(distance)
        color = "green" if ok else "red"
        
        entry_t = x.iloc[entry_index]
        exit_t  = x.iloc[exit_index]

        plt.plot([entry_t, exit_t], [ep, xp], linewidth=2, color=color)
        mid_x = entry_t + (exit_t - entry_t)/2
        mid_y = (ep + xp)/2
        
        plt.text(mid_x, mid_y + 0.01*distance, f"{distance:.2f}", fontsize=8,
                ha='center', va='bottom', color=color)
        plt.text(mid_x, mid_y - 0.01*distance, f"{hold_time:.2f}", fontsize=8,
                ha='center', va='top', color="black")

    print(len(df_merged), above_ub, below_lb)
    print(f"POS PNL: {sum(pos_trades)}, POS TRADES: {len(pos_trades)}")
    print(f"NEG PNL: {sum(neg_trades)}, NEG TRADES: {len(neg_trades)}")

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

# TICK
symbol1 = "GOOG"
symbol2 = "GOOGL"
start = "2026-03-03"
end = "2026-03-03"
df1 = open_data(symbol1, mode="quote")
df2 = open_data(symbol2, mode="quote")
df1 = df1.rename(columns={"bid": "close", "ask": "open"})
df2 = df2.rename(columns={"bid": "close", "ask": "open"})
df1['timestamp'] = pd.to_datetime(df1['timestamp'], unit='ms', utc=True).dt.tz_convert(timezone) 
df2['timestamp'] = pd.to_datetime(df2['timestamp'], unit='ms', utc=True).dt.tz_convert(timezone)
mask = (df1['timestamp'].dt.date >= pd.to_datetime(start).date()) & \
        (df1['timestamp'].dt.date <= pd.to_datetime(end).date())
df1 = df1.loc[mask]
mask = (df2['timestamp'].dt.date >= pd.to_datetime(start).date()) & \
        (df2['timestamp'].dt.date <= pd.to_datetime(end).date())
df2 = df2.loc[mask]
backtest_pairs(symbol1, symbol2, df1, df2, window=1000, z=2.0)

# INTRADAY
# symbol1 = "XLE"
# symbol2 = "VDE"
# start = "2026-02-26"
# end = "2026-02-26"
# df1 = open_data(symbol1, start_date=start, end_date=end, mode="intraday")
# df2 = open_data(symbol2, start_date=start, end_date=end, mode="intraday")
# df1 = df1.set_index("timestamp").between_time("09:30", "16:00").reset_index()
# df2 = df2.set_index("timestamp").between_time("09:30", "16:00").reset_index()
# backtest_pairs(symbol1, symbol2, df1, df2, window=15, z=2.0)

# DAILY
# symbol1 = "GS"
# symbol2 = "MS"
# start = "2024-02-03"
# end = "2026-02-03"
# df1 = open_data(symbol1, start_date=start, end_date=end, mode="daily")
# df2 = open_data(symbol2, start_date=start, end_date=end, mode="daily")
# backtest_pairs(symbol1, symbol2, df1, df2, window=20, z=1.75)

# with open("trade_logs_live_pt.json") as f:
#     trade_history = json.load(f)["trade_history"]

# for i in range(0, len(trade_history), 2):
#     idx1 = i
#     idx2 = i + 1
#     if idx2 < len(trade_history):
#         t1 = trade_history[idx1]["entry_time"]
#         t2 = trade_history[idx2]["entry_time"]
#         print(abs(t1 - t2))

# compute_share_split(468.14, 74.68, min_pct=0.50, cash=10000, top_n=5)
# dca_plan(56.52, 159.38,  min_pct=0.80, cash=2000)
# find_pair_corr("XLE", "VDE", start="2024-02-03", end="2026-02-03")