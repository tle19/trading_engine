import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import schwabdev
from polygon import RESTClient

from utils import *

class DataHandler:
    def __init__(self):
        config = load_config()
        self.data_path = config['data_path']
        if not os.path.exists(self.data_path):
            os.mkdir(self.data_path)

        self.api_key = config['api_key']
        self.app_key = config['app_key']
        self.app_secret = config['app_secret']

        self.polygon_client = RESTClient(self.api_key)
        self.client = schwabdev.Client(self.app_key, self.app_secret)
        self.streamer = self.client.stream

        self.timezone = ZoneInfo("America/New_York")


    def historical_data(self, symbol='SPY', from_date='2023-10-15', to_date='2025-10-15',
                                timespan='minute', multiplier=1, max_iter=10):

        data_list = []
        current_from = from_date

        if "/" in symbol:
            base, quote = symbol.split("/")
            polygon_symbol = f"C:{base}{quote}"
        elif symbol.upper().endswith("USD") and not symbol.startswith(("C:", "X:")):
            polygon_symbol = f"X:{symbol.upper()}"
        else:
            polygon_symbol = symbol  # equity or already formatted

        for _ in range(max_iter):
            print(current_from)
            print("     |")
            print("     v")
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
            if current_from > pd.to_datetime(to_date).strftime("%Y-%m-%d"):
                break
            # Respect Polygon's rate limit (5 calls/minute)
            time.sleep(13)

        df = pd.DataFrame(data_list)
        save_data(df, symbol)


    def schwab_data(self, symbol='SPY', periodType="month", period=6, frequencyType="daily", frequency=1, 
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

        save_data(df, symbol)

        return df


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
