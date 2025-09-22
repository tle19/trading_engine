import pandas as pd
import itertools
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from utils import *

def run_backtest(strategy, symbol, dh, start_date="2024-08-29", end_date="2025-08-29", initial_cash=30_000, plot=False):
    df = dh.open_data(symbol, start_date, end_date)
    df["date"] = df["timestamp"].dt.date

    cash = initial_cash
    equity_list = []
    win_rates = []
    total_trades = 0

    for day, day_df in df.groupby("date"):
        strat = strategy()
        cash, day_win_rate, trades, intraday_equity = run_one_day(day_df, strat, cash)
        total_trades += trades
        equity_list.append(intraday_equity)
        win_rates.append(day_win_rate)

    profit_pct, avg_win_rate, max_drawdown_pct = summary(cash, initial_cash, win_rates, total_trades, equity_list)
    
    if plot:
        equity_df = pd.DataFrame(equity_list, columns=["timestamp", "equity"])
        equity_df.set_index("timestamp", inplace=True)
        profits(equity_df, symbol, f"{start_date} to {end_date}")
    
    return cash, avg_win_rate, max_drawdown_pct, total_trades

def run_one_day(df, strat, cash, win_rate=0):
    shares = 0
    entry_price = None
    position = None   # "long", "short", or None
    wins = 0
    total_trades = 0
    intraday_equity = []

    for _, row in df.iterrows():
        signal, stop_loss, take_profit = strat.update(row)

        close = row['close']
        high = row['high']
        low = row['low']
        
        # --- Enter Long ---
        if signal == 1 and position is None:
            shares = cash // close
            entry_price = close
            position = "long"

        # --- Enter Short ---
        elif signal == -1 and position is None:
            shares = cash // close
            entry_price = close
            position = "short"

        
        # --- Exit (PESSIMISTIC) ---
        elif signal == 0 and position is not None:
            if position == "long":
                pnl = (close - entry_price) * shares
                if low <= entry_price * (1 - stop_loss):
                    pass
                elif high >= entry_price * (1 + take_profit):
                    wins += 1

            elif position == "short":
                pnl = (entry_price - close) * shares
                if high >= entry_price * (1 + stop_loss):
                    pass
                elif low <= entry_price * (1 - take_profit):
                    wins += 1

            cash += pnl
            total_trades += 1
            shares = 0
            entry_price = None
            position = None
        

        # --- Exit (OPTIMISTIC) ---
        elif signal == 0 and position is not None:
            if position == "long":
                pnl = (close - entry_price) * shares
                if high >= entry_price * (1 + take_profit):
                    wins += 1
                elif low <= entry_price * (1 - stop_loss):
                    pass

            elif position == "short":
                pnl = (entry_price - close) * shares
                if low <= entry_price * (1 - take_profit):
                    wins += 1
                elif high >= entry_price * (1 + stop_loss):
                    pass

            cash += pnl
            total_trades += 1
            shares = 0
            entry_price = None
            position = None

        # --- Force close at 16:00 ---
        ts = pd.to_datetime(row['timestamp'])
        if position is not None and ts.hour == 15 and ts.minute == 59:
            if position == "long":
                pnl = (close - entry_price) * shares
                cash += pnl
                if pnl > 0:
                    wins += 1

            elif position == "short":
                pnl = (entry_price - close) * shares
                cash += pnl
                if pnl > 0:
                    wins += 1

            total_trades += 1
            shares = 0
            entry_price = None
            position = None

        if position == "long":
            current_equity = cash + (close - entry_price) * shares
        elif position == "short":
            current_equity = cash + (entry_price - close) * shares
        else:
            current_equity = cash
        intraday_equity.append(current_equity)

    win_rate = wins / total_trades if total_trades > 0 else None
    return cash, win_rate, total_trades, intraday_equity

def _run_combination(params):
    entry_spread, stop_loss, take_profit, strategy_class, symbol, dh_class, start_date, end_date, initial_cash = params

    # fresh instances inside the worker
    dh = dh_class()
    strat = strategy_class(entry_spread=entry_spread, stop_loss=stop_loss, take_profit=take_profit)

    final_cash, avg_win_rate, max_drawdown_pct, total_trades = run_backtest(
        lambda: strat, symbol, dh,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash
    )

    pnl_pct = ((final_cash - initial_cash) / initial_cash) * 100

    return {
        "entry_spread": entry_spread,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "pnl_pct": pnl_pct,
        "win_rate": avg_win_rate,
        "max_drawdown_pct": max_drawdown_pct,
        "total_trades": total_trades
    }

def grid_search_scalp(strategy, symbol, dh_class, 
                      start_date="2024-08-29", end_date="2025-08-29",
                      initial_cash=30_000,
                      entry_spreads=[0.0005, 0.0006, 0.00065, 0.0007, 0.00075, 0.0008, 0.0009],
                      stop_losses=[0.00035, 0.0004, 0.00045, 0.0005, 0.00055, 0.0006, 0.00065],
                      take_profits=[0.0003, 0.00035, 0.0004, 0.00045, 0.0005],
                      results_file="scalp_optimize_results.json"):

    best_pnl_pct = -float("inf")
    best_params = None
    best_winrate = 0.0
    results = []

    all_params = [
        (entry_spread, stop_loss, take_profit, strategy, symbol, dh_class, start_date, end_date, initial_cash)
        for entry_spread, stop_loss, take_profit in itertools.product(entry_spreads, stop_losses, take_profits)
    ]

    # run in parallel
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_run_combination, p) for p in all_params]

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            pnl_pct = result["pnl_pct"]
            win_rate = result["win_rate"]

            if pnl_pct > best_pnl_pct or (pnl_pct == best_pnl_pct and win_rate > best_winrate):
                best_pnl_pct = pnl_pct
                best_winrate = win_rate
                best_params = (
                    result.get("entry_spread"),
                    result.get("stop_loss"),
                    result.get("take_profit")
                )

            print(result)

    # save all results
    with open(results_file, "w") as f:
        json.dump(results, f, indent=4)

    print("Best params:", best_params)
    print("Best PnL %:", best_pnl_pct)
    print("Best winrate:", best_winrate)
    print(f"Saved all results to {results_file}")

    return best_params, best_pnl_pct, best_winrate, results

def grid_search_trend(strategy, symbol, dh, 
                start_date="2024-09-03", end_date="2025-08-29",
                initial_cash=30_000,
                entry_times=[25, 30, 35, 40],  # trend focused
                entry_conds=[0.002, 0.003, 0.004, 0.005],
                stop_losses=[0.004, 0.006, 0.008, 0.01],
                take_profits=[0.001, 0.002, 0.003, 0.004],
                results_file="trend_optimize_results.json"):

    best_pnl_pct = -float("inf")
    best_params = None
    best_winrate = 0.0
    results = []

    for entry_time, entry_cond, stop_loss, take_profit in itertools.product(
        entry_times, entry_conds, stop_losses, take_profits
    ):
        # define strategy with current params
        def strat_factory():
            return strategy(
                entry_time=entry_time,
                entry_cond=entry_cond,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

        # run backtest
        final_cash, avg_win_rate, max_drawdown_pct, total_trades = run_backtest(
            strat_factory, symbol, dh,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash
        )

        pnl = final_cash - initial_cash
        pnl_pct = (pnl / initial_cash) * 100

        result = {
            "entry_time": entry_time,
            "entry_cond": entry_cond,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "win_rate": avg_win_rate,
            "max_drawdown_pct": max_drawdown_pct,
            "total_trades": total_trades
        }
        results.append(result)

        # choose best by pnl % first, then winrate
        if pnl_pct > best_pnl_pct or (pnl_pct == best_pnl_pct and avg_win_rate > best_winrate):
            best_pnl_pct = pnl_pct
            best_winrate = avg_win_rate
            best_params = (entry_time, entry_cond, stop_loss, take_profit)

        print(result)

    # save all results to JSON
    with open(results_file, "w") as f:
        json.dump(results, f, indent=4)

    print("Best params:", best_params)
    print("Best PnL %:", best_pnl_pct)
    print("Best winrate:", best_winrate)
    print(f"Saved all results to {results_file}")

    return best_params, best_pnl_pct, best_winrate, results