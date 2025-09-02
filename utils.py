import os

import matplotlib.pyplot as plt
import pandas as pd


def open_data(symbol, date="", start_time="9:30", end_time="16:00"):

    df = pd.read_csv(f"data/{symbol}_historical_data.csv")
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)

    if date != "":
        df = df[df.index.date == pd.to_datetime(date).date()]
    df = df.between_time(start_time, end_time)

    return df

def summary(df, initial_cash):
    strategy_final = df['equity'].iloc[-1]
    print("Strategy final value:", strategy_final)
    print("Strategy Profit %:", (strategy_final - initial_cash) / initial_cash * 100, "%")

def profits(df, symbol="", date=""):
    plt.figure(figsize=(12,6))
    plt.plot(df.index, df['equity'], label='Strategy', color='blue')
    plt.xlabel("Time")
    plt.ylabel("Portfolio Value")
    plt.title(f"{symbol} Strategy Profits ({date})")
    plt.legend()
    plt.grid(True)
    plt.show()