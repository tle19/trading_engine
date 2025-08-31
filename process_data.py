import pandas as pd
import os
import mplfinance as mpf

symbol = "TSLA"

df = pd.read_csv(f"{symbol}_historical_data.csv")
df['datetime'] = pd.to_datetime(df['datetime'])
df.set_index('datetime', inplace=True)

df = df[['open', 'high', 'low', 'close', 'volume']]

mpf.plot(df, type='candle', style='charles', volume=True, title='AMD Minute Candles')

# df = df.sort_values('datetime')
# split_index = int(len(df) * 0.8)

# train_df = df.iloc[:split_index]
# test_df = df.iloc[split_index:]


# high_mean = df['high'].mean()
# low_mean = df['low'].mean()

# high_max = df['high'].max()
# low_min = df['low'].min()

# print(train_df)
# print(test_df)