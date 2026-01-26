from core import *
from strategies import *
from metrics import *
from utils import *

timezone = ZoneInfo("America/New_York")

symbols = ["GOOG", "GOOGL"]

def test_order(symbol="AAPL"):
    eq = Equities(symbol, StochasticIndicator)
    symbol = symbol[0]

    entry_id, _ = eq.buy_market(symbol, 1, "BUY")
    exit_id = eq.long_bracket(symbol, 1, 333.0, 333.5)
    time.sleep(20)
    fill_price = eq.get_fill_price(exit_id, timeout=0.1)
    print(fill_price)


pt = Pairs(["GOOG", "GOOGL"], StochasticIndicator)
# pt.run()

def enter():
    pt.buy_market("GOOG", 1, type="BUY")
    pt.sell_market("GOOGL", 1, type="SELL_SHORT")

def exit():
    pt.sell_market("GOOG", 1, type="SELL")
    pt.buy_market("GOOGL", 1, type="BUY_TO_COVER")

