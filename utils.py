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


class TradeLogger:
    def __init__(self, log_file="trade_logs.json"):
        self.open_trades = {}
        self.trade_history = []
        self.log_file = log_file

        try:
            with open("trade_logs.json", "r") as f:
                self.trade_history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.trade_history = []

    def log_entry(self, symbol, position, shares, entry_time, entry_price, fill_price):
        trade = {
            "symbol": symbol,
            "position": position,
            "shares": shares,
            "entry_time": entry_time.isoformat(),
            "entry_price": entry_price,
            "entry_fill": fill_price,
            "exit_time": None,
            "exit_price": None,
            "exit_fill": None,
            "pnl_real": None,
            "pnl_real_pct": None,
            "pnl_theoretical": None,
            "pnl_theoretical_pct": None,
            "regime": None
        }

        self.open_trades[symbol] = trade
    
    def update_exit(self, symbol, position, shares, exit_time, exit_price, fill_price):
        if symbol not in self.open_trades:
            raise ValueError(f"No open trade for symbol {symbol}")

        trade = self.open_trades.pop(symbol)
        trade["exit_time"] = exit_time.isoformat()
        trade["exit_price"] = exit_price
        trade["exit_fill"] = fill_price

        if position == "long":
            trade["pnl_real"] = (fill_price - trade["entry_fill"]) * shares
            trade["pnl_theoretical"] = (exit_price - trade["entry_price"]) * shares
        elif position == "short":
            trade["pnl_real"] = (trade["entry_fill"] - fill_price) * shares
            trade["pnl_theoretical"] = (trade["entry_price"] - exit_price) * shares

        trade["pnl_real"] = round(trade["pnl_real"], 2)
        trade["pnl_real_pct"] = round(trade["pnl_real"] / trade["entry_fill"] * 100, 2)
        trade["pnl_theoretical"] = round(trade["pnl_theoretical"], 2)
        trade["pnl_theoretical_pct"] = round(trade["pnl_theoretical"] / trade["entry_price"] * 100, 2)

        self.trade_history.append(trade)

    def output_logs(self):
        with open(self.log_file, "w") as f:
            json.dump(self.trade_history, f, indent=4)
        print(f"Saved {len(self.trade_history)} trades to {self.log_file}")