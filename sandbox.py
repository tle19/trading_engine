import time
import json
from itertools import product
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

def multiple_symbol_performance(symbols, strategy_class, start_date, end_date, plot, **strategy_kwargs):
    ticker_pnls = []
    for symbol in symbols:
        stats = run_one_backtest(symbol, strategy_class, start_date, end_date, plot=plot, **strategy_kwargs)
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
    start = pd.Timestamp("2023-11-01")
    end = pd.Timestamp("2025-11-01")

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
        "fast_window": [10],
        "slow_window": [20],
        "htf_window": [50],
        "rsi_period": [6],
        "rsi_lower": [30],
        "rsi_upper": [70],
        "stop_loss": [0.003],
        "take_profit": [0.003],
        "trailing_ratio": [0.05],
        "position_size": [1.0]
    }

    param_grid = { # MACD
        "fast_window": [12],
        "slow_window": [26],
        "signal_window": [9],
        "htf_window": [50],
        "rsi_period": [14],
        "vol_fast_window": [7],
        "vol_slow_window": [12],
        "stop_loss": [0.01],
        "take_profit": [0.01],
        "trailing_ratio": [0.05]
    }

    param_grid = { # ORB
        "orb_window": [15],
        "rsi_period": [14],
        "stop_loss": [0.005],
        "take_profit": [0.01],
        "trailing_ratio": [0.05]
    }

    param_grid = { # Stochastic
        "fast_window": [12],
        "slow_window": [26],
        "signal_window": [9],
        "htf_window": [50], 
        "rsi_period": [14],
        "k_period": [14],
        "k_smooth": [3],
        "d_period": [3],
        "stoch_lower": [20],
        "stoch_upper": [80],
        "vol_fast_window": [14], # [7, 10, 12, 14]
        "vol_slow_window": [28], # [15, 20, 25, 28]
        "stop_loss": [0.0075],
        "take_profit": [1.25],
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

symbols = [
    # ===== INDEX / MACRO =====
    "SPY",   # S&P 500 ETF
    "QQQ",   # Nasdaq-100 ETF
    "IWM",   # Russell 2000 ETF
    "TLT",   # 20+ Year Treasury Bonds ETF
    "BRK.B",  # Berkshire Hathaway

    # ===== TECH =====
    "AAPL",  # Apple
    "MSFT",  # Microsoft
    "NVDA",  # NVIDIA
    "AMD",   # AMD
    "GOOG",  # Alphabet
    "META",  # Meta Platforms
    "ADBE",  # Adobe
    "CRM",   # Salesforce
    "INTC",  # Intel
    "AVGO",  # Broadcom
    "NFLX",  # Netflix

    # ===== CONSUMER =====
    "TSLA",  # Tesla
    "AMZN",  # Amazon
    "HD",    # Home Depot
    "MCD",   # McDonald's
    "NKE",   # Nike
    "SBUX",  # Starbucks
    "COST",  # Costco
    "WMT",   # Walmart
    "PG",    # Procter & Gamble
    "KO",    # Coca-Cola
    "PEP",   # PepsiCo

    # ===== FINANCIALS =====
    "V",     # Visa
    "MA",     # Mastercard
    "JPM",   # JPMorgan Chase
    "GS",    # Goldman Sachs
    "BAC",   # Bank of America
    "MS",    # Morgan Stanley
    "C",     # Citigroup
    "AXP",   # American Express
    "SCHW",  # Charles Schwab
    "WFC",   # Wells Fargo
    "COP",   # Capital One

    # ===== INDUSTRIALS / ENERGY =====
    "XOM",   # ExxonMobil
    "CVX",   # Chevron
    "SLB",   # Schlumberger
    "CAT",   # Caterpillar
    "DE",    # Deere & Co
    "GE",    # General Electric
    "BA",    # Boeing
    "LMT",   # Lockheed Martin
    "RTX",   # RTX
    "HON",   # Honeywell
    "UPS",   # United Parcel Service

    # ===== HEALTHCARE =====
    "UNH",   # UnitedHealth Group
    "LLY",   # Eli Lilly
    "ABBV",  # AbbVie
    "JNJ",   # Johnson & Johnson
    "MRK",   # Merck
    "PFE",   # Pfizer
    "TMO",   # Thermo Fisher Scientific
    "AMGN"  # Amgen
    
]

strategy_kwargs = { # Stochastic
    "fast_window": 12,
    "slow_window": 26,
    "signal_window": 9,
    "htf_window": 50, 
    "rsi_period": 14,
    "k_period": 14,
    "k_smooth": 3,
    "d_period": 3,
    "stoch_lower": 20,
    "stoch_upper": 80,
    "vol_fast_window": 14,
    "vol_slow_window": 28,
    "stop_loss": 0.0075,
    "take_profit": 1.25,
    "trailing_ratio": 0.05
}
# strategy_kwargs = { # ORB
#     "orb_window": 15,
#     "rsi_period": 14,
#     "fast_window": 12,
#     "slow_window": 26,
#     "signal_window": 9,
#     "stop_loss": 0.0025,
#     "take_profit": 0.01,
#     "trailing_ratio": 0.1
# }
# strategy_kwargs = { # MACD
#         "fast_window": 12,
#         "slow_window": 26,
#         "signal_window": 9,
#         "htf_window": 50,
#         "rsi_period": 14,
#         "vol_fast_window": 7,
#         "vol_slow_window": 12,
#         "stop_loss": 0.005,
#         "take_profit": 0.0075,
#         "trailing_ratio": 0.05
# }
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

run_one_backtest( # Stochastic
    "MSFT",
    StochasticIndicator,
    start_date="2023-11-01",
    end_date="2025-11-01",
    plot=True,
    **strategy_kwargs
)
# run_one_backtest( # ORB
#     "TSLA",
#     ORBIndicator,
#     start_date="2023-01-01",
#     end_date="2024-10-21",
#     plot=True,
#     **strategy_kwargs
# )
# run_one_backtest( # MACD
#     "TSLA",
#     MACDIndicator,
#     start_date="2023-11-01",
#     end_date="2024-11-01",
#     plot=True,
#     **strategy_kwargs
# )
# run_one_backtest( # SMA
#     "TSLA",
#     SMACrossoverIndicator,
#     start_date="2023-11-01",
#     end_date="2024-11-01",
#     plot=True,
#     **strategy_kwargs
# )

multiple_symbol_performance(symbols, StochasticIndicator, "2023-11-01", "2025-11-01", plot=True, **strategy_kwargs)
# grid_search("MSFT", StochasticIndicator, start_date="2023-10-01", end_date="2024-10-01")
# walk_forward_optimize("MSFT", StochasticIndicator)


