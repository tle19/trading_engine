import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import schwabdev

class Program:
    def __init__(self, symbol, strategy):
        with open("config.json") as f:
            config = json.load(f)

        self.app_key = config['app_key']
        self.app_secret = config['app_secret']

        self.client = schwabdev.Client(self.app_key, self.app_secret)
        self.hash = self.client.account_linked().json()[0]['hashValue']
        self.streamer = self.client.stream

        self.timezone = ZoneInfo("America/New_York")

        self.strategy = strategy()
        
        self.symbol = symbol
        self.position = None
        self.shares = 35

    def start(self, duration=23520):
        df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'timestamp'])

        def response_handler(response):
            data = json.loads(response).get("data", [])
            nonlocal df

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
                df.loc[len(df)] = pd.Series(row, index=df.columns)
                print(f"Timestamp: {timestamp}")

            signal = self.strategy.update(df.iloc[-1])
            self.interpret_signal(signal, df.iloc[-1]['timestamp'])

        self.streamer.start(response_handler)
        
        self.streamer.send(self.streamer.chart_equity(self.symbol, "0,1,2,3,4,5,6", command="SUBS"))
        time.sleep(duration) # stream duration
        
        self.streamer.stop()
        

    def interpret_signal(self, signal, curr_time):

        # --- Enter Long ---
        if signal == 1 and self.position is None:
            self.position = "long"
            self.buy_market(self.shares)

        # --- Enter Short ---
        elif signal == -1 and self.position is None:
            self.position = "short"
            self.sell_market(self.shares)

        # --- Exit Position ---
        elif signal == 0 and self.position is not None:
            if self.position == "long":
                self.sell_market(self.shares)

            elif self.position == "short":
                self.buy_market(self.shares)

            self.position = None

        # --- Force close at 16:00 ---
        if self.position is not None and curr_time.time().strftime("%H:%M") == "16:00":
            if self.position == "long":
                self.sell_market(self.shares)

            elif self.position == "short":
                self.buy_market(self.shares)

            self.position = None

    def buy_market(self, shares):
        order = {"orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {"instruction": "BUY",
                "quantity": shares,
                "instrument": {
                    "symbol": self.symbol,
                    "assetType": "EQUITY"
                }
                }
            ]
            }    
        self.client.order_place(self.hash, order)
        print(f"BUY {shares} of {self.symbol}")
    
    def sell_market(self, shares):
        order = {"orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {"instruction": "SELL",
                "quantity": shares,
                "instrument": {
                    "symbol": self.symbol,
                    "assetType": "EQUITY"
                }
                }
            ]
            }  
        self.client.order_place(self.hash, order)
        print(f"SELL {shares} of {self.symbol}")
    
    def limit_order(self, shares):
        order = {"orderType": "LIMIT",
         "session": "NORMAL",
         "duration": "DAY",
         "orderStrategyType": "SINGLE",
         "price": '10.00',
         "orderLegCollection": [
             {"instruction": "SELL",
              "quantity": shares,
              "instrument": {
                  "symbol": self.symbol,
                  "assetType": "EQUITY"
              }
              }
         ]
         }
        self.client.order_place(self.hash, order)
    
    def stop_loss(self, shares):
        order = {"orderType": "STOP",
         "session": "NORMAL",
         "duration": "DAY",
         "orderStrategyType": "SINGLE",
         "price": '10.00',
         "orderLegCollection": [
             {"instruction": "BUY",
              "quantity": shares,
              "instrument": {
                  "symbol": self.symbol,
                  "assetType": "EQUITY"
              }
              }
         ]
         }
        self.client.order_place(self.hash, order)