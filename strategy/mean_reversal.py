import os

import pandas as pd

def strategy1(df):
    # High/Low breakout strategy
    df['prev_high'] = df['high'].shift(1)
    df['prev_low'] = df['low'].shift(1)
    df.dropna(subset=['prev_high', 'prev_low'], inplace=True)

    df['signal'] = 0
    df.loc[df['close'] > df['prev_high'], 'signal'] = 1   # buy
    df.loc[df['close'] < df['prev_low'], 'signal'] = -1   # sell

    # Calculate returns
    df['returns'] = df['close'].pct_change().fillna(0)
    df['strategy_returns'] = df['returns'] * df['signal'].shift(1)  # assume enter next minute

    # Cumulative profits
    df['cum_strategy'] = (1 + df['strategy_returns']).cumprod()
    df['cum_market'] = (1 + df['returns']).cumprod()  # buy-and-hold baseline
    
    return df