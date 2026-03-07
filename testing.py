import time
from datetime import datetime

from zoneinfo import ZoneInfo
import schwabdev

from symbols import SYMBOLS, PAIRS
from core import Equities
from strategies import SMACrossover
from utils import *

timezone = ZoneInfo("America/New_York")
symbols = SYMBOLS
pairs = PAIRS

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