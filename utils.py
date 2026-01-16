import os
import json
import time
import pandas as pd
import numpy as np
from zoneinfo import ZoneInfo

import schwabdev

data_path = "data"
timezone = ZoneInfo("America/New_York")

def load_config(config_path="configs/api_config.json"):
    with open(config_path) as f:
        config = json.load(f)
    return config

def save_data(df, symbol):
    df = df.drop_duplicates(subset=["timestamp"])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df["timestamp"] = df["timestamp"].dt.tz_convert(timezone)

    file_path = os.path.join(data_path, f"{symbol}_historical_data.csv")
    df.to_csv(file_path, index=False)
    print(f"Saved CSV to {file_path}")

def open_data(symbol, start_date=None, end_date=None, start_time="9:30", end_time="15:59"):
    file_path = os.path.join(data_path, f"{symbol}_historical_data.csv")
    df = pd.read_csv(file_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["timestamp"] = df["timestamp"].dt.tz_convert(timezone)

    if start_date is not None and end_date is not None:
        mask = (df['timestamp'].dt.date >= pd.to_datetime(start_date).date()) & \
                (df['timestamp'].dt.date <= pd.to_datetime(end_date).date())
        df = df.loc[mask]

    df = df.set_index('timestamp').between_time(start_time, end_time).reset_index()
    return df

def resample_data(df, type="1D"):
    df = df.set_index("timestamp")
    df = (df.resample(
            type,
            offset="9h30min",
            label="left",
            closed="left"
        ).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna()
    )
    return df

def train_test_split(df, n_months=18, datetime_column="entry_time", target_column="target"):
    df = df.sort_values(datetime_column)
    df[datetime_column] = pd.to_datetime(df[datetime_column])

    train_start = df[datetime_column].min()
    train_end = train_start + pd.DateOffset(months=n_months)
    print(f"Train Start: {train_start.date()} Train End: {train_end.date()}")

    train_df = df[(df[datetime_column] < train_end)].drop(columns=[datetime_column])
    test_df = df[(df[datetime_column] >= train_end)].drop(columns=[datetime_column])

    X_train = train_df.drop(columns=[target_column])
    y_train = train_df[target_column]
    X_test  = test_df.drop(columns=[target_column])
    y_test  = test_df[target_column]

    return X_train, X_test, y_train, y_test

def fetch_latest_prices(symbols):
    config = load_config()
    client = schwabdev.Client(config["app_key"], config["app_secret"])
    stream = schwabdev.Stream(client)

    prices = {}
    def response_handler(message):
        data = json.loads(message).get("data", [])
        if not data:
            return
        
        content = data[0].get("content")
        if not content:
            return
        for item in content:
            prices[item["key"]] = float(item.get("3"))

    stream.start(response_handler)
    stream.send(stream.level_one_equities(symbols, "0,3", command="SUBS"))
    time.sleep(3)
    stream.stop()
    time.sleep(1)

    print("Current Prices:", prices)
    return prices

def get_average_spread(symbols, start_date="2023-10-02", end_date="2024-10-02"):
    for symbol in symbols:
        data = open_data(symbol, start_date=start_date, end_date=end_date)
        data["spread"] = data["high"] - data["low"]
        data["normalized_spread"] = data["spread"] / data["close"]
        avg_spread = data["normalized_spread"].mean()
        print(symbol, avg_spread)

def train_model(model, strategy, symbol):
    mdl = model(symbol=symbol, strategy=strategy.__name__, live=False)
    mdl.initialize()
    X_train, _, y_train, _ = train_test_split(mdl.df, n_months=24)
    mdl.train(X_train, y_train)
    mdl.save_model()

def current_drawdown(intraday_equity):
    curr_max = max(intraday_equity)
    current = intraday_equity[-1]
    drawdown = (curr_max - current) / curr_max
    return drawdown

def equity_slope(intraday_equity, lookback=10):
    df = pd.DataFrame(list(intraday_equity.items()), columns=['timestamp', 'equity'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    start_time = df['timestamp'].iloc[-1] - pd.Timedelta(days=lookback)
    df = df[df['timestamp'] >= start_time]
    x = (df['timestamp'] - df['timestamp'].iloc[0]).dt.total_seconds()
    y = df['equity'].values
    return np.polyfit(x, y, 1)[0]
    
def drawdown_rebalance(drawdown, slope, day_rebalance=7):
    if drawdown > 0.05:
        days = 3
    else:
        days = day_rebalance
    return days

        