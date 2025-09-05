import pandas as pd
from utils import *


def run_backtest(strategy, symbol, dh, date="2024-10-01", initial_cash=30_000):
    df = dh.open_data(symbol, date)

    cash = initial_cash
    position = 0
    equity_curve = []

    run_statistics(strategy, df)
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

def run_statistics(strategy, df):
    strat = str(strategy)
    if strategy == 'Momentum':
        HOD_probability(df)
        bearish_overnight_return(df)
    if strategy == 'mean_reversal':
        return