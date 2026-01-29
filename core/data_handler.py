import os
import json
import time
import pandas as pd
from datetime import date, datetime, timedelta
from collections import namedtuple

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
        self.stream = schwabdev.Stream(self.client)

        self.timezone = ZoneInfo("America/New_York")
        self.ohlcv_Row = namedtuple("Row", ["timestamp", "open", "high", "low", "close", "volume"])
        self.bidask_Row = namedtuple("Row", ["timestamp", "bid", "ask", "last", "bid_size", "ask_size", "volume"])

    def historical_data(self, symbols=['SPY'], from_date='2024-01-01', to_date='2026-01-01',
                                timespan='minute', multiplier=1, max_iter=10):
        start_time = time.perf_counter()

        now = datetime.now()
        if now.hour >= 19:
            to_date = date.today()
        else:
            to_date = date.today() - timedelta(days=1)
        to_date = str(to_date)
        
        for symbol in symbols:
            data_list = []
            df = pd.DataFrame()
            current_from = from_date

            try:
                df = open_data(symbol, start_time="0:00", end_time="23:59")
                last_ts = df['timestamp'].iloc[-1]
                current_from = (last_ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                print(f"[{symbol}] Existing data found: fetching from {current_from} → {to_date}")
            except FileNotFoundError:
                print(f"[{symbol}] No existing data: fetching from {current_from} → {to_date}")

            if "/" in symbol:
                base, quote = symbol.split("/")
                symbol = f"C:{base}{quote}"
            elif symbol.upper().endswith("USD") and not symbol.startswith(("C:", "X:")):
                symbol = f"X:{symbol.upper()}"
            else:
                pass  # equity or already formatted

            for _ in range(max_iter):
                print(f"   batch starting {current_from} → ...")
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

                current_from = last_ts.strftime("%Y-%m-%d")
                if current_from > pd.to_datetime(to_date).strftime("%Y-%m-%d"):
                    break
                
                time.sleep(12.5) # Polygon.io rate limit (5 calls/minute)
            
            if data_list:
                new_df = pd.DataFrame(data_list)
                new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms', utc=True)
                new_df['timestamp'] = new_df['timestamp'].dt.tz_convert(self.timezone)
                df = pd.concat([df, new_df], ignore_index=True)
                df.drop_duplicates(subset='timestamp', inplace=True)
                df.sort_values('timestamp', inplace=True)
                df.reset_index(drop=True, inplace=True)

            save_data(df, symbol)

        elapsed_time = time.perf_counter() - start_time
        print(f"Elapsed Data Fetch Time: {elapsed_time:.6f} seconds")

    def schwab_data(self, symbols=['SPY'], periodType="month", period=6, frequencyType="daily", frequency=1, 
                       startDate=None, endDate=None, needExtendedHoursData=None, needPreviousClose=None):
        start_time = time.perf_counter()
        endDate = str(date.today())

        for symbol in symbols:
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

        elapsed_time = time.perf_counter() - start_time
        print(f"Elapsed Data Fetch Time: {elapsed_time:.6f} seconds")

    def stream_data(self, symbols, duration=300):
        def equity_handler(response):
            data = json.loads(response).get("data", [])
            if not data:
                return
            
            for entry in data:
                content = entry["content"]
                for item in content:
                    symbol = item["key"]

                    timestamp = pd.to_datetime(item.get("7"), unit='ms', utc=True).tz_convert(self.timezone)
                    open = item.get("2")
                    high = item.get("3")
                    low = item.get("4")
                    close = item.get("5")
                    volume = item.get("6")

                    row = self.ohlcv_Row(timestamp, open, high, low, close, volume)
                    print(f"[{symbol}] {row}")

        def forex_handler(response):
            data = json.loads(response).get("data", [])
            if not data:
                return

            for entry in data:
                content = entry["content"]
                for item in content:
                    symbol = item["key"]

                    timestamp = pd.to_datetime(item.get("8"), unit='ms', utc=True).tz_convert(self.timezone)
                    bid = item.get("1")
                    ask = item.get("2")
                    last = item.get("3")
                    bid_size = item.get("4")
                    ask_size = item.get("5")
                    volume = item.get("6")

                    row = self.bidask_Row(timestamp, bid, ask, last, bid_size, ask_size, volume)
                    print(f"[{symbol}] {row}")

        def bid_ask_handler(response):
            data = json.loads(response).get("data", [])
            if not data:
                return
            
            for entry in data:
                content = entry["content"]
                for item in content:
                    symbol = item["key"]

                    ts = item.get('34') or item.get('37') or item.get('38') or item.get('35')
                    timestamp = pd.to_datetime(ts, unit='ms', utc=True).tz_convert(self.timezone)
                    bid = item.get("1")
                    ask = item.get("2")
                    last = item.get("3")
                    bid_size = item.get("4")
                    ask_size = item.get("5")
                    volume = item.get("8")

                    row = self.bidask_Row(timestamp, bid, ask, last, bid_size, ask_size, volume)
                    print(f"[{symbol}] {row}")   

        if "/" in symbols[0]:
            self.stream.start(forex_handler)
            self.stream.send(self.stream.level_one_forex(symbols, "0,1,2,3,4,5,6,7,8", command="SUBS"))  
            time.sleep(duration)
            self.stream.stop()
        else:
            self.stream.start(equity_handler)
            self.stream.send(self.stream.chart_equity(symbols, "0,1,2,3,4,5,6,7", command="SUBS"))
            time.sleep(duration)
            self.stream.stop()
        # else:
        #     self.stream.start(bid_ask_handler)
        #     self.stream.send(self.stream.level_one_equities(symbols, "0,1,2,3,4,5,6,7,8,34,35,37,38", command="SUBS"))
        #     time.sleep(duration)
        #     self.stream.stop()
    
    def get_quote(self, symbols):
        response = self.client.quotes(symbols)
        data = response.json()
        if not data:
            return

        for symbol in symbols:
            quote = data.get(symbol, {}).get("quote", {})

            timestamp = pd.to_datetime(quote['quoteTime'], unit='ms', utc=True).tz_convert(timezone)
            bid = quote['bidPrice']
            ask = quote['askPrice']
            last = quote['lastPrice']
            bid_size = quote['bidSize']
            ask_size = quote['askSize']
            volume = quote['totalVolume']

            row = self.bidask_Row(timestamp, bid, ask, last, bid_size, ask_size, volume)
            print(f"[{symbol}] {row}")
