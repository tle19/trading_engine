import json
import os
import time
from datetime import datetime, timezone
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
        self.shares = 5

    def start_equity(self, duration=23520):

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

            signal, stop_loss, take_profit, position_size = self.strategy.update(row)
            # self.shares = (20000 * position_size) // row['close']
            self.interpret_equity_signal(signal, stop_loss, take_profit)

        self.streamer.start(response_handler)
        
        self.streamer.send(self.streamer.chart_equity(self.symbol, "0,1,2,3,4,5,6", command="SUBS"))
        time.sleep(duration) # stream duration
        
        self.streamer.stop()
        
    def start_forex(self, duration=23520):

        def response_handler(response):
            data = json.loads(response).get("data", [])

            if not data:
                return
            
            for item in data:
                content = item["content"][0]

                timestamp = datetime.fromtimestamp(item["timestamp"] / 1000, tz=timezone.utc)
                timestamp = timestamp.astimezone(ZoneInfo(self.timezone))
                row = {
                    "timestamp": timestamp,
                    "bid": content.get("1"),
                    "ask": content.get("2"),
                    "last": content.get("3"),
                    "bid_size": content.get("4"),
                    "ask_size": content.get("5"),
                    "volume": content.get("6")
                }
                print(f"Timestamp: {timestamp}")

            signal, stop_pct, limit_pct = self.strategy.update(row)
            self.interpret_signal(signal, signal, stop_pct, limit_pct)

        self.streamer.start(response_handler)
        
        self.streamer.send(self.streamer.chart_equity(self.symbol, "0,1,2,3,4,5,6", command="SUBS"))
        time.sleep(duration) # stream duration
        
        self.streamer.stop()

    def interpret_equity_signal(self, signal, stop_pct, limit_pct):

        # --- Enter Long ---
        if signal == 1 and self.position is None:
            self.position = "long"
            self.buy_equity_bracket(self.shares, stop_pct, limit_pct)

        # --- Enter Short ---
        elif signal == -1 and self.position is None:
            self.position = "short"
            self.sell_equity_bracket(self.shares, stop_pct, limit_pct)

        # --- Exit Position ---
        elif signal == 0 and self.position is not None:
            if self.position == "long":
                pass

            elif self.position == "short":
                pass

            self.position = None
            
    def interpret_forex_signal(self, signal, stop_pct, limit_pct, curr_time):

        # --- Enter Long ---
        if signal == 1 and self.position is None:
            self.position = "long"
            self.buy_equity_bracket(self.shares, stop_pct, limit_pct)

        # --- Enter Short ---
        elif signal == -1 and self.position is None:
            self.position = "short"
            self.sell_equity_bracket(self.shares, stop_pct, limit_pct)

        # --- Exit Position ---
        elif signal == 0 and self.position is not None:
            if self.position == "long":
                pass

            elif self.position == "short":
                pass

            self.position = None

    def buy_equity_bracket(self, quantity, stop_pct, limit_pct):
        buy_order = {
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

        response = self.client.order_place(self.hash, buy_order)
        order_id = response.headers.get('location', '/').split('/')[-1]
        details = self.client.order_details(self.hash, order_id)
        details_json = details.json()

        legs = details_json['orderActivityCollection'][0]['executionLegs']
        fill_price = sum(leg['price'] * leg['quantity'] for leg in legs) / sum(leg['quantity'] for leg in legs)

        stop_price = str(round(fill_price * (1 - stop_pct), 2))
        limit_price = str(round(fill_price * (1 + limit_pct), 2))

        bracket_order = {
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

        response = self.client.order_place(self.hash, bracket_order)

        print(f"BUY {quantity} {self.symbol} with TP {limit_price} and SL {stop_price}")

        return response

    def sell_equity_bracket(self, quantity, stop_pct, limit_pct):
            sell_order = {
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

            response = self.client.order_place(self.hash, sell_order)
            order_id = response.headers.get('location', '/').split('/')[-1]
            details = self.client.order_details(self.hash, order_id)
            details_json = details.json()

            legs = details_json['orderActivityCollection'][0]['executionLegs']
            fill_price = sum(leg['price'] * leg['quantity'] for leg in legs) / sum(leg['quantity'] for leg in legs)

            stop_price = str(round(fill_price * (1 + stop_pct), 2))
            limit_price = str(round(fill_price * (1 - limit_pct), 2))

            bracket_order = {
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

            response = self.client.order_place(self.hash, bracket_order)

            print(f"SELL {quantity} {self.symbol} with TP {limit_price} and SL {stop_price}") 

            return response

    def buy_forex_bracket(self, quantity, stop_pct, limit_pct):
        buy_order = {
            "orderStrategyType": "SINGLE",
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "GTC",
            "orderLegCollection": [
                {
                    "instruction": "BUY",
                    "quantity": quantity,
                    "instrument": {
                        "symbol": self.symbol,
                        "assetType": "FOREX"
                    }
                }
            ]
        }
        
        response = self.client.order_place(self.hash, buy_order)
        order_id = response.headers.get('location', '/').split('/')[-1]
        details = self.client.order_details(self.hash, order_id)
        details_json = details.json()

        legs = details_json['orderActivityCollection'][0]['executionLegs']
        fill_price = sum(leg['price'] * leg['quantity'] for leg in legs) / sum(leg['quantity'] for leg in legs)

        stop_price = str(round(fill_price * (1 - stop_pct), 5))
        limit_price = str(round(fill_price * (1 + limit_pct), 5))

        oco_order = {
            "orderStrategyType": "OCO",
            "childOrderStrategies": [
                {
                    "orderType": "LIMIT",
                    "session": "NORMAL",
                    "price": limit_price,
                    "duration": "GTC",
                    "orderStrategyType": "SINGLE",
                    "orderLegCollection": [
                        {
                            "instruction": "SELL",
                            "quantity": quantity,
                            "instrument": {
                                "symbol": self.symbol,
                                "assetType": "FOREX"
                            }
                        }
                    ]
                },
                {
                    "orderType": "STOP",
                    "session": "NORMAL",
                    "stopPrice": stop_price,
                    "duration": "GTC",
                    "orderStrategyType": "SINGLE",
                    "orderLegCollection": [
                        {
                            "instruction": "SELL",
                            "quantity": quantity,
                            "instrument": {
                                "symbol": self.symbol,
                                "assetType": "FOREX"
                            }
                        }
                    ]
                }
            ]
        }

        response = self.client.order_place(self.hash, oco_order)

        print(f"BUY {quantity} {self.symbol} with TP {stop_price} and SL {limit_price}") 

        return response
    
    def sell_forex_bracket(self, quantity, stop_pct, limit_pct):
        sell_order = {
            "orderStrategyType": "SINGLE",
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "GTC",
            "orderLegCollection": [
                {
                    "instruction": "SELL",
                    "quantity": quantity,
                    "instrument": {
                        "symbol": self.symbol,
                        "assetType": "FOREX"
                    }
                }
            ]
        }

        response = self.client.order_place(self.hash, sell_order)
        order_id = response.headers.get('location', '/').split('/')[-1]
        details = self.client.order_details(self.hash, order_id)
        details_json = details.json()

        legs = details_json['orderActivityCollection'][0]['executionLegs']
        fill_price = sum(leg['price'] * leg['quantity'] for leg in legs) / sum(leg['quantity'] for leg in legs)

        stop_price = str(round(fill_price * (1 + stop_pct), 5))
        limit_price = str(round(fill_price * (1 - limit_pct), 5))

        bracket_order = {
            "orderStrategyType": "OCO",
            "childOrderStrategies": [
                {
                    "orderType": "LIMIT",
                    "session": "NORMAL",
                    "price": limit_price,
                    "duration": "GTC",
                    "orderStrategyType": "SINGLE",
                    "orderLegCollection": [
                        {
                            "instruction": "BUY",
                            "quantity": quantity,
                            "instrument": {
                                "symbol": self.symbol,
                                "assetType": "FOREX"
                            }
                        }
                    ]
                },
                {
                    "orderType": "STOP",
                    "session": "NORMAL",
                    "stopPrice": stop_price,
                    "duration": "GTC",
                    "orderStrategyType": "SINGLE",
                    "orderLegCollection": [
                        {
                            "instruction": "BUY",
                            "quantity": quantity,
                            "instrument": {
                                "symbol": self.symbol,
                                "assetType": "FOREX"
                            }
                        }
                    ]
                }
            ]
        }

        response = self.client.order_place(self.hash, bracket_order)

        print(f"SELL {quantity} {self.symbol} with TP {limit_price} and SL {stop_price}")

        return response

    def cancel_order(self, response):
        order_id = response.headers.get('location', '/').split('/')[-1]
        self.client.order_cancel(self.hash, order_id)

    def replace_order(self, response):
        order_id = response.headers.get('location', '/').split('/')[-1]

        
        self.client.order_replace(self.hash, order_id, replacement_order)

# from strategy.scalp import Scalp

# pr = Program("TSLA", Scalp)
# pr.sell_equity_bracket(1, 0.001, 0.002)