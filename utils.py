import os
import json
import time
import pandas as pd
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

def open_data(symbol, start_date=None, end_date=None, start_time="9:30", end_time="16:00"):
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

def train_test_split(df, n_months=18, datetime_column="entry_time", target_column="target"):
    df = df.sort_values(datetime_column)
    df[datetime_column] = pd.to_datetime(df[datetime_column])

    split_date = df[datetime_column].max() - pd.DateOffset(months=n_months)

    train_df = df[df[datetime_column] < split_date].drop(columns=[datetime_column])
    test_df  = df[df[datetime_column] >= split_date].drop(columns=[datetime_column])

    X_train = train_df.drop(columns=[target_column])
    y_train = train_df[target_column]
    X_test  = test_df.drop(columns=[target_column])
    y_test  = test_df[target_column]

    return X_train, X_test, y_train, y_test

def fetch_latest_prices(symbols):
    config = load_config()
    client = schwabdev.Client(config["app_key"], config["app_secret"])
    streamer = client.stream

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

    streamer.start(response_handler)
    streamer.send(streamer.level_one_equities(symbols, "0,3", command="SUBS"))
    time.sleep(3)
    streamer.stop()
    time.sleep(1)

    print("Current Prices:", prices)
    return prices

def get_symbol_positions():
    raise NotImplementedError

def allocate_positions(symbols_with_size, prices, cash=25_000):
    weights = {s.upper(): float(v) for s, v in (item.split(":") for item in symbols_with_size)}
    total_weight = sum(weights.values())
    if total_weight == 0:
        raise ValueError("Total of position sizes cannot be zero.")
    elif total_weight < 1.0:
        total_weight = 1.0
    
    symbols = list(weights.keys())

    shares_to_buy = {}
    for symbol in symbols:
        weight = weights[symbol]
        cash_for_symbol = cash * (weight / total_weight)
        price = prices[symbol]
        shares = int(cash_for_symbol // price)
        shares_to_buy[symbol] = shares

    print("Allocated positions:", shares_to_buy)
    return shares_to_buy