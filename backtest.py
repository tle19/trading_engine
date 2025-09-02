import matplotlib.pyplot as plt
import pandas as pd
from utils import *

def run_backtest(strategy, symbol, date="2025-08-22", initial_cash=30_000):

    df = open_data(symbol, date)

    cash = initial_cash
    position = 0
    position_price = 0
    equity_curve = []

    strat = strategy()

    for i, row in df.iterrows():
        close = row['close']

        # Get signal from strategy
        signal = strat.update(row)

        # Enter long
        if signal == 1 and position == 0:
            position = 1
            position_price = close
            cash -= close

        # Exit long
        elif signal == 0 and position == 1:
            cash += close
            position = 0
            position_price = 0

        # Update equity
        equity = cash + position * close
        equity_curve.append(equity)

    df['cum_strategy'] = equity_curve
    df['cum_market'] = (df['close'] / df['close'].iloc[0]) * initial_cash

    # Call utils functions for summary and plots
    summary(df)
    profits(df, symbol, date)