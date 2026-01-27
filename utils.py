import os
import json
import time
import pandas as pd
from zoneinfo import ZoneInfo
from collections import namedtuple

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
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"[WARN] Missing CSV for {symbol}: {file_path}")
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

def train_test_split(df, n_days=540, datetime_column="entry_time", target_column="target"):
    df = df.sort_values(datetime_column)
    df[datetime_column] = pd.to_datetime(df[datetime_column])

    train_start = df[datetime_column].min()
    train_end = train_start + pd.DateOffset(days=n_days)
    print(f"Train Start: {train_start.date()} Train End: {train_end.date()}")

    train_df = df[(df[datetime_column] < train_end)].drop(columns=[datetime_column])
    test_df = df[(df[datetime_column] >= train_end)].drop(columns=[datetime_column])

    X_train = train_df.drop(columns=[target_column])
    y_train = train_df[target_column]
    X_test  = test_df.drop(columns=[target_column])
    y_test  = test_df[target_column]

    return X_train, X_test, y_train, y_test