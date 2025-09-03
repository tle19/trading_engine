import pandas as pd
from utils import *


def run_backtest(strategy, symbol, dh, date="", initial_cash=30_000):
    df = dh.open_data(symbol, date)

    cash = initial_cash
    position = 0
    equity_curve = []

    strat = strategy()

    for _, row in df.iterrows():
        signal = strat.update(row)
        close = row['close']

        if signal == 1:
            cash -= close
            position = 1
        elif signal == -1:
            cash += close
            position = 0

        equity_curve.append(cash + position * close)

    df['equity'] = equity_curve
    summary(df, initial_cash)
    profits(df, symbol, date)