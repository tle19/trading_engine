import time
import json
from itertools import product
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from core import *
from strategies import *
from utils import *

def fetch_multiple_symbols(symbols):
    dh = DataHandler()
    for symbol in symbols:
        start_time = time.perf_counter()

        dh.historical_data(symbol)

        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        print(f"Elapsed Data Fetch Time: {elapsed_time:.6f} seconds")

def fetch_schwab_data(symbol, current_date):
    dh = DataHandler()
    dh.schwab_data(symbol, end_date=(datetime.fromisoformat(current_date) - timedelta(days=1)).date().isoformat())

def test_order(symbol):
    eq = Equities(symbol, SMACrossoverIndicator(symbol))
    entry_response = eq.buy_market(1)
    hold_response = eq.long_bracket(1, 250, 254)
    time.sleep(5)
    eq.replace_order("long", 1, 251, 253, hold_response)

def get_average_spread(symbols, start_date="2023-10-02", end_date="2024-10-02"):
    for symbol in symbols:
        data = open_data(symbol, start_date=start_date, end_date=end_date)
        data["spread"] = data["high"] - data["low"]
        data["normalized_spread"] = data["spread"] / data["close"]
        avg_spread = data["normalized_spread"].mean()
        print(symbol, avg_spread)

symbols = ["SPY", "QQQ", 
           "AAPL", "MSFT", 
           "NVDA", "AMD", 
           "AMZN", "GOOG", 
           "META", "TSLA"]
symbols = [
    "IONQ", "FSLY", "SANA", "DNA", "CRSP", "EDIT",
    "NKLA", "CVNA", "CHPT", "RIVN", "FUBO", "GME",
    "AMC", "SPWR",
]
curr_symbol = symbols[2]

fetch_multiple_symbols(symbols)
# fetch_schwab_data("2025-10-15") 
# get_average_spread(symbols, start_date="2025-7-01", end_date="2025-10-01")
# test_order(symbol)