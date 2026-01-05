import os
import json
import time
import pandas as pd
from collections import namedtuple
from datetime import datetime
from zoneinfo import ZoneInfo

import schwabdev
from polygon import RESTClient

from utils import *

class DataHandler:
    def __init__(self):
        config = load_config()
        os.makedirs(config['data_path'], exist_ok=True)

        self.polygon_client = RESTClient(config['api_key'])
        self.client = schwabdev.Client(config['app_key'], config['app_secret'])
        self.streamer = self.client.stream

        self.timezone = ZoneInfo("America/New_York")
        self.Equity_Row = namedtuple("Row", ["timestamp", "open", "high", "low", "close", "volume"])
        self.Forex_Row = namedtuple("Row", ["timestamp", "bid", "ask", "last", "bid_size", "ask_size", "volume"])

    def historical_data(self, symbol='SPY', from_date='2023-11-01', to_date='2025-11-01',
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

            last_ts = pd.to_datetime(rows[-1].timestamp, unit='ms', utc=True)
            last_date = last_ts.date()

            for agg in rows:
                ts_date = pd.to_datetime(agg.timestamp, unit='ms', utc=True).date()
                if ts_date == last_date:
                    break
                data_list.append({
                    'timestamp': agg.timestamp,
                    'open': agg.open,
                    'high': agg.high,
                    'low': agg.low,
                    'close': agg.close,
                    'volume': getattr(agg, "volume", 0)
                })

            # Advance current_from beyond last fetched bar
            current_from = last_ts.strftime("%Y-%m-%d")
            if current_from > pd.to_datetime(to_date).strftime("%Y-%m-%d"):
                break
            
            time.sleep(13) # Polygon.io rate limit (5 calls/minute)

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
            startDate=startDate,
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
        def equity_handler(response):
            data = json.loads(response).get("data", [])
            if not data:
                return
            
            content = data[0].get("content")
            if not content:
                return
            for item in content:
                symbol = item["key"]

                timestamp = pd.to_datetime(item.get("7"), unit='ms', utc=True).tz_convert(self.timezone)
                open = item.get("2")
                high = item.get("3")
                low = item.get("4")
                close = item.get("5")
                volume = item.get("6")

                row = self.Equity_Row(timestamp, open, high, low, close, volume)
                print(f"{symbol}: {row}")

        def forex_handler(response):
            data = json.loads(response).get("data", [])
            if not data:
                return

            content = data[0].get("content")
            if not content:
                return
            for item in data:
                symbol = item["key"]

                timestamp = pd.to_datetime(item.get("7"), unit='ms', utc=True).tz_convert(self.timezone)
                bid = item.get("1")
                ask = item.get("2")
                last = item.get("3")
                bid_size = item.get("4")
                ask_size = item.get("5")
                volume = item.get("6")

                row = self.Forex_Row(timestamp, bid, ask, last, bid_size, ask_size, volume)
                print(f"{symbol}: {row}")
                
        if "/" in symbol:
            self.streamer.start(forex_handler)
            self.streamer.send(self.streamer.level_one_forex(symbol, "0,1,2,3,4,5,6,7,8", command="SUBS"))  
            time.sleep(duration)
            self.streamer.stop()
        else:
            self.streamer.start(equity_handler)
            self.streamer.send(self.streamer.chart_equity(symbol, "0,1,2,3,4,5,6,7,8", command="SUBS"))
            time.sleep(duration)
            self.streamer.stop()
