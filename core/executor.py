import json
import time
import pandas as pd
from collections import namedtuple
from zoneinfo import ZoneInfo

import schwabdev

from utils import *

class Equities:
    def __init__(self, symbol, strategy_class, margin=1.0):
        config = load_config()
        self.app_key = config['app_key']
        self.app_secret = config['app_secret']

        self.client = schwabdev.Client(self.app_key, self.app_secret)
        self.hash = self.client.account_linked().json()[0]['hashValue']
        self.streamer = self.client.stream

        self.timezone = ZoneInfo("America/New_York")
        self.cash = self.get_liquidation_value()
        self.margin = margin

        self.symbols = [s.split(":")[0] for s in symbol]
        self.strategies = {}
        self.entry_responses = {}
        self.hold_responses = {}

        self.shares_to_buy = allocate_positions(symbol, cash=self.cash)

        for sym in self.symbols:
            strategy_instance = strategy_class(sym)
            self.strategies[sym] = strategy_instance
            self.entry_responses[sym] = None
            self.hold_responses[sym] = None
        
        self.fill_price = None
        self.force_close = False
        self.Row = namedtuple("Row", ["timestamp", "open", "high", "low", "close", "volume"])

    def run(self, duration=23520):
        def response_handler(response):
            data = json.loads(response).get("data", [])
            if not data:
                return

            content = data[0].get("content")
            if not content:
                return
            for item in content:
                symbol = item["key"]
                strategy = self.strategies[symbol]
                
                timestamp = pd.to_datetime(item.get("7"), unit='ms', utc=True).tz_convert(self.timezone)
                open = item.get("2")
                high = item.get("3")
                low = item.get("4")
                close = item.get("5")
                volume = item.get("6")

                row = self.Row(timestamp, open, high, low, close, volume)
                print(f"{symbol}: {row}")

                signal = strategy.generate_signal(row)
                self.interpret_signal(signal, strategy, symbol)

            if (row.timestamp.hour, row.timestamp.minute) >= (15, 57):
                self.force_close = True

        total_weight = sum(self.shares_to_buy.values())
        for symbol, strategy in self.strategies.items():
            weight = self.shares_to_buy[symbol]
            cash_allocation = self.cash * (weight / total_weight)
            strategy.get_risk_manager().set_start_cash(cash_allocation)

        self.streamer.start(response_handler)
        #start_auto for auto market open
        
        self.streamer.send(self.streamer.chart_equity(self.symbols, "0,1,2,3,4,5,6,7,8", command="SUBS"))
        time.sleep(duration)
        
        self.streamer.stop()

    def interpret_signal(self, signal, strategy, symbol):
        stop_price = str(strategy.get_stop_price())
        profit_price = str(strategy.get_profit_price())
        is_trailing_stop = strategy.is_trailing_stop()
        position = strategy.get_position()
        position_size = strategy.get_position_size()
        shares = max(1, int(self.shares_to_buy[symbol] * position_size))
        shares = 1 # for testing
        
        # --- Enter Long ---
        if signal == 1 and position == "long":
            self.entry_responses[symbol] = self.buy_market(symbol, shares, "BUY")
            self.hold_responses[symbol] = self.long_bracket(symbol, shares, stop_price, profit_price)
            strategy.update_entry_price(self.fill_price)
            self.fill_price = None

        # --- Enter Short ---
        elif signal == -1 and position == "short":
            self.entry_responses[symbol] = self.sell_market(symbol, shares, "SELL_SHORT")
            self.hold_responses[symbol] = self.short_bracket(symbol, shares, stop_price, profit_price)
            strategy.update_entry_price(self.fill_price)
            self.fill_price = None

        # --- Holding ---
        elif signal is None and position is not None:
            if is_trailing_stop:
                if position == "long":
                    self.hold_responses[symbol] = self.replace_order(symbol, shares, position, stop_price, profit_price, self.hold_responses[symbol])

                elif position == "short":
                    self.hold_responses[symbol] = self.replace_order(symbol, shares, position, stop_price, profit_price, self.hold_responses[symbol])
                
        # --- Exit Position --- 
        elif signal == 0 and position is not None:
            if position == "long": 
                fill_price = self.get_fill_price(self.hold_responses[symbol])
                print(f"SOLD -{shares} {symbol} @ {fill_price}")
            #implement market sell (if cancel hold_response returns object, then sell else do nothing)
            elif position == "short":
                fill_price = self.get_fill_price(self.hold_responses[symbol])
                print(f"BOT +{shares} {symbol}")

            self.flatten(symbol, strategy)
            self.update_pnl(symbol, strategy)
        
        # --- Force Close ---
        elif self.force_close and signal is None and position is not None:
            self.cancel_order(self.hold_responses[symbol])
            if position == "long":
                self.sell_market(symbol, shares, "SELL")

            elif position == "short":
                self.buy_market(symbol, shares, "BUY_TO_COVER")

            self.flatten(symbol, strategy)
            self.update_pnl(symbol, strategy)
        
    def flatten(self, symbol, strategy):
        self.entry_responses[symbol] = None
        self.hold_responses[symbol] = None
        strategy.flatten()

    def update_pnl(self, strategy):
        pnl = self.get_liquidation_value() - self.cash
        self.cash += pnl
        strategy.get_risk_manager().check_risk(pnl)

    def buy_market(self, symbol, quantity, type="BUY"):
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
                        "symbol": symbol,
                        "assetType": "EQUITY"
                    }
                }
            ]
        }

        response = self.client.order_place(self.hash, order_dict)
        self.fill_price = self.get_fill_price(response)
        print(f"BOT +{quantity} {symbol} @ {self.fill_price}")
        return response
    
    def sell_market(self, symbol, quantity, type="SELL"):
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
                        "symbol": symbol,
                        "assetType": "EQUITY"
                    }
                }
            ]
        }

        response = self.client.order_place(self.hash, order_dict)
        self.fill_price = self.get_fill_price(response)
        print(f"SELL -{quantity} {symbol} @ {self.fill_price}")
        return response
    
    def long_bracket(self, symbol, quantity, stop_price, profit_price):
        order_dict = self.get_sell_order_dict(symbol, quantity, stop_price, profit_price)
        response = self.client.order_place(self.hash, order_dict)

        print(f"SL @ {stop_price} & TP @ {profit_price}")
        return response

    def short_bracket(self, symbol, quantity, stop_price, profit_price):
        order_dict = self.get_buy_order_dict(symbol, quantity, stop_price, profit_price)
        response = self.client.order_place(self.hash, order_dict)

        print(f"SL @ {stop_price} & TP @ {profit_price}")
        return response
    
    def get_buy_order_dict(self, symbol, quantity, stop_price, profit_price):
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
                                "symbol": symbol,
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
                                "symbol": symbol,
                                "assetType": "EQUITY"
                            }
                        }
                    ]
                }
            ]
        }

        return order_dict
    
    def get_sell_order_dict(self, symbol, quantity, stop_price, profit_price):
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
                                "symbol": symbol,
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
                                "symbol": symbol,
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

    def replace_order(self, symbol, position, quantity, stop_loss, take_profit, response):
        self.cancel_order(response)
        time.sleep(0.05) # buffer time for order to cancel
        if position == "long":
            return self.long_bracket(symbol, quantity, stop_loss, take_profit)
        elif position == "short":
            return self.short_bracket(symbol, quantity, stop_loss, take_profit)

    def cancel_order(self, response):
        order_id = response.headers.get('location', '/').split('/')[-1]
        self.client.order_cancel(self.hash, order_id)

    def get_liquidation_value(self):
        details = self.client.account_details(self.hash)
        details_json = details.json()
        liquidationValue = details_json["securitiesAccount"]["currentBalances"]["liquidationValue"]
        return liquidationValue