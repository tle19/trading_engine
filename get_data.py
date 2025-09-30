import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import schwabdev
from polygon import RESTClient


class DataHandler:
    def __init__(self, data_path="data"):
        self.data_path = data_path
        if not os.path.exists(self.data_path):
            os.mkdir(self.data_path)

        # save keys in json
        with open("config.json") as f:
            config = json.load(f)
        self.api_key = config['api_key']
        self.app_key = config['app_key']
        self.app_secret = config['app_secret']

        self.polygon_client = RESTClient(self.api_key)
        self.client = schwabdev.Client(self.app_key, self.app_secret)
        self.streamer = self.client.stream

        self.timezone = ZoneInfo("America/New_York")

    def historical_data(self, symbol='GOOG', from_date='2023-09-01', to_date='2025-09-01',
                                timespan='minute', multiplier=2, max_iter=12):

        data_list = []
        current_from = from_date

        if "/" in symbol:
            base, quote = symbol.split("/")
            polygon_symbol = f"C:{base}{quote}"
        elif symbol.upper().endswith("USD") and not symbol.startswith(("C:", "X:")):
            polygon_symbol = f"X:{symbol.upper()}"
        else:
            polygon_symbol = symbol  # stock or already formatted

        for _ in range(max_iter):
            print(current_from, "--->")
            aggs = self.polygon_client.get_aggs(
                polygon_symbol,
                multiplier,
                timespan,
                current_from,
                to_date,
                limit=50000
            )

            rows = list(aggs)
            if not rows:
                break

            for agg in rows:
                data_list.append({
                    'timestamp': agg.timestamp,
                    'open': agg.open,
                    'high': agg.high,
                    'low': agg.low,
                    'close': agg.close,
                    'volume': getattr(agg, "volume", 0)
                })

            # Advance current_from beyond last fetched bar
            last_ts = pd.to_datetime(rows[-1].timestamp, unit='ms', utc=True)
            current_from = (last_ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

            # Respect Polygon's rate limit (5 calls/minute)
            time.sleep(13)

        df = pd.DataFrame(data_list)
        self.save_data(df, symbol)

    def schwab_historical_data(self, symbol='TSLA', periodType="day", period=10, frequencyType="minute", frequency=1, 
                       startDate=None, endDate=None, needExtendedHoursData=None, needPreviousClose=None):

        raw_data = self.client.price_history(
            symbol=symbol, 
            periodType=periodType, 
            period=period, 
            frequencyType=frequencyType, 
            frequency=frequency, 
            startDate=startDate, #datetime(2025, 3, 3)
            endDate=endDate, 
            needExtendedHoursData=needExtendedHoursData, 
            needPreviousClose=needPreviousClose
        )

        full_str = b"".join(raw_data).decode("utf-8")
        data = json.loads(full_str)
        df = pd.DataFrame(data.get("candles", []))

        df.rename(columns={"datetime": "timestamp"}, inplace=True)

        self.save_data(df, symbol)


    def stream_data(self, symbol, duration=300):

        equity_df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'timestamp'])
        forex_df = pd.DataFrame(columns=['bid', 'ask', 'last', 'bid_size', 'ask_size', 'volume', 'timestamp'])

        def equity_handler(response):
            data = json.loads(response).get("data", [])
            nonlocal equity_df

            if not data:
                return

            for item in data:
                content = item["content"][0]
                timestamp = pd.to_datetime(item['timestamp'], unit='ms').tz_localize("UTC").tz_convert(self.timezone)
                row = {
                    "timestamp": timestamp,
                    "open": content.get("2"),
                    "high": content.get("3"),
                    "low": content.get("4"),
                    "close": content.get("5"),
                    "volume": content.get("6")
                }
                equity_df.loc[len(equity_df)] = pd.Series(row, index=equity_df.columns)
                print(f"Timestamp: {timestamp}, "
                    f"Open: {row['open']}, "
                    f"High: {row['high']}, "
                    f"Low: {row['low']}, "
                    f"Close: {row['close']}, "
                    f"Volume: {row['volume']}")

        def forex_handler(response):
            data = json.loads(response).get("data", [])
            nonlocal forex_df

            if not data:
                return

            for item in data:
                content = item["content"][0]
                timestamp = pd.to_datetime(item['timestamp'], unit='ms').tz_localize("UTC").tz_convert(self.timezone)
                row = {
                    "timestamp": timestamp,
                    "bid": content.get("1"),
                    "ask": content.get("2"),
                    "last": content.get("3"),
                    "bid_size": content.get("4"),
                    "ask_size": content.get("5"),
                    "volume": content.get("6")
                }
                forex_df.loc[len(forex_df)] = pd.Series(row, index=forex_df.columns)
                print(f"Timestamp: {timestamp}, "
                    f"Bid: {row['bid']}, "
                    f"Ask: {row['ask']}, "
                    f"Last: {row['last']}, "
                    f"Bid Size: {row['bid_size']}, "
                    f"Ask Size: {row['ask_size']}, "
                    f"Volume: {row['volume']}")
                
        if "/" in symbol:
            self.streamer.start(forex_handler)
            self.streamer.send(self.streamer.level_one_forex(symbol, "0,1,2,3,4,5,6,7", command="SUBS"))
            
            time.sleep(duration)

            self.streamer.stop()
        else:
            self.streamer.start(equity_handler)
            self.streamer.send(self.streamer.chart_equity(symbol, "0,1,2,3,4,5,6", command="SUBS"))

            time.sleep(duration)

            self.streamer.stop()


    def save_data(self, df, symbol):
        df = df.drop_duplicates(subset=["timestamp"])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df["timestamp"] = df["timestamp"].dt.tz_convert(self.timezone)

        file_path = os.path.join(self.data_path, f"{symbol}_historical_data.csv")
        df.to_csv(file_path, index=False)
        print(f"Saved CSV to {file_path}")

    
    def open_data(self, symbol, start_date=None, end_date=None, start_time="9:30", end_time="16:00"):
        file_path = os.path.join(self.data_path, f"{symbol}_historical_data.csv")
        df = pd.read_csv(file_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["timestamp"] = df["timestamp"].dt.tz_convert(self.timezone)

        if start_date is not None and end_date is not None:
            mask = (df['timestamp'].dt.date >= pd.to_datetime(start_date).date()) & \
                    (df['timestamp'].dt.date <= pd.to_datetime(end_date).date())
            df = df.loc[mask]

        df = df.set_index('timestamp').between_time(start_time, end_time).reset_index()

        return df

    