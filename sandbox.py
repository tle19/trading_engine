import json
import time
import numpy as np
import pandas as pd
import re
from itertools import combinations
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import coint

import schwabdev

from symbols import *
from core import *
from metrics import *
from strategies import *
from models import *
from utils import *

def test_order(symbol="AAPL"):
    eq = Equities(symbol, SMACrossover)

    fill_price = eq.buy(1, symbol, 1)
    order_id = eq.sell_oco(symbol, 1, 333.0, 333.5)
    time.sleep(20)
    fill_price = eq.get_fill_price(order_id, 1, instruction="oco", timeout=1)
    print(fill_price)

def acc_latency():
    config = load_config()
    client = schwabdev.Client(config['app_key'], config['app_secret'])
    hash = client.linked_accounts().json()[0].get('hashValue')

    start = time.perf_counter()
    details = client.account_details(hash)
    details_json = details.json()
    cash_balance = details_json["securitiesAccount"]["currentBalances"]["cashBalance"]
    end = time.perf_counter()
    print(f"Execution time: {end - start:.6f} seconds")
    print(cash_balance)

def find_num_orders(file="trade_logs/trade_logs.json"):
    with open(file) as f:
        trade_history = json.load(f)["trade_history"]

    orders = 0
    seen_exits = set()

    for trade in trade_history:
        orders += 1
        
        exit_key = (trade["exit_time"], trade["symbol"])
        if exit_key not in seen_exits:
            orders += 1
            seen_exits.add(exit_key)

    print(f"TOTAL ORDERS: {orders}")

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
    def prepare_df(symbol, mode):
        df = open_data(symbol, start_date=start, end_date=end, mode=mode)
        if mode == "intraday":
            df = df.set_index("timestamp").between_time("09:30", "16:00").reset_index()
        return df[['timestamp', 'open', 'high', 'low', 'close']]

    df_intraday1 = prepare_df(symbol1, "intraday")
    df_intraday2 = prepare_df(symbol2, "intraday")
    df_intraday = pd.merge(df_intraday1, df_intraday2, on='timestamp')
    
    df_daily1 = prepare_df(symbol1, "daily")
    df_daily2 = prepare_df(symbol2, "daily")
    df_daily = pd.merge(df_daily1, df_daily2, on='timestamp')

    def compute_spread_move(df, window=10, mode="intraday"):
        df['date'] = df['timestamp'].dt.date

        beta = (df['close_x'] / df['close_y']).ewm(span=window, adjust=False).mean()
        spread = df['close_x'] - beta * df['close_y']
        mean = spread.rolling(window).mean()
        std = spread.rolling(window).std()

        in_trade = False
        entry_price = 0
        spread_moves = []
        curr_date = df['date'][0]

        for i in range(len(spread)):
            if mode == "intraday" and df['date'].iloc[i] != curr_date:
                in_trade = False
                entry_price = 0
                curr_date = df['date'].iloc[i]

            if not in_trade:
                if spread.iloc[i] > mean.iloc[i] + 2 * std.iloc[i]:
                    in_trade = "short"
                    entry_price = spread.iloc[i]
                elif spread.iloc[i] < mean.iloc[i] - 2 * std.iloc[i]:
                    in_trade = "long"
                    entry_price = spread.iloc[i]
            else:
                if in_trade == "short" and spread.iloc[i] <= mean.iloc[i]:
                    spread_moves.append(entry_price - spread.iloc[i])
                    in_trade = False
                elif in_trade == "long" and spread.iloc[i] >= mean.iloc[i]:
                    spread_moves.append(spread.iloc[i] - entry_price)
                    in_trade = False

        return np.mean(spread_moves) if spread_moves else 0.00, len(spread_moves)
    
    def intraday_group_corr(df, col_x, col_y):
        return df.groupby(df['timestamp'].dt.date).apply(
            lambda x: x[col_x].pct_change().corr(x[col_y].pct_change())
        ).mean()
    def daily_group_corr(df, col_x, col_y):
        return df[col_x].pct_change().corr(df[col_y].pct_change())
    intraday_open_corr = intraday_group_corr(df_intraday, 'open_x', 'open_y')
    intraday_high_corr = intraday_group_corr(df_intraday, 'high_x', 'high_y')
    intraday_low_corr = intraday_group_corr(df_intraday, 'low_x', 'low_y')
    intraday_close_corr = intraday_group_corr(df_intraday, 'close_x', 'close_y')
    intraday_corr = (intraday_open_corr + intraday_high_corr + intraday_low_corr + intraday_close_corr) / 4
    daily_open_corr = daily_group_corr(df_daily, 'open_x', 'open_y')
    daily_high_corr = daily_group_corr(df_daily, 'high_x', 'high_y')
    daily_low_corr = daily_group_corr(df_daily, 'low_x', 'low_y')
    daily_close_corr = daily_group_corr(df_daily, 'close_x', 'close_y')
    daily_corr = (daily_open_corr + daily_high_corr + daily_low_corr + daily_close_corr) / 4
    _, pvalue, _ = coint(df_daily['close_x'], df_daily['close_y'])
    intraday_spread, intraday_moves = compute_spread_move(df_intraday, mode="intraday")
    daily_spread, daily_moves = compute_spread_move(df_daily, mode="daily")

    print(f"{"=" * 10} {symbol1}-{symbol2} {"=" * 10}")
    print("INTRADAY STATS")
    print(f"Intraday Corr: {intraday_corr:.4f}")
    print(f"Average Spread Move: ${intraday_spread:.2f}")
    print()
    print("DAILY STATS")
    print(f"Daily Corr: {daily_corr:.4f}")
    print(f"Average Spread Move: ${daily_spread:.2f}")

    return {
        "intraday_corr": intraday_corr,
        "daily_corr": daily_corr,
        "coint_pvalue": pvalue,
        "intraday_spread": intraday_spread,
        "daily_spread": daily_spread,
    }

def find_pair_stats_combos(symbols):
    pair_corrs = []
    for x, y in combinations(symbols, 2):
        stats = find_pair_stats(x, y)
        pair_corrs.append({
            "symbol1": x,
            "symbol2": y,
            "intraday_corr": stats["intraday_corr"],
            "daily_corr": stats["daily_corr"],
            "coint_pvalue": stats["coint_pvalue"],
            "intraday_spread": stats["intraday_spread"],
            "daily_spread": stats["daily_spread"],
        })

    with open("pair_stats.json", "w") as f:
        json.dump(pair_corrs, f, indent=4)

def top_pairs(top_n=20, stat="intraday_corr"):
    with open("pair_stats.json", "r") as f:
        pair_stats = json.load(f)
    pairs = sorted(pair_stats, key=lambda x: x[stat], reverse=True)[:top_n]
    for i, pair in enumerate(pairs, 1):
        print(f"{"=" * 10} {pair["symbol1"]}-{pair["symbol2"]} {"=" * 10}")
        print(f"{i}. {stat}: {pair[stat]:.4f}")

def exchange_latency(file_path="market_logs/market_logs_2026-03-19.jsonl"):
    with open(file_path) as f:
        trade_history = [json.loads(line) for line in f]

    latencies = {}

    for packet in trade_history:
        receive_time = int(packet[0])

        for quote in packet:
            match = re.search(r"\[(\w+)\].*timestamp=(\d+)", quote)
            if match:
                symbol, ts = match.group(1), int(match.group(2))

                if symbol not in latencies:
                    latencies[symbol] = []

                latency_ms = receive_time - ts
                latencies[symbol].append(latency_ms)

    for symbol, times in latencies.items():
        print(f"{'='*10} {symbol} {'='*10}")
        if times:
            print(f"{'Packets received:':25} {len(times)}")
            print(f"{'Min latency:':25} {min(times)} ms")
            print(f"{'5th percentile latency:':25} {np.percentile(times, 5):.0f} ms")
            print(f"{'Average latency:':25} {np.mean(times):.0f} ms")
            print(f"{'95th percentile latency:':25} {np.percentile(times, 95):.0f} ms")
            print(f"{'Max latency:':25} {max(times)} ms")
        else:
            print(f"No data for {symbol}")

def check_packet_sync(symbol1, symbol2, log_file="market_logs/market_logs_2026-03-02.jsonl"):
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

    print(f"{"=" * 10} {symbol1}-{symbol2} {"=" * 10}")
    print(f"Synced packets: {synced_packets} ({synced_packets / total_packets:.2%})")
    print(f"Unsynced packets: {unsynced_packets} ({unsynced_packets / total_packets:.2%})")
    print(f"Average difference: {np.mean(time_diffs):.0f} ms")
    print(f"5th percentile latency: {np.percentile(time_diffs, 5):.0f} ms")
    print(f"Min difference: {min(time_diffs)} ms")
    print(f"95th percentile latency: {np.percentile(time_diffs, 95):.0f} ms")
    print(f"Max difference: {max(time_diffs)} ms") 

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

    print(f"{"=" * 10} {symbol1}-{symbol2} {"=" * 10}")
    print(f"Mean Latency: {latency_ms.mean():.0f} ms")
    print(f"95th percentile latency: {latency_ms.quantile(0.95):.0f} ms")

    plt.figure(figsize=(10, 5))
    plt.hist(latency_ms, bins=30, edgecolor="black")
    plt.title(f"Latency Distribution ({symbol1} vs {symbol2})")
    plt.xlabel("Milliseconds")
    plt.ylabel("Count")
    plt.show()
    
def sync_and_latency_test(file="trade_logs/trade_logs_live_pt.json"):
    with open(file) as f:
        trade_history = json.load(f)["trade_history"]

    latency = []
    time_diffs = []
    pnls = []

    for trade in trade_history:
        time_diffs.append(trade['features']['time_diff'])
        latency.append(trade['features']['latency'])
        pnls.append(trade['pnl_pct'])


    time_diffs = np.array(time_diffs)
    latency = np.array(latency)
    pnls = np.array(pnls) * 100

    time_bins = [0, 500, 1000]
    lat_bins  = [0, 100, 200, 300, 500]

    def stats(x):
        n = len(x)
        if n < 1:
            return None

        mean = x.mean()
        std = x.std()
        sharpe = mean / std if std > 1e-12 else 0

        return mean, std, sharpe, n

    for i in range(len(time_bins) - 1):

        t_low, t_high = time_bins[i], time_bins[i + 1]
        t_mask = (time_diffs >= t_low) & (time_diffs < t_high)

        mean, std, sharpe, n = stats(pnls[t_mask]) or (0, 0, 0, 0)
        if n < 50:
            continue

        print("========================================")
        print(f"T[{t_low}-{t_high}] mean={mean:.4f}, std={std:.4f}, sharpe={sharpe:.4f}, n={n}")
        print("========================================")

        for j in range(len(lat_bins) - 1):
            l_low, l_high = lat_bins[j], lat_bins[j + 1]
            x = pnls[t_mask & (latency >= l_low) & (latency < l_high)]

            m = stats(x)
            if not m or m[3] < 50:
                continue

            mean, std, sharpe, n = m

            print(f"  L[{l_low}-{l_high}]")
            print(f"    mean={mean:.4f}, std={std:.4f}, sharpe={sharpe:.4f}, n={n}")

def visualize_bid_ask_spread(symbol):
    try:
        df = open_data(symbol, mode="quote")
    except FileNotFoundError:
        return

    spread = (df["ask"] - df["bid"]).round(10)

    print(f"{"=" * 10} {symbol} {"=" * 10}")
    print(f"Average bid-ask spread: {spread.mean():.4f}")
    print(f"Min bid-ask spread: {max(0, min(spread)):.4f}") 
    print(f"Max bid-ask spread: {max(spread):.4f}")   

    lower = spread.quantile(0.001)
    upper = spread.quantile(0.999)
    spread = spread[(spread >= lower) & (spread <= upper)]

    plt.figure(figsize=(10, 5))
    plt.hist(spread, bins=30, edgecolor='black')
    plt.title(f"{symbol} Bid-Ask Spread Distribution")
    plt.xlabel("Bid-Ask Spread")
    plt.ylabel("Count")
    plt.show()

def visualize_spread(symbol1, symbol2, window=1000, z=2):
    with open(f"{symbol1}-{symbol2}_spread.json", "r") as f:
        spread = json.load(f)
    with open("trade_logs/trade_logs.json") as f:
        trade_history = json.load(f)["trade_history"]
    
    spread = pd.Series(spread)
    spread.index = pd.to_datetime(spread.index.astype(int), unit='ms', utc=True).tz_convert(timezone)

    roll_mean = spread.shift().rolling(window).mean()
    roll_std = spread.shift().rolling(window).std()
    upper_band = roll_mean + z * roll_std
    lower_band = roll_mean - z * roll_std
    
    plt.figure(figsize=(10, 5))
    plt.plot(spread, label="Spread")
    plt.plot(roll_mean, linestyle="--", label="Mean", color="gray")
    plt.plot(upper_band, linestyle="--", label=f"+{z} Std", color="lightgray")
    plt.plot(lower_band, linestyle="--", label=f"-{z} Std", color="lightgray")

    for trade in trade_history:
        if trade["symbol"] not in (symbol1, symbol2):
            continue
        entry_time = pd.to_datetime(trade["entry_time"], utc=True).tz_convert(timezone)
        exit_time = pd.to_datetime(trade["exit_time"], utc=True).tz_convert(timezone)
        entry_idx = spread.index.get_indexer([entry_time], method="nearest")[0]
        exit_idx = spread.index.get_indexer([exit_time], method="nearest")[0]

        entry_val = spread.iloc[entry_idx]
        exit_val = spread.iloc[exit_idx]
        entry_mean = roll_mean.iloc[entry_idx]
        slope = exit_val - entry_val

        if entry_val > entry_mean:
            color = "green" if slope < 0 else "red"
        else:
            color = "green" if slope > 0 else "red"

        plt.plot(
            spread.index[[entry_idx, exit_idx]],
            spread.iloc[[entry_idx, exit_idx]],
            color=color,
            linewidth=2,
            alpha=0.8
        )

    plt.legend()
    plt.gcf().autofmt_xdate()
    plt.show()
    
# test_order("AAPL")
# acc_latency()
# find_num_orders(file="trade_logs/trade_logs_live_pt.json")

# compute_share_split(580.93, 24.92, min_pct=0.85, cash=1200, top_n=5)
# dca_plan(687.12, 602.37, min_pct=0.85, cash=30000)

# for pair in pairs:
#     symbol1, symbol2 = pair[0], pair[1]
#     find_pair_stats(symbol1, symbol2)
# find_pair_stats("SPY", "QQQ", start="2026-03-16", end="2026-03-27")
# find_pair_stats_combos(["VOO", "SCHX", "VTI", "VXUS", "ITOT", "IXUS", "VT", "TLT"])
# top_pairs(top_n=20, stat="intraday_spread")

# exchange_latency()
# check_packet_sync("SPY", "QQQ", log_file="market_logs/market_logs_2026-03-06.jsonl")
# visualize_latency("XLV", "XBI")
# sync_and_latency_test(file="trade_logs/trade_logs_live_pt.json")

# visualize_bid_ask_spread("VTI")
visualize_spread("SPY", "QQQ")






# df = open_data("SPY", mode="quote")
# df['date'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert(timezone) 
# mask = (df['date'].dt.date >= pd.to_datetime("2026-02-25").date()) & \
#         (df['date'].dt.date <= pd.to_datetime("2026-03-08").date())
# df_old = df.loc[~mask].copy().drop(columns=['date'])
# df_fix = df.loc[mask].copy().drop(columns=['date'])

# df_fix.loc[:, 'timestamp'] = df['timestamp'] - 3600000

# print(df)
# print(df_old)
# print(df_fix)

# df_new = pd.concat([df_old, df_fix]).sort_index()
# print(df_new)
# # df_new['timestamp'] = pd.to_datetime(df_new['timestamp'], unit='ms', utc=True)
# # print(df_new)

# save_data(df_new, "SPY", mode="quote")