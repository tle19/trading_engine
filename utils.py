import os
import json
import time
import pandas as pd
from zoneinfo import ZoneInfo

import schwabdev

data_path = "data"
timezone = ZoneInfo("America/New_York")

def load_config():
    with open("configs/api_config.json") as f:
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

def allocate_positions(symbols_with_size, cash=25_000):
    weights = {s.upper(): float(v) for s, v in (item.split(":") for item in symbols_with_size)}
    total_weight = sum(weights.values())
    if total_weight == 0:
        raise ValueError("Total of position sizes cannot be zero.")

    config = load_config()
    client = schwabdev.Client(config['app_key'], config['app_secret'])
    streamer = client.stream

    latest_prices = {}
    def response_handler(message):
        data = json.loads(message).get("data", [])
        if not data:
            return
        
        for content in data[0].get("content", []):
            latest_prices[content["key"]] = content.get("3")
    
    symbols = list(weights.keys())
    streamer.start(response_handler)
    streamer.send(streamer.level_one_equities(symbols, "0,3"))
    time.sleep(1)
    streamer.stop()

    shares_to_buy = {}
    for symbol in symbols:
        weight = weights[symbol]
        cash_for_symbol = cash * (weight / total_weight)
        price = latest_prices[symbol]
        shares = int(cash_for_symbol // price)
        shares_to_buy[symbol] = shares

    print(shares_to_buy)