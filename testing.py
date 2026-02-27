import time
import numpy as np
from collections import defaultdict
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.dates as mdates

from zoneinfo import ZoneInfo
import schwabdev

from symbols import SYMBOLS
from core import *
from metrics import *
from strategies import *
from models import *
from utils import *

timezone = ZoneInfo("America/New_York")
symbols = SYMBOLS

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

def find_new_day_indices():
    with open("trade_logs_live_pt.json") as f:
        trade_history = json.load(f)["trade_history"]

    new_day_indices = [0]
    prev_day = None

    for i, trade in enumerate(trade_history):
        ts = datetime.fromtimestamp(trade["entry_time"] / 1000, tz=timezone)
        current_day = ts.date()

        if prev_day is None:
            prev_day = current_day
            continue
        if current_day != prev_day:
            new_day_indices.append(i)

        prev_day = current_day

    print("New day starts at indices:", new_day_indices)

def pairs_pnl(symbol1, symbol2, start=0, end=None):
    with open("trade_logs_live_pt.json") as f:
        trade_history = json.load(f)["trade_history"]
    
    trade_history = trade_history[start:end]
    pair_sums = []
    pair_times = []
    hold_times = []
    latencies = []
    fill_diffs = []

    def z_bucket(z):
        return round(z * 2) / 2.0
    
    pair_zscores = []
    th = []
    for trade in trade_history.copy():
        if trade["symbol"] == symbol1 or trade["symbol"] == symbol2:
            th.append(trade)

    buy_slopes = []
    sell_slopes = []

    for i in range(0, len(th), 2):
        idx1 = i
        idx2 = i + 1
        if idx2 < len(th):
            net_pnl = th[idx1]["pnl_pct"] + th[idx2]["pnl_pct"]
            pair_sums.append(net_pnl)

            entry_time1 = datetime.fromtimestamp(th[idx1]["entry_time"] / 1000, tz=timezone)
            entry_time2 = datetime.fromtimestamp(th[idx2]["entry_time"] / 1000, tz=timezone)
            exit_time1 = datetime.fromtimestamp(th[idx1]["exit_time"] / 1000, tz=timezone)
            exit_time2 = datetime.fromtimestamp(th[idx2]["exit_time"] / 1000, tz=timezone)

            entry_time = max(entry_time1, entry_time2)
            exit_time = max(exit_time1, exit_time2)
            pair_times.append(entry_time)
            hold_times.append((exit_time - entry_time).total_seconds())

            entry_latency = th[idx1]["features"][2] + th[idx1]["features"][3]
            fill_1 = abs(th[idx1]["entry_price"] - th[idx1]["entry_fill"])
            fill_2 = abs(th[idx2]["entry_price"] - th[idx2]["entry_fill"])
            latencies.append(entry_latency)
            fill_diffs.append(fill_1 + fill_2)

            z = th[idx1]["features"][0]
            pair_zscores.append(z_bucket(z))

            dir = th[idx1]["direction"]
            slope_sum = th[idx1]["features"][1]
            if dir == 1:
                buy_slopes.append([slope_sum, net_pnl])
            elif dir == -1:
                sell_slopes.append([slope_sum, net_pnl])

    pnl_by_z = defaultdict(list)

    for pnl, z in zip(pair_sums, pair_zscores):
        pnl_by_z[z].append(pnl)

    for z in sorted(pnl_by_z.keys()):
        arr = pnl_by_z[z]
        print(
            f"Z bucket = {z:+.1f} | count = {len(arr)} | mean pnl = {sum(arr)/len(arr):.10f}"
        )

    cum = np.cumsum(pair_sums)
    cum = cum - cum[0]

    plt.figure(figsize=(14,8))

    plt.subplot(1,2,1)
    plt.plot(pair_times, cum, color='blue', linewidth=2, label="Cumulative PnL")
    plt.xlabel("Exit Time")
    plt.ylabel("PnL %")
    plt.title("Pair-Summed PnLs and Cumulative PnL Over Time")
    plt.legend()
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S', tz=timezone))
    plt.gcf().autofmt_xdate()

    plt.subplot(1,2,2)
    plt.hist(hold_times, bins=50, weights=cum, color='blue', edgecolor='black', label="Cumulative PnL")
    # plt.hist(latencies, bins=50, weights=cum, color='blue', edgecolor='black', label="Cumulative PnL")
    plt.xlabel("Hold Times")
    plt.ylabel("Cumulative PnL")
    plt.title("Histogram of Hold Times Weighted by Cumulative PnL")
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.show()

    plt.hist(latencies, bins=50, weights=fill_diffs, color='blue', edgecolor='black', label="Cumulative PnL")
    # plt.hist(latencies, bins=50, weights=cum, color='blue', edgecolor='black', label="Cumulative PnL")
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.show()

    buy_values, buy_pnl = zip(*buy_slopes) if buy_slopes else ([], [])
    sell_values, sell_pnl = zip(*sell_slopes) if sell_slopes else ([], [])

    buy_values = np.array(buy_values)
    buy_pnl = np.array(buy_pnl)
    sell_values = np.array(sell_values)
    sell_pnl = np.array(sell_pnl)

    clip_low, clip_high = 0.05, 0.95  # keep 5%-95% percentile
    all_values = np.concatenate([buy_values, sell_values])
    vmin, vmax = np.percentile(all_values, [clip_low*100, clip_high*100])

    buy_values_clipped = np.clip(buy_values, vmin, vmax)
    sell_values_clipped = np.clip(sell_values, vmin, vmax)

    bins = np.linspace(vmin, vmax, 50)

    plt.figure(figsize=(14,6))

    plt.subplot(1,2,1)
    plt.hist(
        buy_values_clipped, 
        bins=bins, 
        weights=buy_pnl, 
        alpha=0.7, 
        color='green', 
        edgecolor='black', 
        histtype='stepfilled'
    )
    plt.axvline(0, color='black', linestyle='--')
    plt.title("Buy Spread (-2σ) Slope Sum Weighted by PnL")
    plt.xlabel("Slope Sum (A-B) at Entry")
    plt.ylabel("Weighted PnL")
    plt.grid(True)

    plt.subplot(1,2,2)
    plt.hist(
        sell_values_clipped, 
        bins=bins, 
        weights=sell_pnl, 
        alpha=0.7, 
        color='red', 
        edgecolor='black', 
        histtype='stepfilled'
    )
    plt.axvline(0, color='black', linestyle='--')
    plt.title("Sell Spread (+2σ) Slope Sum Weighted by PnL")
    plt.xlabel("Slope Sum (A-B) at Entry")
    plt.ylabel("Weighted PnL")
    plt.grid(True)

    plt.tight_layout()
    plt.show()

find_new_day_indices()

pairs_pnl("SPY", "QQQ", start=330, end=None) # -2std, A - B > 0 yes; +2std, A - B < 0 yes