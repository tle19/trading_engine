import pandas as pd
import itertools
import json
from pathos.multiprocessing import ProcessingPool as Pool
from utils import *

def run_backtest(strategy, symbol, dh, start_date="2024-09-03", end_date="2025-08-29", initial_cash=30_000, stats=False, plot=False):
    df = dh.open_data(symbol, start_date, end_date)
    df["date"] = df.index.date

    cash = initial_cash
    equity_list = []
    win_rates = []
    total_trades = 0

    if stats:
        run_statistics(strategy, df)

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
        signal = strat.update(row)
        close = row['close']

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

        # --- Exit Position ---
        elif signal == 0 and position is not None:
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

        # --- Force close at 16:00 ---
        if position is not None and row.name.time().strftime("%H:%M") == "16:00":
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

        if position:
            if position == "long":
                current_equity = cash + (close - entry_price) * shares
            elif position == "short":
                current_equity = cash + (entry_price - close) * shares
            intraday_equity.append(current_equity)

    win_rate = wins / total_trades if total_trades > 0 else None
    return cash, win_rate, total_trades, intraday_equity

def run_statistics(strategy, df):
    strat = str(strategy)
    if strategy == 'Momentum':
        HOD_probability(df)
        bearish_overnight_return(df)
    elif strategy == 'mean_reversal':
        return

def _run_combination(params):
    entry_time, entry_cond, stop_loss, take_profit, strategy, symbol, dh_class, start_date, end_date, initial_cash = params

    # instantiate fresh dh inside the worker
    dh = dh_class()

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

    pnl_pct = ((final_cash - initial_cash) / initial_cash) * 100

    return {
        "entry_time": entry_time,
        "entry_cond": entry_cond,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "pnl_pct": pnl_pct,
        "win_rate": avg_win_rate,
        "max_drawdown_pct": max_drawdown_pct,
        "total_trades": total_trades
    }

def grid_search(strategy, symbol, dh, 
                start_date="2024-09-03", end_date="2025-08-29",
                initial_cash=30_000,
                entry_times=[30, 45, 60],  # trend focused
                entry_conds=[0.002, 0.003, 0.004, 0.005, 0.006],
                stop_losses=[0.005, 0.006, 0.008, 0.01],
                take_profits=[0.0025, 0.003, 0.004, 0.005],
                results_file="optimize_results.json"):

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