import time
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

    strat = SMACrossoverIndicator(symbol, short_window=10, long_window=20, position_size=1.0, 
                                stop_loss=0.005, take_profit=0.015, trailing_ratio=0.9)
    bt = Backtest(symbol, strat, cash=25_000, margin=1.0, shares=30, 
                commission=0.0, slippage=0.0002, force_close=True)
    bt.run(start_date="2023-10-02", end_date="2024-10-02")

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Elapsed time: {elapsed_time:.6f} seconds")

# grid search
def grid_search(symbol):
    short_window = [5, 8, 10, 15, 20, 25]
    long_window = [8, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    take_profits = [0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.0175, 0.02, 0.025, 0.03]
    stop_losses = [0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.0175, 0.02, 0.025, 0.03]

    grid_lists = [take_profits, stop_losses]

    for combo in product(*grid_lists):
        tp, sl = combo  # unpack current take_profit and stop_loss

        start_time = time.perf_counter()
        
        strat = SMACrossoverIndicator(
            symbol,
            short_window=10,
            long_window=20,
            position_size=1.0,
            stop_loss=sl,
            take_profit=tp,
            trailing_ratio=0.9 #fixed
        )

        bt = Backtest(symbol, strat, cash=25_000, margin=1.0, shares=30, 
                    commission=0.0, slippage=0.0002, force_close=True
        )
        bt.run(start_date="2023-10-02", end_date="2024-10-02")

        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        print(f"Take Profit: {tp}, Stop Loss: {sl}, Elapsed time: {elapsed_time:.6f} seconds")



symbols = ["SPY", "QQQ", 
           "TSLA", "NVDA", 
           "AMD", "AMZN", 
           "AAPL", "GOOG", 
           "MSFT", "META", 
           "TSM", "CSCO", 
           "INTC", "ADBE"]
curr_symbol = symbols[2]


# fetch_multiple_symbols(symbols)
# run_one_backtest(curr_symbol)
grid_search(curr_symbol)


# walk forward optimization / OOS
