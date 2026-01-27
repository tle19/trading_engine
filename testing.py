from collections import namedtuple

from core import *
from strategies import *
from metrics import *
from utils import *

timezone = ZoneInfo("America/New_York")

symbols = ["GOOG", "GOOGL"]

def test_order(symbol="AAPL"):
    eq = Equities(symbol, SMACrossover)

    entry_id, _ = eq.buy_market(symbol, 1, "BUY")
    exit_id = eq.long_bracket(symbol, 1, 333.0, 333.5)
    time.sleep(20)
    fill_price = eq.get_fill_price(exit_id, timeout=0.1)
    print(fill_price)

def get_positions():
    response = pt.client.account_details(pt.hash, fields="positions")
    data = response.json()
    positions = data.get('securitiesAccount', {}).get('positions', [])
    return positions

pt = Pairs(["GOOG", "GOOGL"], SMACrossover)

def buy_pair(shares=100):
    positions = get_positions()
    if not positions:
        pt.buy_market("GOOG", shares, type="BUY")
        pt.sell_market("GOOGL", shares, type="SELL_SHORT")
    else:
        pt.buy_market("GOOG", shares, type="BUY_TO_COVER")
        pt.sell_market("GOOGL", shares, type="SELL")

def sell_pair(shares=100):
    positions = get_positions()
    if not positions:
        pt.sell_market("GOOG", shares, type="SELL_SHORT")
        pt.buy_market("GOOGL", shares, type="BUY")
    else:
        pt.sell_market("GOOG", shares, type="SELL")
        pt.buy_market("GOOGL", shares, type="BUY_TO_COVER")
