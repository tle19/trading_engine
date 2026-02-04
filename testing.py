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

# import sys
# import time

# log_buffer = ["Line " + str(i) for i in range(10)]  # example buffer

# # --- Approach 1: append to list, write at end ---
# start = time.time()
# sys.stdout.write("\n".join(log_buffer) + "\n")
# end = time.time()
# print(f"Buffer + sys.stdout.write() time: {(end - start) * 1000:.6f} ms")

# # --- Approach 2: direct print in a loop ---
# start = time.time()
# for line in log_buffer:
#     print(line)
# end = time.time()
# print(f"Direct print() loop time: {(end - start) * 1000:.6f} ms")


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