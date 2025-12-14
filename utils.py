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

def trade_history_to_csv(log_file="trade_logs.json", csv_file="trade_history.csv"):
    with open(log_file, "r") as f:
        data = json.load(f)

    trade_history = []
    for trade in data.get("trade_history", []):
        trade_copy = trade.copy()
        for key in ["entry_time", "exit_time"]:
            if key in trade_copy and trade_copy[key] is not None:
                trade_copy[key] = pd.Timestamp(trade_copy[key])

        features = trade_copy.pop("features", {})
        for feat_name, feat_val in features.items():
            if isinstance(feat_val, list):
                for i, v in enumerate(feat_val, start=1):
                    trade_copy[f"{feat_name}_{i}"] = v
            else:
                trade_copy[feat_name] = feat_val

        trade_history.append(trade_copy)

    df = pd.DataFrame(trade_history)
    df.to_csv(csv_file, index=False)
    print(df)
    print(f"Saved {len(df)} trades to {csv_file}")

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