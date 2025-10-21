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

def get_average_spread(symbols, start_date="2023-10-02", end_date="2024-10-02"):
    for symbol in symbols:
        data = open_data(symbol, start_date=start_date, end_date=end_date)
        data["spread"] = data["high"] - data["low"]
        data["normalized_spread"] = data["spread"] / data["close"]
        avg_spread = data["normalized_spread"].mean()
        print(symbol, avg_spread)

def run_one_backtest(symbol, start_date, end_date, fast_window=10, slow_window=20, htf_window=40, donch_smoothing=0.3, 
                     stop_loss=0.005, take_profit=0.005, trailing_ratio=0.05, position_size=1.0, plot=True):
    start_time = time.perf_counter()

    strat = SMACrossoverIndicator(
        symbol, 
        fast_window=fast_window, 
        slow_window=slow_window, 
        htf_window=htf_window, 
        donch_smoothing=donch_smoothing,
        stop_loss=stop_loss, 
        take_profit=take_profit, 
        trailing_ratio=trailing_ratio,
        position_size=position_size)
    
    bt = Backtest(
        symbol, 
        strat, 
        cash=25_000, 
        shares=30, 
        margin=1.0, 
        commission=0.0, 
        slippage=0.1)
    
    bt.run(start_date=start_date, end_date=end_date, plot=plot)

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Elapsed Backtest Time: {elapsed_time:.6f} seconds")

    return bt.get_stats_class()

def walk_forward_optimize(symbol):
    start = pd.Timestamp("2023-10-01")
    end = pd.Timestamp("2025-10-01")

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

def grid_search(symbol, start_date="2023-10-01", end_date="2024-10-01"):
    best_params = optimize_params(symbol, start_date, end_date)
    print(best_params)
    
def optimize_params(symbol, start, end):
    start_time = time.perf_counter()

    param_grid = { # medium frequency (6-10 trades per day)
        "fast_window": [10, 15, 20, 25],
        "slow_window": [20, 25, 30, 35, 40],
        "htf_window": [40, 50, 60, 70, 80],
        "donch_smoothing": [0.1],
        "stop_loss": [0.003],
        "take_profit": [0.003],
        "trailing_ratio": [0.05],
        "position_size": [1.0]
    }

    # param_grid = {
    #     "fast_window": [10],
    #     "slow_window": [20],
    #     "htf_window": [50],
    #     "donch_smoothing": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    #     "stop_loss": [0.003],
    #     "take_profit": [0.003],
    #     "trailing_ratio": [0.05],
    #     "position_size": [1.0]
    # }

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
    eq = Equities(symbol, SMACrossoverIndicator(symbol))
    entry_response = eq.buy_market(1)
    hold_response = eq.long_bracket(1, 0.001, 0.001, entry_response)
    time.sleep(5)
    eq.position = "long"
    eq.replace_order(1, 0.002, 0.002, entry_response, hold_response)

def multiple_symbol_performance(symbols):
    ticker_pnls = []
    for symbol in symbols:
        stats = run_one_backtest(
            symbol, 
            start_date="2023-10-01", 
            end_date="2024-10-01", 
            fast_window=10, 
            slow_window=20, 
            htf_window=50, 
            donch_smoothing=0.1,
            stop_loss=0.003, 
            take_profit=0.003, 
            trailing_ratio=0.05,
            position_size=1.0,
            plot=False)
        ticker_pnls.append(stats.daily_pnls)
    
    min_len = min(len(p) for p in ticker_pnls)
    ticker_truncated = [p[:min_len] for p in ticker_pnls]

    ticker_sums = np.sum(np.array(ticker_truncated), axis=0)
    
    num_wins = np.sum(ticker_sums > 0)
    total_days = len(ticker_sums)
    win_rate = num_wins / total_days * 100

    print(f"Lengths after truncation: {[len(p) for p in ticker_truncated]}")
    print("Ticker sums:", ticker_sums)
    print(f"Daily Win rate: {win_rate:.2f}%")

symbols = ["SPY", "QQQ", 
           "TSLA", "NVDA", 
           "AMD", "AMZN", 
           "AAPL", "GOOG", 
           "MSFT", "META", 
           "TSM", "CSCO", 
           "INTC", "ADBE"]
curr_symbol = symbols[2]

# fetch_multiple_symbols(symbols)
# fetch_schwab_data("2025-10-15") 
# get_average_spread(symbols, start_date="2025-7-01", end_date="2025-10-01")

# run_one_backtest(
#     curr_symbol, 
#     start_date="2023-10-01", 
#     end_date="2024-10-01", 
#     fast_window=20, 
#     slow_window=40, 
#     htf_window=80, 
#     donch_smoothing=0.0,
#     stop_loss=0.03, 
#     take_profit=0.03, 
#     trailing_ratio=0.05,
#     position_size=1.0)

# multiple_symbol_performance(symbols[2:])

# grid_search(curr_symbol, start_date="2023-10-01", end_date="2024-10-01")

walk_forward_optimize(curr_symbol)

# test_order(curr_symbol)    