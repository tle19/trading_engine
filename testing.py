import time
import json
from itertools import product
import numpy as np
import pandas as pd

from core import *
from strategies import *
from utils import *

def run_one_backtest(symbol, strategy_class, start_date, end_date, cash=25_000, display_plot=True, display_stats=True, save_plot=True, **strategy_kwargs):
    bt = Backtest(symbol, strategy_class, cash=cash, margin=1.0, commission=0.0, slippage=0.1)
    bt.run(start_date=start_date, end_date=end_date, display_plot=display_plot, display_stats=display_stats, save_plot=save_plot, **strategy_kwargs)
    return bt.stats

def grid_search(symbol, strategy_class, start_date="2023-10-01", end_date="2024-10-01"):
    best_params = optimize_params(symbol, strategy_class, start_date, end_date)
    print(best_params)
    
def optimize_params(symbol, strategy_class, start, end):
    start_time = time.perf_counter()

    param_grid = { # MACD
        "fast_window": [3, 4, 5, 6],
        "slow_window": [7, 8, 9, 10, 11, 12],
        "signal_window": [4, 5, 6, 7, 8, 9],
        "stop_loss": [0.001],
        "take_profit": [0.005]
    }

    param_grid = { # Volume
        "fast_window": [14],
        "slow_window": [28],
        "rsi_period": [14],
        "rsi_thresh": [1, 2, 3, 4, 5],
        "vol_accel_factor": [1.1, 1.2, 1.3, 1.4, 1.5],
        "vol_decay_factor": [1.5, 2, 3, 4, 5],
        "stop_loss": [0.0025, 0.005, 0.0075, 0.01],
        "take_profit": [0.03] # 0.01, 0.015, 0.02, 0.03
        }
    
    param_grid = { # ORB
        "orb_window": [5, 10, 15, 30, 45, 60],
        "stop_loss": [0.25, 0.50, 0.75, 1.00, 1.25, 1.5, 1.75, 2.00],
        "take_profit": [0.25, 0.50, 0.75, 1.00, 1.25, 1.5, 1.75, 2.00],
        "trailing_ratio": [0.1]
    }

    param_grid = { # Stochastic
        "fast_window": [12],
        "slow_window": [26],
        "signal_window": [9],
        "rsi_period": [14],
        "k_period": [14],
        "k_smooth": [3],
        "d_period": [3],
        "stoch_lower": [20],
        "stoch_upper": [80],
        "vol_fast_window": [14],
        "vol_slow_window": [28],
        "stop_loss": [0.005, 0.0075, 0.01, 0.0125, 0.015],
        "take_profit": [0.005, 0.0075, 0.01, 0.0125, 0.015],
        "trailing_ratio": [0.05]
    }

    best_score = -np.inf
    best_params = None
    results = []

    for combo in product(*param_grid.values()):
        params = dict(zip(param_grid.keys(), combo))
        perf = run_one_backtest(symbol, strategy_class, start, end, **params, display_plot=False, save_plot=False)
        perf_dict = perf.get_data_dict()
        pnl = perf_dict["Net Profit"]
        if pnl > best_score:
            best_score = pnl
            best_params = params
        print(params)
        results.append({"params": params, "perf": perf_dict})

    with open("grid_search.json", "w") as f:
        json.dump(results, f, indent=4)

    elapsed_time = time.perf_counter() - start_time
    print(f"Elapsed Parameter Optimize Time: {elapsed_time:.6f} seconds")
    
    return best_params

symbols = [
    "SPY", "QQQ", "IWM", "TLT", "BRK.B", 
    "AAPL", "MSFT", "NVDA", "AMD", "GOOG",
    "META", "ADBE", "CRM", "INTC", "AVGO",
    "NFLX", "TSLA", "AMZN", "HD", "MCD", "NKE",
    "SBUX", "COST", "WMT", "PG", "KO", "PEP",
    "V", "MA", "JPM", "GS", "BAC", "MS", 
    "C", "AXP", "SCHW", "WFC", "COF", 
    "XOM", "CVX", "SLB", "CAT", "DE", 
    "GE", "BA", "LMT", "RTX", "HON", "UPS", 
    "UNH", "LLY", "ABBV", "JNJ", 
    "MRK", "PFE", "TMO", "AMGN" 
]

symbols = ["QQQ", "AAPL", "MSFT", "META", "CRM", "ABBV", "CVX", "MRK", "UPS", "AXP", "CAT"]

# strategy_kwargs = { # MACD
#     "fast_window_low": 5, 
#     "slow_window_low": 8, 
#     "signal_window_low": 9,
#     "fast_window_med": 13, 
#     "slow_window_med": 21, 
#     "signal_window_med": 9,
#     "fast_window_high": 34, 
#     "slow_window_high": 144, 
#     "signal_window_high": 9,
#     "htf_window": 50,
#     "ma_threshold": 0.001,
#     "stop_loss": 0.005, 
#     "take_profit": 0.01
# }
# run_one_backtest( # MACD
#     "TSLA",
#     MACDIndicator,
#     start_date="2023-11-01",
#     end_date="2025-11-01",
#     plot=True,
#     **strategy_kwargs
# )

# strategy_kwargs = { # Volume
#     "fast_window": 14,
#     "slow_window": 28,
#     "rsi_period": 14,
#     "rsi_thresh": 1,
#     "vol_decay_factor": 2,
#     "vol_accel_factor": 1.1,
#     "stop_loss": 0.01,
#     "take_profit": 0.01
# }
# run_one_backtest( # Volume
#     "TSLA",
#     VolumeDecayIndicator,
#     start_date="2025-10-20",
#     end_date="2025-11-01",
#     plot=True,
#     **strategy_kwargs
# )

# strategy_kwargs = { # ORB
#     "orb_window": 5,
#     "stop_loss": 0.01,
#     "take_profit": 0.01,
#     "trailing_ratio": 0.1
# }
# run_one_backtest( # ORB
#     "TSLA",
#     ORBIndicator,
#     start_date="2025-11-01",
#     end_date="2025-12-01",
#     plot=True,
#     **strategy_kwargs
# )

# strategy_kwargs = { # RSI
#     "rsi_period": 2,
#     "htf_window": 50,
#     "stop_loss": 0.01,
#     "take_profit": 0.01
# }
# run_one_backtest( # RSI
#     "TSLA",
#     RSIScalp,
#     start_date="2025-11-01",
#     end_date="2025-12-01",
#     plot=True,
#     **strategy_kwargs
# )

strategy_kwargs = { # Stochastic
    "fast_window": 12,
    "slow_window": 26,
    "signal_window": 9,
    "rsi_period": 14,
    "k_period": 14,
    "k_smooth": 3,
    "d_period": 3,
    "stoch_lower": 20,
    "stoch_upper": 80,
    "vol_fast_window": 14,
    "vol_slow_window": 28,
    "stop_loss": 0.01,
    "take_profit": 0.01,
    "trailing_ratio": 0.05
}
# run_one_backtest( # Stochastic
#     "[QQQ]",
#     StochasticIndicator,
#     start_date="2024-01-10",
#     end_date="2026-01-02",
#     plot=True,
#     **strategy_kwargs
# )

# grid_search("MSFT", StochasticIndicator, start_date="2024-01-10", end_date="2026-01-02")

# dd = current_drawdown(stats.intraday_equity)
# slope = equity_slope(stats.intraday_equity)
# days = drawdown_rebalance(dd, slope, day_rebalance)