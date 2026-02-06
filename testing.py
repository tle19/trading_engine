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

# config = load_config()
# client = schwabdev.Client(config['app_key'], config['app_secret'])
# hash = client.linked_accounts().json()[0].get('hashValue')

# start = time.perf_counter()
# details = client.account_details(hash)
# details_json = details.json()
# cash_balance = details_json["securitiesAccount"]["currentBalances"]["cashBalance"]
# end = time.perf_counter()
# print(f"Execution time: {end - start:.6f} seconds")
# print(cash_balance)

spy_price = 689
qqq_price = 608
total_cash = 50000

results = []

# Maximum shares possible for each
max_spy = total_cash // spy_price
max_qqq = total_cash // qqq_price

for s1 in range(max_spy + 1):
    for s2 in range(max_qqq + 1):
        cash1 = s1 * spy_price
        cash2 = s2 * qqq_price
        if cash1 + cash2 > total_cash:
            continue
        diff = abs(cash1 - cash2)
        results.append((s1, s2, cash1, cash2, diff))

# Sort by smallest difference first
results.sort(key=lambda x: x[4])

# Display top 10 combinations closest to dollar-neutral
print("Top 10 combinations closest to dollar-neutrality:")
for r in results[:10]:
    print(f"SPY: {r[0]} (${r[2]:.2f}), QQQ: {r[1]} (${r[3]:.2f}), Difference: ${r[4]:.2f}")