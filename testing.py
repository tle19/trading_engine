import time
import numpy as np
import re
from collections import defaultdict
from datetime import datetime
import matplotlib.pyplot as plt
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

def pairs_pnl(symbol1, symbol2):
    with open("trade_logs_live_pt.json") as f:
        trade_history = json.load(f)["trade_history"]

    trade_history = trade_history[0:]
    pair_sums = []
    pair_times = []
    def z_bucket(z):
        return round(z * 2) / 2.0
    pair_zscores = []
    th = []
    for trade in trade_history.copy():
        if trade["symbol"] == symbol1 or trade["symbol"] == symbol1:
            th.append(trade)
    for i in range(0, len(th), 2):
        idx1 = i
        idx2 = i + 1
        if idx2 < len(th):
            pair_sums.append(th[idx1]["pnl_pct"] + th[idx2]["pnl_pct"])

            t1 = th[idx1]["exit_time"]
            t2 = th[idx2]["exit_time"]
            t1_dt = datetime.fromtimestamp(t1 / 1000, tz=timezone)
            t2_dt = datetime.fromtimestamp(t2 / 1000, tz=timezone)

            pair_times.append(max(t1_dt, t2_dt))

            z = th[idx1]["features"][0]
            pair_zscores.append(z_bucket(z))

    pnl_by_z = defaultdict(list)

    for pnl, z in zip(pair_sums, pair_zscores):
        pnl_by_z[z].append(pnl)

    for z in sorted(pnl_by_z.keys()):
        arr = pnl_by_z[z]
        print(
            f"Z bucket = {z:+.1f} | count = {len(arr)} | mean pnl = {sum(arr)/len(arr):.10f}"
        )

    plt.figure(figsize=(12, 5))
    plt.plot(pair_times, np.cumsum(pair_sums), color='blue', linewidth=2, label="Cumulative PnL")

    plt.xlabel("Exit Time")
    plt.ylabel("PnL %")
    plt.title("Pair-Summed PnLs and Cumulative PnL Over Time")
    plt.legend()
    plt.grid(True)

    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S', tz=timezone))
    plt.gcf().autofmt_xdate()
    plt.show()

pairs_pnl()