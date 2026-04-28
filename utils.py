import os
import json
import pandas as pd
import datetime
import zoneinfo

SEC_FEE_RATE = 0.0000206 # 20.60 per 1 000 000

data_path = "data"
timezone = zoneinfo.ZoneInfo("America/New_York")

def load_config(config_path="configs/api_config.json"):
    with open(config_path) as f:
        config = json.load(f)
    return config

def save_data(df, symbol, mode="intraday"):
    df = df.drop_duplicates(subset=["timestamp"])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert(timezone)

    folder = os.path.join(data_path, mode)
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, f"{symbol}_{mode}.csv")

    df.to_csv(file_path, index=False)
    print(f"Saved data to {file_path}")

def open_data(symbol, start_date=None, end_date=None, mode="intraday"):
    folder = os.path.join(data_path, mode)
    file_path = os.path.join(folder, f"{symbol}_{mode}.csv")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"[WARN] Missing CSV for {symbol}: {file_path}")
    
    df = pd.read_csv(file_path)

    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", utc=True).dt.tz_convert(timezone)
    if start_date is not None and end_date is not None:
        mask = (df['timestamp'].dt.date >= pd.to_datetime(start_date).date()) & \
                (df['timestamp'].dt.date <= pd.to_datetime(end_date).date())
        df = df.loc[mask]

    return df

def convert_epoch_ms(ts):
    return datetime.datetime.fromtimestamp(ts / 1000, tz=timezone)

def resample_data(df, type="1D"): # 1min, 5min, 1H, 4H, 1D, 1W, 1M
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
        })
        .dropna()
        .reset_index()
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