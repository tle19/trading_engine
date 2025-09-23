import pandas as pd
import itertools
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from utils import *

def run_backtest(strategy, symbol, dh, start_date="2023-09-01", end_date="2024-09-01", initial_cash=25_000, plot=True):
    df = dh.open_data(symbol, start_date, end_date)
    df["date"] = df["timestamp"].dt.date

    pess_cash = opt_cash = avg_cash = initial_cash

    pess_win_rates = []
    opt_win_rates = []
    avg_win_rates = []

    equity_list = []
    total_trades = 0

    for day, day_df in df.groupby("date"):
        strat = strategy()
        pess_cash, opt_cash, avg_cash, p_win_rate, o_win_rate, a_win_rate, trades, intraday_equity = run_one_day(day_df, strat, pess_cash, opt_cash, avg_cash)
        
        pess_win_rates.append(p_win_rate)
        opt_win_rates.append(o_win_rate)
        avg_win_rates.append(a_win_rate)

        equity_list.append(intraday_equity)
        total_trades += trades

    avg_cash, win_rate, max_drawdown_pct = summary(initial_cash, pess_cash, opt_cash, avg_cash, 
                                                            pess_win_rates, opt_win_rates, avg_win_rates, total_trades, equity_list)

    if plot:
        plot_equity(equity_list, symbol, start_date, end_date)
    
    return avg_cash, win_rate, max_drawdown_pct, total_trades

def run_one_day(df, strat, pess_cash, opt_cash, avg_cash, shares=100):
    entry_price = None
    position = None
    total_trades = 0
    pess_wins = 0
    opt_wins = 0
    intraday_equity = []

    for _, row in df.iterrows():
        signal, stop_loss, take_profit, position_size = strat.update(row)

        close = row['close']
        high = row['high']
        low = row['low']

        if position_size is not None:
            shares = (avg_cash * position_size) // close

        # --- Enter Long ---
        if signal == 1 and position is None:
            position = "long"
            entry_price = close

        # --- Enter Short ---
        elif signal == -1 and position is None:
            position = "short"
            entry_price = close

        # --- Exit ---
        elif signal == 0 and position is not None:
            if position == "long":
                stop_loss_price = entry_price * (1 - stop_loss)
                take_profit_price = entry_price * (1 + take_profit)

                # pessimistic
                if low <= stop_loss_price:
                    pnl = (stop_loss_price - entry_price) * shares
                elif high >= take_profit_price:
                    pnl = (take_profit_price - entry_price) * shares
                    pess_wins += 1
                pess_cash += pnl
                
                # optimistic
                if high >= take_profit_price:
                    pnl = (take_profit_price - entry_price) * shares
                    opt_wins += 1
                elif low <= stop_loss_price:
                    pnl = (stop_loss_price - entry_price) * shares
                opt_cash += pnl

            elif position == "short":
                stop_loss_price = entry_price * (1 + stop_loss)
                take_profit_price = entry_price * (1 - take_profit)

                # pessimistic
                if high >= stop_loss_price:
                    pnl = (entry_price - stop_loss_price) * shares
                elif low <= take_profit_price:
                    pnl = (entry_price - take_profit_price) * shares
                    pess_wins += 1
                pess_cash += pnl

                # optimistic
                if low <= take_profit_price:
                    pnl = (entry_price - take_profit_price) * shares
                    opt_wins += 1
                elif high >= stop_loss_price:
                    pnl = (entry_price - stop_loss_price) * shares
                opt_cash += pnl

            entry_price = None
            position = None
            total_trades += 1
            avg_cash = (pess_cash + opt_cash) / 2

        # --- Force close at 16:00 --- WIP
        # ts = pd.to_datetime(row['timestamp'])
        # if position is not None and ts.hour == 15 and ts.minute == 59:
        #     if position == "long":
        #         pnl = (close - entry_price) * shares
        #         cash += pnl
        #         if pnl > 0:
        #             wins += 1

        #     elif position == "short":
        #         pnl = (entry_price - close) * shares
        #         cash += pnl
        #         if pnl > 0:
        #             wins += 1

        #     total_trades += 1
        #     entry_price = None
        #     position = None

        current_equity = avg_cash
        if position == "long":
            current_equity = shares * (close - entry_price) + avg_cash
        elif position == "short":
            current_equity = shares * (entry_price - close) + avg_cash
        intraday_equity.append(current_equity)

    pess_win_rate = pess_wins / total_trades if total_trades > 0 else None
    opt_win_rate = opt_wins / total_trades if total_trades > 0 else None
    if pess_win_rate is None or opt_win_rate is None:
        avg_win_rate = None
    else:
        avg_win_rate = (pess_win_rate + opt_win_rate) / 2
    
    return pess_cash, opt_cash, avg_cash, pess_win_rate, opt_win_rate, avg_win_rate, total_trades, intraday_equity

def _run_combination(params):
    entry_spread, stop_loss, take_profit, strategy_class, symbol, dh_class, start_date, end_date, initial_cash = params

    # fresh instances inside the worker
    dh = dh_class()
    strat = strategy_class(entry_spread=entry_spread, stop_loss=stop_loss, take_profit=take_profit)

    final_cash, avg_win_rate, max_drawdown_pct, total_trades = run_backtest(
        lambda: strat, symbol, dh,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        plot=False
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
                      initial_cash=25_000,
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

def grid_search_mean_reversion(strategy_class, symbol, dh_class, 
                               start_date="2023-08-29", end_date="2024-08-29",
                               initial_cash=25_000,
                               entry_spreads=[0.000275, 0.0003, 0.000325, 0.00035],
                               stop_losses=[0.002, 0.0020625, 0.002125, 0.0021875, 0.00225],
                               take_profits=[0.002, 0.0020625, 0.002125, 0.0021875, 0.002255],
                               results_file="mean_rev_optimize_results.json"):

    best_pnl_pct = -float("inf")
    best_params = None
    best_winrate = 0.0
    results = []

    all_params = [
        (entry_spread, stop_loss, take_profit, strategy_class, symbol, dh_class, start_date, end_date, initial_cash)
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
                initial_cash=25_000,
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