import time
import json
from itertools import product
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

def get_average_spread(symbols, start_date="2023-10-02", end_date="2024-10-02"):
    for symbol in symbols:
        data = open_data(symbol, start_date=start_date, end_date=end_date)
        data["spread"] = data["high"] - data["low"]
        data["normalized_spread"] = data["spread"] / data["close"]
        avg_spread = data["normalized_spread"].mean()
        print(symbol, avg_spread)

def run_one_backtest(symbol, start_date, end_date, fast_window=10, slow_window=20, htf_window=40, position_size=1.0, stop_loss=0.005, take_profit=0.0075, trailing_ratio=0.15, plot=True):
    start_time = time.perf_counter()

    strat = SMACrossoverIndicator(
        symbol, 
        fast_window=fast_window, 
        slow_window=slow_window, 
        htf_window=htf_window, 
        position_size=position_size, 
        stop_loss=stop_loss, 
        take_profit=take_profit, 
        trailing_ratio=trailing_ratio)
    
    bt = Backtest(
        symbol, 
        strat, 
        cash=25_000, 
        shares=30, 
        margin=1.0, 
        commission=0.0, 
        slippage=0.0003)
    
    bt.run(start_date=start_date, end_date=end_date, plot=plot)

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Elapsed Backtest Time: {elapsed_time:.6f} seconds")

    return bt.get_stats_class()

def walk_forward_optimize(symbol):
    start = pd.Timestamp("2023-10-02")
    end = pd.Timestamp("2025-10-02")

    train_months = 6
    test_months = 3
    step_months = 3

    results = []
    current_start = start

    while True:
        train_start = current_start
        train_end = train_start + pd.DateOffset(months=train_months)
        test_end = train_end + pd.DateOffset(months=test_months)
        
        if test_end > end:
            break

        print(f"Training: {train_start.date()} → {train_end.date()} | Testing: {train_end.date()} → {test_end.date()}")

        best_params = optimize_params(
            symbol, 
            train_start.strftime("%Y-%m-%d"), 
            train_end.strftime("%Y-%m-%d"))

        perf = run_one_backtest(
            symbol, 
            train_end.strftime("%Y-%m-%d"), 
            test_end.strftime("%Y-%m-%d"), 
            **best_params,
            plot=False)
        
        perf_dict = perf.get_data_dict()

        fold_result = {
            "train_start": train_start.strftime("%Y-%m-%d"),
            "train_end": train_end.strftime("%Y-%m-%d"),
            "test_start": train_end.strftime("%Y-%m-%d"),
            "test_end": test_end.strftime("%Y-%m-%d"),
            "params": best_params,
            "perf": perf_dict
        }

        results.append(fold_result)
        current_start += pd.DateOffset(months=step_months)
        print()

    with open("wfo_results.json", "w") as f:
        json.dump(results, f, indent=4)
    print(f"Saved WFO results to wfo_results.json")
    
    return results

def grid_search(symbol, start_date="2023-10-02", end_date="2024-10-02"):
    best_params = optimize_params(symbol, start_date, end_date)
    print(best_params)
    
def optimize_params(symbol, start, end):
    start_time = time.perf_counter()

    param_grid = { #bullish params
        "fast_window": [5, 10, 15],
        "slow_window": [15, 20, 30, 40],
        "htf_window": [40, 50, 60, 70],
        "position_size": [1.0],
        "stop_loss": [0.005, 0.0075, 0.01, 0.0125],
        "take_profit": [0.01, 0.0125, 0.015, 0.0175],
        "trailing_ratio": [0.075, 0.1, 0.125],
    }

    param_grid = { #bearish params
        "fast_window": [10, 15],
        "slow_window": [20, 30, 40],
        "htf_window": [60, 70, 80],
        "position_size": [1.0],
        "stop_loss": [0.01, 0.0125, 0.015],
        "take_profit": [0.0075, 0.01, 0.0125],
        "trailing_ratio": [0.075, 0.1, 0.125],
    }

    param_grid = { #trailing ratio params
        "fast_window": [10],
        "slow_window": [20],
        "htf_window": [40],
        "position_size": [1.0],
        "stop_loss": [0.005],
        "take_profit": [0.015],
        "trailing_ratio": [0.05, 0.075, 0.1, 0.125, 0.15],
    }

    best_score = -np.inf
    best_params = None
    results = []

    for combo in product(*param_grid.values()):
        params = dict(zip(param_grid.keys(), combo))
        perf = run_one_backtest(symbol, start, end, **params, plot=False)
        perf_dict = perf.get_data_dict()
        pnl = perf_dict["Net Profit"]
        if pnl > best_score:
            best_score = pnl
            best_params = params
        print(params)
        results.append({"params": params, "perf": perf_dict})

    with open("gs_results.json", "w") as f:
        json.dump(results, f, indent=4)

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Elapsed Parameter Optimize Time: {elapsed_time:.6f} seconds")
    
    return best_params

def test_order(symbol):
    eq = Equities(symbol, SMACrossoverIndicator)
    entry_response = eq.sell_market(1)
    hold_response = eq.short_bracket(1, 0.001, 0.001, entry_response)
    time.sleep(5)
    eq.replace_order(1, 0.002, 0.002, entry_response, hold_response, "short")

def test_order_timed(symbol):
    eq = Equities(symbol, SMACrossoverIndicator)

    start_time = time.perf_counter()
    entry_response = eq.sell_market(1)
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Elapsed Order Time: {elapsed_time:.6f} seconds")

    start_time = time.perf_counter()
    hold_response = eq.short_bracket(1, 0.001, 0.001, entry_response)
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Elapsed Order Time: {elapsed_time:.6f} seconds")

    time.sleep(5)
    start_time = time.perf_counter()
    eq.replace_order(1, 0.002, 0.002, entry_response, hold_response, "short")
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Elapsed Order Time: {elapsed_time:.6f} seconds")

# play around with replace_order if succesful
# client.order_replace(account_hash, orderID, order)

symbols = ["SPY", "QQQ", 
           "TSLA", "NVDA", 
           "AMD", "AMZN", 
           "AAPL", "GOOG", 
           "MSFT", "META", 
           "TSM", "CSCO", 
           "INTC", "ADBE"]
curr_symbol = symbols[8]


# fetch_multiple_symbols(symbols)
# get_average_spread(curr_symbol, start_date="2023-10-02", end_date="2025-10-02")

# run_one_backtest(
#     curr_symbol, 
#     start_date="2025-3-01", 
#     end_date="2025-6-01", 
#     fast_window=10, 
#     slow_window=30, 
#     htf_window=80, 
#     position_size=1.0, 
#     stop_loss=0.0125, 
#     take_profit=0.0125, 
#     trailing_ratio=0.1)
run_one_backtest(curr_symbol, start_date="2023-10-01", end_date="2024-10-01")

# grid_search(curr_symbol, start_date="2024-10-01", end_date="2025-10-01")
# walk_forward_optimize(curr_symbol)

# test_order_timed(curr_symbol)    