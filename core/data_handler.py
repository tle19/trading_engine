import json
import time
import numpy as np
import pandas as pd
import datetime
import orjson

import polygon
import schwabdev

from utils import *

class DataHandler:
    def __init__(self):
        config = load_config()

        self.polygon_client = polygon.RESTClient(config['api_key'])
        self.client = schwabdev.Client(config['app_key'], config['app_secret'])
        self.stream = schwabdev.Stream(self.client)
        self.hash = self.client.linked_accounts().json()[0].get('hashValue')
        
        self.ohlcv_row = OHLCVRow()
        self.level1_row = Level1Row()
        self.level2_row = Level2Row()

    def intraday_data(self, symbols=['SPY'], from_date='2024-01-01', to_date='2026-01-01',
                                timespan='minute', multiplier=1, max_iter=10):
        start_time = time.perf_counter()

        now = datetime.datetime.now(timezone)
        to_date = str((now - datetime.timedelta(days=1)).date())
        
        for symbol in symbols:
            data_list = []

            try:
                df = open_data(symbol, mode="intraday")
                last_ts = df['timestamp'].iloc[-1]
                current_from = (last_ts).strftime("%Y-%m-%d")
                print(f"[{symbol}] Existing data found: fetching from {current_from} → {to_date}")
            except FileNotFoundError:
                df = pd.DataFrame()
                current_from = from_date
                print(f"[{symbol}] No existing data: fetching from {current_from} → {to_date}")

            if "/" in symbol:
                base, quote = symbol.split("/")
                symbol = f"C:{base}{quote}"
            elif symbol.upper().endswith("USD") and not symbol.startswith(("C:", "X:")):
                symbol = f"X:{symbol.upper()}"
            else:
                pass  # equity or already formatted

            for i in range(max_iter):
                aggs = self.polygon_client.get_aggs(
                    symbol,
                    multiplier,
                    timespan,
                    current_from,
                    to_date,
                    limit=50000
                )
                time.sleep(13) # Polygon.io rate limit (5 calls/minute)

                rows = list(aggs)
                if not rows:
                    break
                
                last_ts = pd.to_datetime(rows[-1].timestamp, unit='ms', utc=True)
                last_date = last_ts.date()
                print(f"{' ' * (len(symbol) + 3)}Batch {i} | {current_from} → {last_date}")
                
                for agg in rows:
                    ts_date = pd.to_datetime(agg.timestamp, unit='ms', utc=True).date()
                    if ts_date >= last_date:
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
                if current_from >= pd.to_datetime(to_date).strftime("%Y-%m-%d"):
                    break
                if current_from == pd.to_datetime(last_date).strftime("%Y-%m-%d"):
                    break
            
            if data_list:
                new_df = pd.DataFrame(data_list)
                new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms', utc=True)
                new_df['timestamp'] = new_df['timestamp'].dt.tz_convert(timezone)
                df = pd.concat([df, new_df], ignore_index=True)
                df.drop_duplicates(subset='timestamp', inplace=True)
                df.sort_values('timestamp', inplace=True)
                df.reset_index(drop=True, inplace=True)

            save_data(df, symbol, mode="intraday")

        elapsed_time = time.perf_counter() - start_time
        print(f"Elapsed Data Fetch Time: {elapsed_time:.3f} seconds")

    def daily_data(self, symbols=['SPY'], periodType="year", period=20, frequencyType="daily", frequency=1, 
                       startDate=None, endDate=None, needExtendedHoursData=None, needPreviousClose=None):
        start_time = time.perf_counter()

        endDate = int(time.time() * 1000)

        for symbol in symbols:
            try:
                df = open_data(symbol, mode="daily")
            except FileNotFoundError:
                df = pd.DataFrame()

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

            new_df = pd.DataFrame(data.get("candles", []))
            new_df.rename(columns={"datetime": "timestamp"}, inplace=True)
            new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms', utc=True)
            new_df['timestamp'] = new_df['timestamp'].dt.tz_convert(timezone)
            df = pd.concat([df, new_df], ignore_index=True)
            df.drop_duplicates(subset='timestamp', inplace=True)
            df.sort_values('timestamp', inplace=True)
            df.reset_index(drop=True, inplace=True)

            save_data(df, symbol, mode="daily")

        elapsed_time = time.perf_counter() - start_time
        print(f"Elapsed Data Fetch Time: {elapsed_time:.3f} seconds")

    def stream_data(self, symbols, service="level1", duration=300):
        feed_latencies = []
        internal_latencies = []
        processing_latencies = []
        def response_handler(response):
            system_receive_time = int(time.time() * 1000)
            data = orjson.loads(response).get("data")
            if not data:
                return
            
            for entry in data:
                service = entry["service"]
                content = entry["content"]
                timestamp = entry["timestamp"]
                for item in content:
                    symbol = item["key"]
                    if service == "CHART_EQUITY":
                        ts = item.get("7") or timestamp
                        row = self.ohlcv_row.update(
                            convert_epoch_ms(ts),
                            item.get("2"),
                            item.get("3"),
                            item.get("4"),
                            item.get("5"),
                            item.get("6")
                        )
                    elif service == "LEVELONE_EQUITIES":
                        ts = item.get('34') or item.get('37') or item.get('38') or item.get('35') or timestamp
                        row = self.level1_row.update(
                            convert_epoch_ms(ts),
                            item.get("1"),
                            item.get("2"),
                            item.get("3"),
                            item.get("4"),
                            item.get("5")
                        )
                    elif service == "NASDAQ_BOOK" or service == "NYSE_BOOK":
                        ts = item.get("1") or timestamp
                        row = self.level2_row.update(
                            convert_epoch_ms(ts),
                            item.get("2"),
                            item.get("3")
                        )
                    elif service == "LEVELONE_FOREX":
                        ts = item.get('8') or timestamp
                        row = self.level1_row.update(
                            convert_epoch_ms(ts),
                            item.get("1"),
                            item.get("2"),
                            item.get("3"),
                            item.get("4"),
                            item.get("5")
                        )

                    print(f"[{symbol}] {row}")

                    feed_latency = timestamp - ts
                    internal_latency = system_receive_time - timestamp
                    processing_latency = (time.time() * 1000) - system_receive_time

                    feed_latencies.append(feed_latency)
                    internal_latencies.append(internal_latency)
                    processing_latencies.append(processing_latency)

                    print(f"  FEED LATENCY (Exchange → API): {feed_latency:.2f} ms")
                    print(f"  INTERNAL LATENCY (API → System): {internal_latency:.2f} ms")
                    print(f"  PROCESSING LATENCY (System → Output): {processing_latency:.2f} ms")

        self.stream.start(response_handler)

        if service == "chart":
            self.stream.send(self.stream.chart_equity(symbols, "0,1,2,3,4,5,6,7", command="SUBS"))
        elif service == "level1":
            self.stream.send(self.stream.level_one_equities(symbols, "0,1,2,3,4,5,34,35,37,38", command="SUBS"))
        elif service == "level2":
            self.stream.send(self.stream.nasdaq_book(symbols, "0,1,2,3,4", command="SUBS"))
        elif service == "forex":
            self.stream.send(self.stream.level_one_forex(symbols, "0,1,2,3,4,5,6,7,8", command="SUBS"))
        else:
            raise ValueError("You must provide a service, e.g. --service chart/level1/level2/forex")

        time.sleep(duration)
        print(f"AVERAGE FEED LATENCY (Exchange → API): {np.mean(feed_latencies):.2f} ms")
        print(f"AVERAGE INTERNAL LATENCY (API → System): {np.mean(internal_latencies):.2f} ms")
        print(f"AVERAGE PROCESSING LATENCY (System → Output): {np.mean(processing_latencies):.2f} ms")
        self.stream.stop()
    
    def get_quote(self, symbols):
        response = self.client.quotes(symbols)
        data = response.json()
        if not data:
            return

        for symbol in symbols:
            content = data[symbol]
            quote = content["quote"]
            reference = content["reference"]

            row = self.level1_row.update(
                convert_epoch_ms(quote['quoteTime']),
                quote['bidPrice'],
                quote['askPrice'],
                quote['lastPrice'],
                quote['bidSize'],
                quote['askSize']
            )

            print(f"[{symbol}] {row}, {"HTB" if reference.get('isHardToBorrow') else "ETB"}")

    def get_order_details(self, order_id):
        details = self.client.order_details(self.hash, order_id)
        details_json = details.json()
        print(details_json)
    
class OHLCVRow:
    __slots__ = ("timestamp", "open", "high", "low", "close", "volume")

    def __init__(self, timestamp=None, open=None, high=None, low=None, close=None, volume=None):
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume

    def update(self, timestamp=None, open=None, high=None, low=None, close=None, volume=None):
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        return self

    def __repr__(self):
        return (
            f"timestamp={self.timestamp}, open={self.open}, high={self.high}, "
            f"low={self.low}, close={self.close}, volume={self.volume}"
        )

class Level1Row:
    __slots__ = ("timestamp", "bid", "ask", "last", "bid_size", "ask_size")

    def __init__(self, timestamp=None, bid=None, ask=None, last=None, bid_size=None, ask_size=None):
        self.timestamp = timestamp
        self.bid = bid
        self.ask = ask
        self.last = last
        self.bid_size = bid_size
        self.ask_size = ask_size

    def update(self, timestamp=None, bid=None, ask=None, last=None, bid_size=None, ask_size=None):
        self.timestamp = timestamp
        self.bid = bid
        self.ask = ask
        self.last = last
        self.bid_size = bid_size
        self.ask_size = ask_size
        return self
    
    def __repr__(self):
        return (f"timestamp={self.timestamp}, bid={self.bid}, ask={self.ask}, "
                f"last={self.last}, bid_size={self.bid_size}, ask_size={self.ask_size}"
            )

class Level2Row:
    __slots__ = ("timestamp", "bid_side", "ask_side")

    def __init__(self, timestamp=None, bid_side=None, ask_side=None):
        self.timestamp = timestamp
        self.bid_side = bid_side
        self.ask_side = ask_side

    def update(self, timestamp=None, bid_side=None, ask_side=None):
        self.timestamp = timestamp
        self.bid_side = bid_side
        self.ask_side = ask_side
        return self

    def __repr__(self):
        return (f"timestamp={self.timestamp}, bid_side={bool(self.bid_side)}, ask_side={bool(self.ask_side)}")
        return (f"timestamp={self.timestamp}, bid_side={self.bid_side}, ask_side={self.ask_side}")