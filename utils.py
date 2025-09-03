import os

import matplotlib.pyplot as plt
import pandas as pd


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