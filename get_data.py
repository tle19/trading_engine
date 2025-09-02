import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import schwabdev


class DataHandler:
    def __init__(self, data_path="data"):
        self.data_path = data_path
        if not os.path.exists(self.data_path):
            os.mkdir(self.data_path)

        with open("config.json") as f:
            config = json.load(f)
        self.app_key = config['app_key']
        self.app_secret = config['app_secret']

        self.client = schwabdev.Client(self.app_key, self.app_secret)
        self.streamer = self.client.stream

        self.timezone = ZoneInfo("America/New_York")

    def historical_data(self, symbol='TSLA', periodType="day", period=10, frequencyType="minute", frequency=1, 
                       startDate=None, endDate=None, needExtendedHoursData=None, needPreviousClose=None):

        raw_data = self.client.price_history(
            symbol=symbol, 
            periodType=periodType, 
            period=period, 
            frequencyType=frequencyType, 
            frequency=frequency, 
            startDate=startDate,
            endDate=endDate, 
            needExtendedHoursData=needExtendedHoursData, 
            needPreviousClose=needPreviousClose
        )

        full_str = b"".join(raw_data).decode("utf-8")
        data = json.loads(full_str)
        df = pd.DataFrame(data.get("candles", []))

        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms') \
                            .dt.tz_localize('UTC') \
                            .dt.tz_convert(self.timezone)
        
        self.save_data(df, f"{symbol}_historical_data.csv")

    def stream_data(self, symbol, duration=100):
        df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume' ,'datetime'])

        def response_handler(response):
            data = json.loads(response).get("data", [])

            nonlocal df

            if not data:
                return 
            for item in data:
                content = item["content"][0]
                row = {
                    "open": content.get("17"),
                    "high": content.get("10"),
                    "low": content.get("11"),
                    "close": content.get("12"),
                    "volume": content.get("8"),
                    "datetime": pd.to_datetime(item["timestamp"], unit='ms').tz_localize('UTC').tz_convert(self.timezone)
                }
                df.loc[len(df)] = row
            
            curr = df.iloc[-1]
            print(f"Datetime: {curr['datetime']}, "
                f"Open: {curr['open']}, "
                f"High: {curr['high']}, "
                f"Low: {curr['low']}, "
                f"Close: {curr['close']}, "
                f"Volume: {curr['volume']}")
            
        self.streamer.start(response_handler)
        self.streamer.send(self.streamer.level_one_equities(symbol, "0,8,10,11,12,17", command="ADD"))
        
        time.sleep(duration) # stream duration
        self.streamer.stop()

        self.save_data(df, f"{symbol}_streamed_data.csv")


    def save_data(self, df, filename):
        file_path = os.path.join(self.data_path, filename)
        df.to_csv(file_path, index=False)
        print(f"Saved CSV to {file_path}")

    
