import os

import json
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def summary(final_cash, initial_cash, win_rates, total_trades, equity_list):
    profit = final_cash - initial_cash
    profit_pct = (profit / initial_cash) * 100

    avg_win_rate = (
        sum(w for w in win_rates if w is not None) / len([w for w in win_rates if w is not None])
        if any(w is not None for w in win_rates) else None
    )

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

    overall_max_drawdown = max(max_drawdowns_per_day) if max_drawdowns_per_day else None

    print("Final Cash:", round(final_cash, 2))
    print("Profit ($):", round(profit, 2))
    print("Profit %:", round(profit_pct, 2), "%")
    print(f"Average win rate: {avg_win_rate:.2%}" if avg_win_rate is not None else "No trades")
    print("Total Trades:", total_trades)
    if overall_max_drawdown is not None:
        print("Max Drawdown %:", round(overall_max_drawdown, 2), "%")
    return profit_pct, avg_win_rate, overall_max_drawdown

def profits(df, symbol="", date=""):
    daily_equity = df.groupby("date")["equity"].last()

    plt.figure(figsize=(12,6))
    plt.plot(daily_equity.index, daily_equity.values, label='Strategy', color='blue', marker="o")
    plt.xlabel("Date")
    plt.ylabel("Portfolio Value")
    plt.title(f"{symbol} Strategy Profits ({date})")
    plt.legend()
    plt.grid(True)
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