import json
import os
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

import schwabdev

from utils import *

class Equities:
    def __init__(self, symbol, strategy):
        
        config = load_config()
        self.app_key = config['app_key']
        self.app_secret = config['app_secret']

        self.client = schwabdev.Client(self.app_key, self.app_secret)
        self.hash = self.client.account_linked().json()[0]['hashValue']
        self.streamer = self.client.stream

        self.timezone = ZoneInfo("America/New_York")

        self.strategy = strategy()
        
        self.symbol = symbol
        self.position = None
        self.shares = 10
        self.daily_stop_loss = -250

        self.entry_response = None
        self.hold_response = None

    def start(self, duration=23520):
        start_of_day_cash = 5000
        def response_handler(response):
            data = json.loads(response).get("data", [])

            if not data:
                return

            for item in data:
                content = item["content"][0]
                
                timestamp = datetime.fromtimestamp(item["timestamp"] / 1000, tz=timezone.utc)
                timestamp = timestamp.astimezone(self.timezone)
                row = {
                    "timestamp": timestamp,
                    "open": content.get("2"),
                    "high": content.get("3"),
                    "low": content.get("4"),
                    "close": content.get("5"),
                    "volume": content.get("6")
                }
                print(f"Timestamp: {timestamp}")

            signal, stop_loss, take_profit, position_size = self.strategy.generate_signal(row)
            if position_size is not None:
                self.shares = (start_of_day_cash * position_size) // row["close"]
            self.interpret_signal(signal, stop_loss, take_profit, position_size)

            # curr_cash = ???
            # if self.daily_stop_loss is not None:
            #     cumulative_pnl = curr_cash - start_of_day_cash
            #     if cumulative_pnl <= self.daily_stop_loss:
            #         self.streamer.stop()  # skip rest of day

        self.streamer.start(response_handler)
        
        self.streamer.send(self.streamer.chart_equity(self.symbol, "0,1,2,3,4,5,6", command="SUBS"))
        time.sleep(duration) # stream duration
        
        self.streamer.stop()

    def interpret_signal(self, signal, stop_pct, limit_pct, position_size):

        # --- Enter Long ---
        if signal == 1 and self.position is None:
            self.position = "long"
            self.entry_response = self.buy_market(self.shares)
            self.hold_response = self.long_bracket(self.shares, stop_pct, limit_pct, self.entry_response)

        # --- Enter Short ---
        elif signal == -1 and self.position is None:
            self.position = "short"
            self.entry_response = self.sell_market(self.shares)
            self.hold_response = self.short_bracket(self.shares, stop_pct, limit_pct, self.entry_response)
        
        # --- Holding ---
        elif signal is None and position_size is not None:
            if self.position == "long":
                self.replace_order(self.shares, stop_pct, limit_pct, self.entry_response, self.hold_response, self.position)

            elif self.position == "short":
                self.replace_order(self.shares, stop_pct, limit_pct, self.entry_response, self.hold_response, self.position)

            self.position = None

        # --- Exit Position ---
        elif signal == 0 and self.position is not None:
            if self.position == "long":
                print(f"SELL -{self.shares} {self.symbol}")

            elif self.position == "short":
                print(f"BOT +{self.shares} {self.symbol}")

            self.position = None

    def buy_market(self, quantity):
        order_dict = {
            "orderStrategyType": "SINGLE",
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderLegCollection": [
                {
                    "instruction": "BUY",
                    "quantity": quantity,
                    "instrument": {
                        "symbol": self.symbol,
                        "assetType": "EQUITY"
                    }
                }
            ]
        }

        response = self.client.order_place(self.hash, order_dict)
        print(f"BOT +{quantity} {self.symbol}")
        return response
    
    def sell_market(self, quantity):
        order_dict = {
            "orderStrategyType": "SINGLE",
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderLegCollection": [
                {
                    "instruction": "SELL_SHORT",
                    "quantity": quantity,
                    "instrument": {
                        "symbol": self.symbol,
                        "assetType": "EQUITY"
                    }
                }
            ]
        }

        response = self.client.order_place(self.hash, order_dict)
        print(f"SELL -{quantity} {self.symbol}")
        return response
    
    def long_bracket(self, quantity, stop_pct, limit_pct, response):
        order_dict, stop_price, limit_price = self.get_sell_order_dict(quantity, stop_pct, limit_pct, response)

        response = self.client.order_place(self.hash, order_dict)
        print(f"SET SL {stop_price} and TP {limit_price}")
        return response

    def short_bracket(self, quantity, stop_pct, limit_pct, response):
        order_dict, stop_price, limit_price = self.get_buy_order_dict(quantity, stop_pct, limit_pct, response)

        response = self.client.order_place(self.hash, order_dict)
        print(f"SET SL {stop_price} and TP {limit_price}")
        return response
    
    def get_buy_order_dict(self, quantity, stop_pct, limit_pct, response):

        fill_price = self.get_fill_price(response)
        stop_price = str(round(fill_price * (1 + stop_pct), 2))
        limit_price = str(round(fill_price * (1 - limit_pct), 2))

        order_dict = {
            "orderStrategyType": "OCO",
            "childOrderStrategies": [
                {
                    "orderType": "LIMIT",
                    "session": "NORMAL",
                    "price": limit_price,
                    "duration": "DAY",
                    "orderStrategyType": "SINGLE",
                    "orderLegCollection": [
                        {
                            "instruction": "BUY_TO_COVER",
                            "quantity": quantity,
                            "instrument": {
                                "symbol": self.symbol,
                                "assetType": "EQUITY"
                            }
                        }
                    ]
                },
                {
                    "orderType": "STOP",
                    "session": "NORMAL",
                    "stopPrice": stop_price,
                    "duration": "DAY",
                    "orderStrategyType": "SINGLE",
                    "orderLegCollection": [
                        {
                            "instruction": "BUY_TO_COVER",
                            "quantity": quantity,
                            "instrument": {
                                "symbol": self.symbol,
                                "assetType": "EQUITY"
                            }
                        }
                    ]
                }
            ]
        }

        return order_dict, stop_price, limit_price
    
    def get_sell_order_dict(self, quantity, stop_pct, limit_pct, response):

        fill_price = self.get_fill_price(response)
        stop_price = str(round(fill_price * (1 - stop_pct), 2))
        limit_price = str(round(fill_price * (1 + limit_pct), 2))

        order_dict = {
            "orderStrategyType": "OCO",
            "childOrderStrategies": [
                {
                    "orderType": "LIMIT",
                    "session": "NORMAL",
                    "price": limit_price,
                    "duration": "DAY",
                    "orderStrategyType": "SINGLE",
                    "orderLegCollection": [
                        {
                            "instruction": "SELL",
                            "quantity": quantity,
                            "instrument": {
                                "symbol": self.symbol,
                                "assetType": "EQUITY"
                            }
                        }
                    ]
                },
                {
                    "orderType": "STOP",
                    "session": "NORMAL",
                    "stopPrice": stop_price,
                    "duration": "DAY",
                    "orderStrategyType": "SINGLE",
                    "orderLegCollection": [
                        {
                            "instruction": "SELL",
                            "quantity": quantity,
                            "instrument": {
                                "symbol": self.symbol,
                                "assetType": "EQUITY"
                            }
                        }
                    ]
                }
            ]
        }

        return order_dict, stop_price, limit_price

    def get_fill_price(self, response):
        order_id = response.headers.get('location', '/').split('/')[-1]
        details = self.client.order_details(self.hash, order_id)
        details_json = details.json()

        legs = details_json['orderActivityCollection'][0]['executionLegs']
        fill_price = sum(leg['price'] * leg['quantity'] for leg in legs) / sum(leg['quantity'] for leg in legs)
        return fill_price

    def replace_order(self, quantity, stop_pct, limit_pct, entry_response, hold_response, position=None):
        self.cancel_order(hold_response)
        if position == "long":
            self.long_bracket(quantity, stop_pct, limit_pct, entry_response)
        elif position == "short":
            self.short_bracket(quantity, stop_pct, limit_pct, entry_response)

    def cancel_order(self, response):
        order_id = response.headers.get('location', '/').split('/')[-1]
        self.client.order_cancel(self.hash, order_id)


# from strategy.trend import IntradayTrend

# pr = Equities("GOOG", IntradayTrend)
# entry_response = pr.sell_market(1)
# hold_response = pr.short_bracket(1, 0.001, 0.001, entry_response)
# time.sleep(5)
# pr.replace_order(1, 0.002, 0.002, entry_response, hold_response, "short")
