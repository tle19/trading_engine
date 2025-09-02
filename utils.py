import os

import matplotlib.pyplot as plt
import pandas as pd


def open_data(symbol, date, start_time="9:30", end_time="16:00"):
    symbol = "TSLA"

    df = pd.read_csv(f"data/{symbol}_historical_data.csv")
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)

    date = "2025-08-22"
    start_time = "09:30"
    end_time = "16:00"

    df = df[df.index.date == pd.to_datetime(date).date()]
    df = df.between_time(start_time, end_time)

    return df

def summary():
    print("Strategy final value:", df['cum_strategy'].iloc[-1])
    print("Market final value:", df['cum_market'].iloc[-1])

def profits():
    plt.figure(figsize=(12,6))
    plt.plot(df.index, df['cum_strategy'], label='Strategy', color='blue')
    plt.plot(df.index, df['cum_market'], label='Market', color='orange')
    plt.xlabel("Time")
    plt.ylabel("Cumulative Profit")
    plt.title(f"{symbol} Strategy vs Market ({date})")
    plt.legend()
    plt.grid(True)
    plt.show()