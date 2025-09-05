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
        print(signal)
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
    elif strategy == 'mean_reversal':
        return



# def run_backtest(strategy, symbol, dh, start_date="2024-10-01", end_date=None, initial_cash=30_000):
#     df = dh.open_data(symbol)

#     if end_date is not None:
#         df = df[(df.index.date >= pd.to_datetime(start_date).date()) &
#                 (df.index.date <= pd.to_datetime(end_date).date())]
#     else:
#         df = df[df.index.date >= pd.to_datetime(start_date).date()]

#     if df.empty:
#         print("No data in the specified date range.")
#         return
    
#     cash = initial_cash
#     position = 0
#     equity_curve = []

#     run_statistics(strategy, df)
#     strat = strategy()

#     for date, day_group in df.groupby(df.index.date):
#         for _, row in day_group.iterrows():
#             signal = strat.update(row)
#             close = row['close']

#             if signal == 1 and position == 0:
#                 cash -= close
#                 position = 1
#             elif signal == -1 and position == 1:
#                 cash += close
#                 position = 0

#             equity_curve.append(cash + position * close)
            
#         print(date, " ", cash)
#         print(close)

#     df['equity'] = equity_curve
#     summary(df, initial_cash)
#     profits(df, symbol, date)