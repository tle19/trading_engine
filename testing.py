import time
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

price1 = 689
price2 = 525
total_cash = 50000

# -------- NORMAL CASH SPLIT (50/50) --------
s = time.perf_counter()
cash_split1 = (total_cash / 2) // price1
cash_split2 = (total_cash / 2) // price2
elapsed = (time.perf_counter() - s) * 1000

cash1_norm = cash_split1 * price1
cash2_norm = cash_split2 * price2
diff_norm = abs(cash1_norm - cash2_norm)

print("=== Normal 50/50 Cash Split ===")
print(f"Symbol1: {int(cash_split1)} (${cash1_norm}) | "
      f"Symbol2: {int(cash_split2)} (${cash2_norm}) | "
      f"Difference = ${diff_norm}")
print(f"ELAPSED TIME: {elapsed:.3f} ms\n")

# -------- OPTIMIZED DOLLAR NEUTRAL SEARCH --------
s = time.perf_counter()

best_combo = None
best_diff = float('inf')

max_s1 = int((total_cash / 2) // price1)
max_s2 = int((total_cash / 2) // price2)
min_s1 = int(max_s1 * 0.85)
min_s2 = int(max_s2 * 0.85)

for s1 in range(min_s1, max_s1 + 1):
    cash1 = s1 * price1
    for s2 in range(min_s2, max_s2 + 1):
        cash2 = s2 * price2
        diff = abs(cash1 - cash2)
        if diff < best_diff:
            best_diff = diff
            best_combo = (s1, s2, cash1, cash2, diff)

elapsed = (time.perf_counter() - s) * 1000

s1, s2, cash1, cash2, diff = best_combo
print("=== Top Dollar-Neutral Combination (≥85% per symbol) ===")
print(f"Symbol1: {s1:2d} (${cash1:6.0f}) | "
      f"Symbol2: {s2:2d} (${cash2:6.0f}) | "
      f"Difference: ${diff}")
print(f"ELAPSED TIME: {elapsed:.3f} ms\n")