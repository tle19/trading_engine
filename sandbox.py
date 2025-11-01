import time
import json
from itertools import product
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from core import *
from strategies import *
from utils import *

def run_one_backtest(symbol, strategy_class, start_date, end_date, plot=True, **strategy_kwargs):
    start_time = time.perf_counter()

    strat = strategy_class(symbol, **strategy_kwargs)
    
    bt = Backtest(
        symbol, 
        strat, 
        cash=25_000, 
        shares=50, 
        margin=1.0, 
        commission=0.0, 
        slippage=0.1)
    
    bt.run(start_date=start_date, end_date=end_date, plot=plot)

    elapsed_time = time.perf_counter() - start_time
    print(f"Elapsed Backtest Time: {elapsed_time:.6f} seconds")

    return bt.get_stats_class()

def multiple_symbol_performance(symbols, strategy_class, start_date, end_date, **strategy_kwargs):
    ticker_pnls = []
    for symbol in symbols:
        stats = run_one_backtest(symbol, strategy_class, start_date, end_date, plot=False, **strategy_kwargs)
        ticker_pnls.append(stats.daily_pnls)
    
    min_len = min(len(p) for p in ticker_pnls)
    ticker_truncated = [p[:min_len] for p in ticker_pnls]

    ticker_sums = np.sum(np.array(ticker_truncated), axis=0)
    
    num_wins = np.sum(ticker_sums > 0)
    total_days = len(ticker_sums)
    win_rate = num_wins / total_days * 100

    print(f"Length after truncation: {len(ticker_truncated[0])}")
    print(f"Total Pnl: {np.sum(ticker_sums)}")
    print(f"Daily Win rate: {win_rate:.2f}%")

def walk_forward_optimize(symbol, strategy_class):
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
            strategy_class,
            train_start.strftime("%Y-%m-%d"), 
            train_end.strftime("%Y-%m-%d"))

        perf = run_one_backtest(
            symbol, 
            strategy_class,
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

def grid_search(symbol, strategy_class, start_date="2023-10-01", end_date="2024-10-01"):
    best_params = optimize_params(symbol, strategy_class, start_date, end_date)
    print(best_params)
    
def optimize_params(symbol, strategy_class, start, end):
    start_time = time.perf_counter()

    param_grid = { # SMA
        "fast_window": [10, 15, 20, 25],
        "slow_window": [20, 25, 30, 35, 40],
        "htf_window": [40, 50, 60, 70, 80],
        "rsi_period": [6],
        "rsi_lower": [30],
        "rsi_upper": [70],
        "stop_loss": [0.003],
        "take_profit": [0.003],
        "trailing_ratio": [0.05],
        "position_size": [1.0]
    }

    param_grid = { # MACD
        "fast_window": [8, 10, 12, 15, 18, 20, 22, 24],
        "slow_window": [5, 6, 8, 10, 12, 15],
        "signal_window": [8, 10, 12, 15, 18, 20, 22, 24],
        "stop_loss": [0.01],
        "take_profit": [0.03],
        "trailing_ratio": [0.05]
    }

    best_score = -np.inf
    best_params = None
    results = []

    for combo in product(*param_grid.values()):
        params = dict(zip(param_grid.keys(), combo))
        perf = run_one_backtest(symbol, strategy_class, start, end, **params, plot=False)
        perf_dict = perf.get_data_dict()
        pnl = perf_dict["Net Profit"]
        if pnl > best_score:
            best_score = pnl
            best_params = params
        print(params)
        results.append({"params": params, "perf": perf_dict})

    with open("gs_results.json", "w") as f:
        json.dump(results, f, indent=4)

    elapsed_time = time.perf_counter() - start_time
    print(f"Elapsed Parameter Optimize Time: {elapsed_time:.6f} seconds")
    
    return best_params

symbols = ["SPY", "QQQ", 
           "AAPL", "MSFT", 
           "NVDA", "AMD", 
           "AMZN", "GOOG", 
           "META", "TSLA"]
curr_symbol = symbols[4]


strategy_kwargs = { # MACD
    "fast_window": 8,
    "slow_window": 15,
    "signal_window": 7, 
    "stop_loss": 0.005,
    "take_profit": 0.02,
    "trailing_ratio": 0.05
}
# strategy_kwargs = { # SMA
#     "fast_window": 10,
#     "slow_window": 20,
#     "htf_window": 50,
#     "rsi_period": 6,
#     "rsi_lower": 30,
#     "rsi_upper": 70,
#     "stop_loss": 0.0075,
#     "take_profit": 0.0075,
#     "trailing_ratio": 0.05
# }

run_one_backtest( # MACD
    curr_symbol,
    MACDIndicator,
    start_date="2023-10-01",
    end_date="2024-10-01",
    plot=True,
    **strategy_kwargs
)
# run_one_backtest( # SMA
#     curr_symbol,
#     SMACrossoverIndicator,
#     start_date="2023-11-01",
#     end_date="2024-11-01",
#     plot=False,
#     **strategy_kwargs
# )

# multiple_symbol_performance(symbols[2:], MACDIndicator, "2023-10-01", "2024-10-01", **strategy_kwargs)
# multiple_symbol_performance(symbols[2:], SMACrossoverIndicator, "2023-11-01", "2024-11-01", **strategy_kwargs)

# walk_forward_optimize(curr_symbol, MACDIndicator)
# walk_forward_optimize(curr_symbol, SMACrossoverIndicator)

# grid_search(curr_symbol, MACDIndicator, start_date="2023-10-01", end_date="2024-10-01")
# grid_search(curr_symbol, SMACrossoverIndicator, start_date="2023-10-01", end_date="2024-10-01")
