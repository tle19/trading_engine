import time
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from zoneinfo import ZoneInfo
import schwabdev

from core import *
from strategies import *
from metrics import *
from utils import *

timezone = ZoneInfo("America/New_York")

def test_order(symbol="AAPL"):
    eq = Equities(symbol, SMACrossover)

    entry_id, _ = eq.buy_market(symbol, 1, "BUY")
    exit_id = eq.long_bracket(symbol, 1, 333.0, 333.5)
    time.sleep(20)
    fill_price = eq.get_fill_price(exit_id, timeout=0.1)
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

with open("trade_logs_live_pt.json") as f:
    trade_history = json.load(f)["trade_history"]

trade_history = trade_history[200:]
pair_sums = []
pair_times = []

for i in range(0, len(trade_history), 2):
    idx1 = i
    idx2 = i + 1
    if idx2 < len(trade_history):
        pair_sums.append(trade_history[idx1]["pnl_pct"] + trade_history[idx2]["pnl_pct"])

        t1 = trade_history[idx1]["exit_time"]
        t2 = trade_history[idx2]["exit_time"]
        t1_dt = datetime.fromtimestamp(t1 / 1000, tz=timezone)
        t2_dt = datetime.fromtimestamp(t2 / 1000, tz=timezone)

        pair_times.append(max(t1_dt, t2_dt))

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