import os
import json
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import schwabdev

from utils import *

class Equities:
    def __init__(self, symbol, strategy_class, cash=30_000, margin=1.0, shares=1):
        self.symbol = symbol
        self.strategy = strategy_class
        self.cash = cash
        self.shares = shares * margin
        self.margin = margin
        self.force_close = False
        self.position = None

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
        self.fill_price = None

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

                high = high if high is not None else self.last_high
                low = low if low is not None else self.last_low

                self.last_high = high
                self.last_low = low

                row = {
                    "timestamp": timestamp,
                    "open": open,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume
                }

            print(f"Timestamp: {timestamp}")
            print(row) #sanity check

            if (timestamp.hour, timestamp.minute) == (15, 58):
                self.force_close = True
                
            signal = self.strategy.generate_signal(row)

            shares = max(1, round(self.shares * position_size))
            stop_loss = self.strategy.get_stop_loss()
            take_profit = self.strategy.get_take_profit()
            sl_change = self.strategy.stop_loss_changed()
            tp_change = self.strategy.take_profit_changed()
            position_size = self.strategy.get_position_size()

            self.interpret_signal(signal, shares, stop_loss, take_profit, sl_change, tp_change)

            if self.position is None:
                curr_cash = self.get_liquidation_value()
                pnl = curr_cash - self.cash
                self.cash = curr_cash
                self.risk_manager.check_risk(pnl)

        self.cash = self.get_liquidation_value()
        self.risk_manager.get_start_cash(self.cash)

        self.streamer.start(response_handler)
        #start_auto for market open
        
        self.streamer.send(self.streamer.chart_equity(self.symbol, "0,1,2,3,4,5,6", command="SUBS"))
        time.sleep(duration) # stream duration
        
        self.streamer.stop()

    def interpret_signal(self, signal, shares, stop_loss, take_profit, sl_change, tp_change):
        # --- Enter Long ---
        if signal == 1 and self.position is None:
            self.position = "long"
            self.entry_response = self.buy_market(shares)
            self.hold_response = self.long_bracket(shares, stop_loss, take_profit, self.entry_response)
            self.strategy.update_prices(self.fill_price, self.stop_price, self.profit_price)

        # --- Enter Short ---
        elif signal == -1 and self.position is None:
            self.position = "short"
            self.entry_response = self.sell_market(shares)
            self.hold_response = self.short_bracket(shares, stop_loss, take_profit, self.entry_response)
            self.strategy.update_prices(self.fill_price, self.stop_price, self.profit_price)

        # --- Holding ---
        elif signal is None and self.position is not None:
            if sl_change or tp_change:
                if self.position == "long":
                    self.hold_response = self.replace_order(shares, stop_loss, take_profit, self.entry_response, self.hold_response)

                elif self.position == "short":
                    self.hold_response = self.replace_order(shares, stop_loss, take_profit, self.entry_response, self.hold_response)
                self.strategy.update_prices(self.fill_price, self.stop_price, self.profit_price)
                
            if self.force_close:
                print('I EXECUTED HERE')
                self.cancel_order(self.hold_response)
                if self.position == "long":
                    self.sell_market(shares) # order_dict doesnt work here

                elif self.position == "short":
                    self.buy_market(shares) # order_dict doesnt work here

                self.reset()

        # --- Exit Position --- #bought here??
        elif signal == 0 and self.position is not None:
            if self.position == "long":
                print(f"SELL -{shares} {self.symbol}")

            elif self.position == "short":
                print(f"BOT +{shares} {self.symbol}")

            self.reset()
            
    def reset(self):
        self.entry_response = None
        self.hold_response = None
        self.fill_price = None
        self.stop_price = None
        self.profit_price = None
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
    
    def long_bracket(self, quantity, stop_loss, take_profit, response):
        order_dict = self.get_sell_order_dict(quantity, stop_loss, take_profit, response)

        response = self.client.order_place(self.hash, order_dict)
        print(f"SET SL {self.stop_price} and TP {self.profit_price}")
        return response

    def short_bracket(self, quantity, stop_loss, take_profit, response):
        order_dict = self.get_buy_order_dict(quantity, stop_loss, take_profit, response)

        response = self.client.order_place(self.hash, order_dict)
        print(f"SET SL {self.stop_price} and TP {self.profit_price}")
        return response
    
    def get_buy_order_dict(self, quantity, stop_loss, take_profit, response):
        if self.fill_price is None:
            self.fill_price = self.get_fill_price(response)
        self.stop_price = str(round(self.fill_price * (1 + stop_loss), 2))
        self.profit_price = str(round(self.fill_price * (1 - take_profit), 2))

        order_dict = {
            "orderStrategyType": "OCO",
            "childOrderStrategies": [
                {
                    "orderType": "LIMIT",
                    "session": "NORMAL",
                    "price": self.profit_price,
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
                    "stopPrice": self.stop_price,
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
    
    def get_sell_order_dict(self, quantity, stop_loss, take_profit, response):
        if self.fill_price is None:
            self.fill_price = self.get_fill_price(response)
        self.stop_price = str(round(self.fill_price * (1 - stop_loss), 2))
        self.profit_price = str(round(self.fill_price * (1 + take_profit), 2))

        order_dict = {
            "orderStrategyType": "OCO",
            "childOrderStrategies": [
                {
                    "orderType": "LIMIT",
                    "session": "NORMAL",
                    "price": self.profit_price,
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
                    "stopPrice": self.stop_price,
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

    def replace_order(self, quantity, stop_loss, take_profit, entry_response, hold_response):
        self.cancel_order(hold_response)
        time.sleep(0.05) # buffer time for order to cancel
        if self.position == "long":
            return self.long_bracket(quantity, stop_loss, take_profit, entry_response)
        elif self.position == "short":
            return self.short_bracket(quantity, stop_loss, take_profit, entry_response)

    def cancel_order(self, response):
        order_id = response.headers.get('location', '/').split('/')[-1]
        self.client.order_cancel(self.hash, order_id)

    def get_liquidation_value(self):
        details = self.client.account_details(self.hash)
        details_json = details.json()
        liquidationValue = details_json["securitiesAccount"]["currentBalances"]["liquidationValue"]
        return liquidationValue
