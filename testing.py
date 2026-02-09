import time
import matplotlib.pyplot as plt
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

pair_sums = []
for i in range(0, len(trade_history), 2):
    if i + 1 < len(trade_history):
        pair_sums.append(
            trade_history[i]["pnl_pct"] + trade_history[i+1]["pnl_pct"]
        )

plt.figure(figsize=(10, 4))
plt.plot(range(len(pair_sums)), pair_sums)
plt.xlabel("Pair index (chronological)")
plt.ylabel("PnL % (pair sum)")
plt.title("Chronological Pair-Summed PnLs")
plt.grid(True)
plt.show()