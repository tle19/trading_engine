import time
import json
from itertools import product

from core import *
from strategies import *

# multiple symbol fetch
def fetch_multiple_symbols():
    dh = DataHandler()
    for symbol in symbols:
        start_time = time.perf_counter()

        dh.historical_data(symbol)

        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        print(f"Elapsed time: {elapsed_time:.6f} seconds")

# once backtest run
def run_one_backtest(symbol):
    start_time = time.perf_counter()

    strat = SMACrossoverIndicator(symbol, fast_window=10, slow_window=20, position_size=1.0, 
                                stop_loss=0.005, take_profit=0.015, trailing_ratio=0.2)
    bt = Backtest(symbol, strat, cash=25_000, margin=1.0, shares=30, 
                commission=0.0, slippage=0.0002, force_close=True)
    bt.run(start_date="2023-10-02", end_date="2024-10-02", plot=True)

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Elapsed time: {elapsed_time:.6f} seconds")

# grid search
def grid_search(symbol):
    fast_window = [5, 8, 10, 15, 20, 25]
    slow_window = [8, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    take_profits = [0.01, 0.0125, 0.015, 0.0175, 0.02]
    stop_losses = [0.0025, 0.005, 0.0075, 0.01]

    grid_lists = [fast_window, slow_window]
    all_results = []

    for combo in product(*grid_lists):
        short, long = combo

        start_time = time.perf_counter()
        
        strat = SMACrossoverIndicator(
            symbol,
            fast_window=short,
            slow_window=long,
            position_size=1.0,
            stop_loss=0.005,
            take_profit=0.015,
            trailing_ratio=0.9
        )

        bt = Backtest(symbol, strat, cash=25_000, margin=1.0, shares=30, 
                    commission=0.0, slippage=0.0002, force_close=True
        )
        bt.run(start_date="2023-10-02", end_date="2024-10-02")

        stats = bt.get_stats_class()
        data = stats.get_data_dict()
        data["slow_window"] = long
        data["fast_window"] = short
        all_results.append(data)

        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        print(f"slow_window: {long}, fast_window: {short}, Elapsed time: {elapsed_time:.6f} seconds")

    with open("grid_search_result.json", "w") as f:
        json.dump(all_results, f, indent=4)

def grid_search_results():   
    with open("grid_search_result.json", "r") as f:
        results = json.load(f)
    best_run = max(results, key=lambda x: x["Net Profit [$]"])

    print("=== Best Grid Search Result ===")
    print(f"Take Profit: {best_run['take_profit']}")
    print(f"Stop Loss: {best_run['stop_loss']}")
    print(f"Net Profit [$]: {best_run['Net Profit [$]']}")
    print(f"Avg Δ per step [$]: {best_run.get('Avg Δ per step [$]', 'N/A')}")
    print(f"Win Rate [%]: {best_run.get('Win Rate [%]', 'N/A')}")
    print(f"# Trades: {best_run.get('# Trades', 'N/A')}")

symbols = ["SPY", "QQQ", 
           "TSLA", "NVDA", 
           "AMD", "AMZN", 
           "AAPL", "GOOG", 
           "MSFT", "META", 
           "TSM", "CSCO", 
           "INTC", "ADBE"]
curr_symbol = symbols[8]


# fetch_multiple_symbols(symbols)
run_one_backtest(curr_symbol)
# grid_search(curr_symbol)
# grid_search_results()


# walk forward optimization / OOS

    