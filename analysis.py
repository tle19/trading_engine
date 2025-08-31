import os

import matplotlib.pyplot as plt
import pandas as pd


symbol = "TSLA"

df = pd.read_csv(f"{symbol}_historical_data.csv")
df['datetime'] = pd.to_datetime(df['datetime'])
df.set_index('datetime', inplace=True)

date = "2025-08-22"
start_time = "09:30"
end_time = "16:00"

df = df[df.index.date == pd.to_datetime(date).date()]
df = df.between_time(start_time, end_time)


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

# Summary
print("Strategy final value:", df['cum_strategy'].iloc[-1])
print("Market final value:", df['cum_market'].iloc[-1])

# profit plot
plt.figure(figsize=(12,6))
plt.plot(df.index, df['cum_strategy'], label='Strategy', color='blue')
plt.plot(df.index, df['cum_market'], label='Market', color='orange')
plt.xlabel("Time")
plt.ylabel("Cumulative Profit")
plt.title(f"{symbol} Strategy vs Market ({date})")
plt.legend()
plt.grid(True)
plt.show()