import os

import json
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from itertools import chain

def summary(initial_cash, pess_cash, opt_cash, avg_cash, 
            pess_win_rates, opt_win_rates, avg_win_rates, total_trades, equity_list):

    avg_pess_win_rate = calculate_win_rate(pess_win_rates)
    avg_opt_win_rate = calculate_win_rate(opt_win_rates)
    avg_avg_win_rate = calculate_win_rate(avg_win_rates)

    max_drawdown_pct = calculate_drawdown(equity_list)

    for scenario, cash, win_rate in [("Pessimistic", pess_cash, avg_pess_win_rate),
                                    ("Optimistic", opt_cash, avg_opt_win_rate),
                                    ("Average", avg_cash, avg_avg_win_rate)]:
        profit = cash - initial_cash
        profit_pct = (profit / initial_cash) * 100
        print(f"{scenario} Scenario:")
        print("  Initial Cash:", round(initial_cash, 2))
        print("  Final Cash:", round(cash, 2))
        print("  Profit ($):", round(profit, 2))
        print("  Profit %:", round(profit_pct, 2), "%")
        print(f"  Win Rate: {win_rate:.2%}" if win_rate is not None else "  No trades")
        print()

    if max_drawdown_pct is not None:
        print("Max Drawdown:", round(max_drawdown_pct, 2), "%")
    print("Total Trades:", total_trades)
    print()

    return avg_cash, avg_avg_win_rate, max_drawdown_pct

def calculate_win_rate(win_rates):
    avg_win_rate = (
        sum(w for w in win_rates if w is not None) / len([w for w in win_rates if w is not None])
        if any(w is not None for w in win_rates) else None
    )

    return avg_win_rate

def calculate_drawdown(equity_list):
    max_drawdowns_per_day = []

    for intraday_equity in equity_list:
        if not intraday_equity:
            continue  # skip empty days

        cum_max = intraday_equity[0]
        max_dd = 0.0

        for eq in intraday_equity:
            if eq > cum_max:
                cum_max = eq
            drawdown = (cum_max - eq) / cum_max
            if drawdown > max_dd:
                max_dd = drawdown

        max_drawdowns_per_day.append(max_dd * 100)

    max_drawdown_pct = max(max_drawdowns_per_day) if max_drawdowns_per_day else None

    return max_drawdown_pct

def plot_equity(equity_list, symbol="", start_date="", end_date=""):
    equity_values = list(chain.from_iterable(equity_list))
    df = pd.DataFrame({"equity": equity_values})
    num_points = len(df)

    plt.figure(figsize=(14,6))
    plt.plot(df.index, df["equity"], label='Strategy', color='blue')

    months = pd.date_range(start=start_date, end=end_date, freq='MS')
    if len(months) > 12:
        step = int(np.ceil(len(months) / 12))
        months = months[::step]

    month_positions = np.linspace(0, num_points-1, len(months), dtype=int)
    plt.xticks(month_positions, [m.strftime('%b %Y') for m in months], rotation=45)

    plt.xlabel("Date")
    plt.ylabel("Portfolio Value")
    plt.title(f"{symbol} Strategy Equity ({start_date} to {end_date})")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


# df = pd.read_json("scalp_optimize_results.json")
# summary1 = df.groupby("entry_spread")[["pnl_pct", "win_rate"]].mean().reset_index()
# summary2 = df.groupby("stop_loss")[["pnl_pct", "win_rate"]].mean().reset_index()
# summary3 = df.groupby("take_profit")[["pnl_pct", "win_rate"]].mean().reset_index()
# print(summary1)
# print(summary2)
# print(summary3)

# df['expected_value'] = df['win_rate'] * df['pnl_pct'] - (1 - df['win_rate']) * df['stop_loss'] * 100
# df_grouped = df.groupby(['entry_spread', 'stop_loss', 'take_profit'])[['expected_value']].mean().reset_index()
# df_grouped = df_grouped.sort_values('expected_value', ascending=False).reset_index(drop=True)
# print(df_grouped)

# df_ranked = df.sort_values('win_rate', ascending=False).reset_index(drop=True)
# df_ranked[['entry_spread', 'stop_loss', 'take_profit', 'pnl_pct', 'win_rate']]
# print(df_ranked.iloc[10:20, :])