import os
import json
import time
import pandas as pd
from collections import namedtuple, deque
from zoneinfo import ZoneInfo

import schwabdev

from utils import *

class Equities:
    def __init__(self, symbol, strategy_class, cash=25_000, margin=1.0, shares=1):
        self.symbol = symbol
        self.strategy = strategy_class
        self.cash = cash
        self.shares = shares * margin
        self.margin = margin
        self.force_close = False

        self.risk_manager = self.strategy.get_risk_manager()
        self.tf = self.strategy.get_tf()

        config = load_config()
        self.app_key = config['app_key']
        self.app_secret = config['app_secret']

        self.client = schwabdev.Client(self.app_key, self.app_secret)
        self.hash = self.client.account_linked().json()[0]['hashValue']
        self.streamer = self.client.stream

        self.timezone = ZoneInfo("America/New_York")

        self.entry_response = None
        self.hold_response = None
        self.is_trailing_stop = False

        self.Row = namedtuple("Row", ["timestamp", "open", "high", "low", "close", "volume"])

    def run(self, duration=23520):
        buffer = deque()
        last_run = None

        def response_handler(response):
            nonlocal last_run

            data = json.loads(response).get("data", [])
            if not data:
                return

            for item in data:
                content = item["content"][0]
                
                timestamp = pd.to_datetime(item['timestamp'], unit='ms', utc=True).tz_convert(self.timezone)
                open = content.get("2")
                high = content.get("3")
                low = content.get("4")
                close = content.get("5")
                volume = content.get("6")

                row = self.Row(timestamp, open, high, low, close, volume)
                buffer.append({
                    "timestamp": timestamp,
                    "open": open,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume
                })

            print(row)
       
            if (row.timestamp.hour, row.timestamp.minute) == (15, 58):
                signal = self.strategy.generate_signal(row)

                stop_price = str(self.strategy.get_stop_price())
                profit_price = str(self.strategy.get_profit_price())
                self.is_trailing_stop = self.strategy.is_trailing_stop()
                position = self.strategy.get_position()
                position_size = self.strategy.get_position_size()
                shares = max(1, int(self.shares * position_size))
                self.force_close = True

                self.interpret_signal(signal, position, shares, stop_price, profit_price)

                self.streamer.stop()
                return

            interval_floor = row.timestamp.floor(f'{self.tf}T')
            if last_run is None or interval_floor > last_run:
                last_run = interval_floor

                df = pd.DataFrame(buffer)
                agg_row = self.Row(
                    timestamp=interval_floor,
                    open=df.iloc[0]['open'],
                    high=df['high'].max(),
                    low=df['low'].min(),
                    close=df.iloc[-1]['close'],
                    volume=df['volume'].sum()
                )
                buffer.clear()

                signal = self.strategy.generate_signal(agg_row)

                stop_price = str(self.strategy.get_stop_price())
                profit_price = str(self.strategy.get_profit_price())
                self.is_trailing_stop = self.strategy.is_trailing_stop()
                position = self.strategy.get_position()
                position_size = self.strategy.get_position_size()
                shares = max(1, int(self.shares * position_size))

                self.interpret_signal(signal, position, shares, stop_price, profit_price)

        self.cash = self.get_liquidation_value()
        self.risk_manager.set_start_cash(self.cash)

        self.streamer.start(response_handler)
        #start_auto for market open
        
        self.streamer.send(self.streamer.chart_equity(self.symbol, "0,1,2,3,4,5,6", command="SUBS"))
        time.sleep(duration)
        
        self.streamer.stop()

    def interpret_signal(self, signal, position, shares, stop_price, profit_price):
        # --- Enter Long ---
        if signal == 1 and position == "long":
            self.entry_response = self.buy_market(shares, "BUY")
            self.hold_response = self.long_bracket(shares, stop_price, profit_price)
            self.strategy.update_entry_price(self.fill_price)

        # --- Enter Short ---
        elif signal == -1 and position == "short":
            self.entry_response = self.sell_market(shares, "SELL_SHORT")
            self.hold_response = self.short_bracket(shares, stop_price, profit_price)
            self.strategy.update_entry_price(self.fill_price)

        # --- Holding ---
        elif signal is None and position is not None:
            if self.is_trailing_stop:
                if position == "long":
                    self.hold_response = self.replace_order(shares, position, stop_price, profit_price, self.hold_response)

                elif position == "short":
                    self.hold_response = self.replace_order(shares, position, stop_price, profit_price, self.hold_response)
                
            if self.force_close:
                self.cancel_order(self.hold_response)
                if position == "long":
                    self.sell_market(shares, "SELL")

                elif position == "short":
                    self.buy_market(shares, "BUY_TO_COVER")

                self.flatten()

        # --- Exit Position ---
        elif signal == 0 and position is not None:
            if position == "long": #implement market sell (if cancel hold_response returns object, then sell else do nothing)
                print(f"SELL -{shares} {self.symbol}") # @ price sold, check order details

            elif position == "short":
                print(f"BOT +{shares} {self.symbol}")

            self.flatten()
            
    def flatten(self):
        self.entry_response = None
        self.hold_response = None
        self.is_trailing_stop = False
        pnl = self.get_liquidation_value() - self.cash
        self.cash += pnl
        self.risk_manager.check_risk(pnl)
        self.strategy.flatten()

    def buy_market(self, quantity, type="BUY"):
        order_dict = {
            "orderStrategyType": "SINGLE",
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderLegCollection": [
                {
                    "instruction": type,
                    "quantity": quantity,
                    "instrument": {
                        "symbol": self.symbol,
                        "assetType": "EQUITY"
                    }
                }
            ]
        }

        response = self.client.order_place(self.hash, order_dict)
        self.fill_price = self.get_fill_price(response)
        print(f"BOT +{quantity} {self.symbol} @ {self.fill_price}")
        return response
    
    def sell_market(self, quantity, type="SELL"):
        order_dict = {
            "orderStrategyType": "SINGLE",
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderLegCollection": [
                {
                    "instruction": type,
                    "quantity": quantity,
                    "instrument": {
                        "symbol": self.symbol,
                        "assetType": "EQUITY"
                    }
                }
            ]
        }

        response = self.client.order_place(self.hash, order_dict)
        self.fill_price = self.get_fill_price(response)
        print(f"SELL -{quantity} {self.symbol} @ {self.fill_price}")
        return response
    
    def long_bracket(self, quantity, stop_price, profit_price):
        order_dict = self.get_sell_order_dict(quantity, stop_price, profit_price)
        response = self.client.order_place(self.hash, order_dict)

        print(f"SL @ {stop_price} & TP @ {profit_price}")
        return response

    def short_bracket(self, quantity, stop_price, profit_price):
        order_dict = self.get_buy_order_dict(quantity, stop_price, profit_price)
        response = self.client.order_place(self.hash, order_dict)

        print(f"SL @ {stop_price} & TP @ {profit_price}")
        return response
    
    def get_buy_order_dict(self, quantity, stop_price, profit_price):
        order_dict = {
            "orderStrategyType": "OCO",
            "childOrderStrategies": [
                {
                    "orderType": "LIMIT",
                    "session": "NORMAL",
                    "price": profit_price,
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

        return order_dict
    
    def get_sell_order_dict(self, quantity, stop_price, profit_price):
        order_dict = {
            "orderStrategyType": "OCO",
            "childOrderStrategies": [
                {
                    "orderType": "LIMIT",
                    "session": "NORMAL",
                    "price": profit_price,
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

        return order_dict

    def get_fill_price(self, response):
        order_id = response.headers.get('location', '/').split('/')[-1]
        details = self.client.order_details(self.hash, order_id)
        details_json = details.json()

        legs = details_json['orderActivityCollection'][0]['executionLegs']
        fill_price = sum(leg['price'] * leg['quantity'] for leg in legs) / sum(leg['quantity'] for leg in legs)
        fill_price = round(fill_price, 2)
        return fill_price

    def replace_order(self, position, quantity, stop_loss, take_profit, response):
        self.cancel_order(response)
        time.sleep(0.05) # buffer time for order to cancel
        if position == "long":
            return self.long_bracket(quantity, stop_loss, take_profit)
        elif position == "short":
            return self.short_bracket(quantity, stop_loss, take_profit)

    def cancel_order(self, response):
        order_id = response.headers.get('location', '/').split('/')[-1]
        self.client.order_cancel(self.hash, order_id)

    def get_liquidation_value(self):
        details = self.client.account_details(self.hash)
        details_json = details.json()
        liquidationValue = details_json["securitiesAccount"]["currentBalances"]["liquidationValue"]
        return liquidationValue
