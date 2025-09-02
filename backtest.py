import matplotlib.pyplot as plt
import pandas as pd
from utils import *

def run_backtest(strategy, symbol, date="", initial_cash=30_000):
    df = open_data(symbol, date)

    cash = initial_cash
    position = 0
    entry_price = 0
    equity_curve = []

    strat = strategy()

    for _, row in df.iterrows():
        signal = strat.update(row)
        close = row['close']

        if signal == 1 and position == 0:
            position = 1
            entry_price = close
            cash -= entry_price

        elif signal == -1 and position == 1:
            position = 0
            cash += close

        equity = cash + position * close
        equity_curve.append(equity)

    df['equity'] = equity_curve
    summary(df, initial_cash)
    profits(df, symbol, date)