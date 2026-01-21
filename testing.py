import time
import json
from itertools import product
import numpy as np
import pandas as pd

from core import *
from metrics import *
from strategies import *
from models import *
from utils import *

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

def run_one_backtest(symbol, strategy_class, start_date, end_date, cash=25_000, display_plot=True, display_stats=True, save_plot=True, **strategy_kwargs):
    bt = Backtest(symbol, strategy_class, cash=cash, margin=1.0, commission=0.0, slippage=0.1)
    bt.run(start_date=start_date, end_date=end_date, display_plot=display_plot, display_stats=display_stats, save_plot=save_plot, **strategy_kwargs)
    return bt.stats
   
def grid_search(symbol, strategy_class, start, end):
    start_time = time.perf_counter()

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
    
    print(best_params)

def train_model(symbol="META"): # move to utils.py later
    trade_manager = TradeManager(live=False)
    trade_manager.load_logs()
    trade_history = trade_manager.trade_history
    
    curr_date = ts.normalize() 
    start_date = curr_date - pd.DateOffset(days=90)
    trade_manager.trade_history = [
            trade for trade in trade_history
            if start_date < pd.to_datetime(trade["entry_time"]).normalize() < curr_date
       ]
    trade_manager.save_logs()

    mdl = XGBModel(symbol=symbol, strategy="StochasticIndicator", live=False)
    # mdl = RFModel(symbol=symbol, strategy="StochasticIndicator", live=False)
    # mdl = KNNModel(symbol=symbol, strategy="StochasticIndicator", live=False)
    mdl.initialize()
    X_train, X_test, y_train, y_test = train_test_split(mdl.df, n_days=540)
    mdl.train(X_train, y_train)
    mdl.evaluate_classification(X_train, y_train, X_test, y_test)
    mdl.save_model()

    trade_manager.trade_history = trade_history
    trade_manager.save_logs()

grid_search("MSFT", StochasticIndicator, start_date="2024-01-10", end_date="2026-01-02")