from collections import namedtuple

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

from collections import namedtuple
from dataclasses import dataclass
import timeit

RowNT = namedtuple("RowNT", ["ts","bid","ask","last","bid_size","ask_size"])

# Dataclass with slots
@dataclass(slots=True)
class RowSlots:
    ts: int = None
    bid: float = None
    ask: float = None
    last: float = None
    bid_size: int = None
    ask_size: int = None

# Dict-based Row
def make_dict_row(ts, bid, ask, last, bid_size, ask_size):
    return {
        "ts": ts,
        "bid": bid,
        "ask": ask,
        "last": last,
        "bid_size": bid_size,
        "ask_size": ask_size
    }

# -------------------------------
# Benchmark function: create Row and read attributes into locals
def bench_namedtuple():
    row = RowNT(1,2,3,4,5,6)
    ts = row.ts
    bid = row.bid
    ask = row.ask
    last = row.last
    bs = row.bid_size
    ask_s = row.ask_size
    return ts + bid + ask + last + bs + ask_s

def bench_slots():
    row = RowSlots(1,2,3,4,5,6)
    ts = row.ts
    bid = row.bid
    ask = row.ask
    last = row.last
    bs = row.bid_size
    ask_s = row.ask_size
    return ts + bid + ask + last + bs + ask_s

def bench_dict():
    row = make_dict_row(1,2,3,4,5,6)
    ts = row["ts"]
    bid = row["bid"]
    ask = row["ask"]
    last = row["last"]
    bs = row["bid_size"]
    ask_s = row["ask_size"]
    return ts + bid + ask + last + bs + ask_s

# -------------------------------
# Run benchmarks
iterations = 10_000_000
nt_time = timeit.timeit("bench_namedtuple()", globals=globals(), number=iterations)
slots_time = timeit.timeit("bench_slots()", globals=globals(), number=iterations)
dict_time = timeit.timeit("bench_dict()", globals=globals(), number=iterations)

print(f"Namedtuple: {nt_time:.6f} s")
print(f"Dataclass(slots=True): {slots_time:.6f} s")
print(f"Dict: {dict_time:.6f} s")