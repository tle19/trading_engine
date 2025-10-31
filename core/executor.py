import os
import json
import time
from collections import namedtuple
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
        self.is_trailing_profit = False

        self.Row = namedtuple("Row", ["timestamp", "open", "high", "low", "close", "volume"])
        self.last_high = None
        self.last_low = None

    def run(self, duration=23520):
        def response_handler(response):
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

                high = self.last_high if high is None else high
                low = self.last_low if low is None else low
                self.last_high = high
                self.last_low = low

                row = self.Row(timestamp, open, high, low, close, volume)

            print(row)
       
            if (row.timestamp.hour, row.timestamp.minute) == (15, 58): # need to adjust
                self.force_close = self.strategy.is_force_close()

            signal = self.strategy.generate_signal(row)

            stop_price = str(self.strategy.get_stop_price())
            profit_price = str(self.strategy.get_profit_price())
            self.is_trailing_stop = self.strategy.is_trailing_stop()
            self.is_trailing_profit = self.strategy.is_trailing_profit()
            position = self.strategy.get_position()
            position_size = self.strategy.get_position_size()
            shares = max(1, int(self.shares * position_size))

            self.interpret_signal(signal, position, shares, stop_price, profit_price)

        self.cash = self.get_liquidation_value()
        self.risk_manager.set_start_cash(self.cash)

        self.streamer.start(response_handler)
        #start_auto for market open
        
        self.streamer.send(self.streamer.chart_equity(self.symbol, "0,1,2,3,4,5,6", command="SUBS"))
        time.sleep(duration) # stream duration
        
        self.streamer.stop()

    def interpret_signal(self, signal, position, shares, stop_price, profit_price):
        # --- Enter Long ---
        if signal == 1 and position == "long":
            self.entry_response = self.buy_market(shares)
            self.hold_response = self.long_bracket(shares, stop_price, profit_price)
            self.strategy.update_entry_price(self.fill_price)

        # --- Enter Short ---
        elif signal == -1 and position == "short":
            self.entry_response = self.sell_market(shares)
            self.hold_response = self.short_bracket(shares, stop_price, profit_price)
            self.strategy.update_entry_price(self.fill_price)

        # --- Holding ---
        elif signal is None and position is not None:
            if self.is_trailing_stop or self.is_trailing_profit:
                if position == "long":
                    self.hold_response = self.replace_order(shares, position, stop_price, profit_price, self.hold_response)

                elif position == "short":
                    self.hold_response = self.replace_order(shares, position, stop_price, profit_price, self.hold_response)
                
            if self.force_close:
                print('I EXECUTED HERE 1')
                self.cancel_order(self.hold_response)
                print('I EXECUTED HERE 2')
                if position == "long":
                    self.sell_market(shares) # order_dict doesnt work here #SELL

                elif position == "short":
                    self.buy_market(shares) # order_dict doesnt work here #BUY_TO_COVER

                self.flatten()

        # --- Exit Position ---
        elif signal == 0 and position is not None:
            if position == "long": #implement market sell
                print(f"SELL -{shares} {self.symbol}") # @ price sold

            elif position == "short":
                print(f"BOT +{shares} {self.symbol}")

            self.flatten()
            
    def flatten(self):
        self.entry_response = None
        self.hold_response = None
        self.is_trailing_stop = False
        self.is_trailing_profit = False
        pnl = self.get_liquidation_value() - self.cash
        self.cash += pnl
        self.risk_manager.check_risk(pnl)
        self.strategy.flatten()

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
        self.fill_price = self.get_fill_price(response)
        print(f"BOT +{quantity} {self.symbol} @ {self.fill_price}")
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
