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

        with open("config.json") as f:
            config = json.load(f)
        self.api_key = config['api_key']
        self.app_key = config['app_key']
        self.app_secret = config['app_secret']

        self.polygon_client = RESTClient(self.api_key)
        self.client = schwabdev.Client(self.app_key, self.app_secret)
        self.streamer = self.client.stream

        self.timezone = ZoneInfo("America/New_York")


    def polygon_historical_data(self, symbol='TSLA', from_date='2024-09-01', to_date='2025-08-31',
                                timespan='minute', multiplier=1, max_iter=5):
        data_list = []
        current_from = from_date

        for _ in range(max_iter):
            aggs = self.polygon_client.get_aggs(
                symbol,
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
                    'volume': agg.volume
                })

            last_ts = pd.to_datetime(rows[-1].timestamp, unit='ms', utc=True)
            current_from = (last_ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        df = pd.DataFrame(data_list)

        self.save_data(df, f"{symbol}_historical_data.csv")


    def historical_data(self, symbol='TSLA', periodType="day", period=10, frequencyType="minute", frequency=1, 
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

        self.save_data(df, f"{symbol}_historical_data.csv")


    def stream_data(self, symbol, duration=100):
        df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'timestamp'])

        def response_handler(response):
            data = json.loads(response).get("data", [])
            nonlocal df

            if not data:
                return

            for item in data:
                content = item["content"][0]
                row = {
                    "timestamp": item["timestamp"],
                    "open": content.get("2"),
                    "high": content.get("3"),
                    "low": content.get("4"),
                    "close": content.get("5"),
                    "volume": content.get("6")
                }
                df.loc[len(df)] = pd.Series(row, index=df.columns)

                print(f"Timestamp: {row['timestamp']}, "
                    f"Open: {row['open']}, "
                    f"High: {row['high']}, "
                    f"Low: {row['low']}, "
                    f"Close: {row['close']}, "
                    f"Volume: {row['volume']}")
            
        self.streamer.start(response_handler)
        
        self.streamer.send(self.streamer.chart_equity(symbol, "0,1,2,3,4,5,6", command="SUBS"))
        time.sleep(duration) # stream duration
        
        self.streamer.stop()

        self.save_data(df, f"{symbol}_streamed_data.csv")


    def save_data(self, df, filename):
        df = df.drop_duplicates(subset=["timestamp"])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        df.index = df.index.tz_convert(self.timezone)

        file_path = os.path.join(self.data_path, filename)
        df.to_csv(file_path, index=True)
        print(f"Saved CSV to {file_path}")


    def open_data(self, symbol, date="", start_time="9:30", end_time="16:00"):
        file_path = os.path.join(self.data_path, f"{symbol}_historical_data.csv")
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, utc=True)
        df.index = df.index.tz_convert(self.timezone)

        if date != "":
            df = df[df.index.date == pd.to_datetime(date).date()]
        df = df.between_time(start_time, end_time)

        return df
    