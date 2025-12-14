import json
import time
import datetime
import pandas as pd
from collections import namedtuple
from zoneinfo import ZoneInfo

import schwabdev

from metrics import *
from utils import *

class Equities:
    def __init__(self, symbols, strategy_class, margin=1.0):
        config = load_config()

        self.client = schwabdev.Client(config['app_key'], config['app_secret'])
        self.hash = self.client.account_linked().json()[0]['hashValue']
        self.streamer = self.client.stream

        self.cash = self.get_liquidation_value() * margin
        self.timezone = ZoneInfo("America/New_York")
        self.initialized = False
        self.force_close = False
        self.prices = []

        if symbols:
            self.initialize_strategies(symbols, strategy_class)
        else:
            self.strategy_class = strategy_class

        self.trade_log = TradeLogger()
        self.Row = namedtuple("Row", ["timestamp", "open", "high", "low", "close", "volume"])

    def run(self):
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

                # if not self.initialized:
                #     self.allocate_cash(symbol, open)

                signal = strategy.generate_signal(row)
                self.interpret_signal(signal, strategy, symbol)

            # if not self.initialized:
            #     self.initialized = True
            if (row.timestamp.hour, row.timestamp.minute) >= (15, 57):
                self.force_close = True   

        self.streamer.start_auto(
            receiver=response_handler, 
            start_time=datetime.time(9, 30, 0), 
            stop_time=datetime.time(16, 0, 0), 
            on_days=(0,1,2,3,4))
        self.await_stream_start()
        self.streamer.send(self.streamer.chart_equity(self.symbols, "0,1,2,3,4,5,6,7,8", command="SUBS"))
        self.stream_duration()

        self.trade_log.output_logs()

    def interpret_signal(self, signal, strategy, symbol):
        is_trailing = strategy.is_trailing()
        stop_price = str(strategy.get_stop_price())
        profit_price = str(strategy.get_profit_price())
        position = strategy.get_position()
        position_size = strategy.get_position_size()
        shares = max(1, int(self.shares_to_buy[symbol] * position_size))
        shares = 1 # for testing
        
        # --- Enter Long ---
        if signal == 1 and position == "long":
            self.entry_ids[symbol] = self.buy_market(symbol, shares, "BUY")
            self.exit_ids[symbol] = self.long_bracket(symbol, shares, stop_price, profit_price)
            fill_price = self.get_fill_price(self.entry_ids[symbol], shares)
            strategy.update_entry_price(fill_price)
            self.trade_log.log_entry(symbol, position, position_size, shares, strategy.ts, strategy.price, fill_price)

        # --- Enter Short ---
        elif signal == -1 and position == "short":
            self.entry_ids[symbol] = self.sell_market(symbol, shares, "SELL_SHORT")
            self.exit_ids[symbol] = self.short_bracket(symbol, shares, stop_price, profit_price)
            fill_price = self.get_fill_price(self.entry_ids[symbol], shares)
            strategy.update_entry_price(fill_price)
            self.trade_log.log_entry(symbol, position, position_size, shares, strategy.ts, strategy.price, fill_price)

        # --- Holding ---
        elif signal is None and position is not None:
            if is_trailing:
                if position == "long":
                    self.exit_ids[symbol] = self.replace_order(symbol, position, shares, stop_price, profit_price, self.exit_ids[symbol])
                elif position == "short":
                    self.exit_ids[symbol] = self.replace_order(symbol, position, shares, stop_price, profit_price, self.exit_ids[symbol])
                
        # --- Exit Position --- 
        elif (signal == 0 or self.force_close) and position is not None:
            fill_price = self.get_fill_price(self.exit_ids[symbol], shares, type="oco", timeout=0.25)
            exit_price = None
            
            if fill_price is None:
                self.cancel_order(self.exit_ids[symbol])
                if position == "long":
                    exit_id = self.sell_market(symbol, shares, "SELL")
                elif position == "short":
                    exit_id = self.buy_market(symbol, shares, "BUY_TO_COVER")
                fill_price = self.get_fill_price(exit_id, shares)
                exit_price = strategy.price
            else:
                if position == "long":
                    print(f"SOLD -{shares} {symbol} @ {fill_price}")
                elif position == "short":
                    print(f"BOT +{shares} {symbol} @ {fill_price}")
                stop_price_f, profit_price_f = float(stop_price), float(profit_price)
                exit_price = min([stop_price_f, profit_price_f], key=lambda x: abs(fill_price - x))
            
            self.trade_log.update_exit(symbol, position, shares, strategy.ts, exit_price, fill_price)
            self.update_pnl(strategy, position, fill_price, shares)
            self.flatten(symbol, strategy)
        
    def update_pnl(self, strategy, position, fill_price, shares):
        if position == "long":
            pnl = (fill_price - strategy.get_entry_price()) * shares
        elif position == "short":
            pnl = (strategy.get_entry_price() - fill_price) * shares
        self.cash += pnl
        strategy.get_risk_manager().update_trade(pnl)

    def flatten(self, symbol, strategy):
        self.entry_ids[symbol] = None
        self.exit_ids[symbol] = None
        strategy.flatten()

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
        order_id = self.get_order_id(response)
        fill_price = self.get_fill_price(order_id, quantity)
        print(f"BOT +{quantity} {symbol} @ {fill_price}")
        return order_id
    
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
        order_id = self.get_order_id(response)
        fill_price = self.get_fill_price(order_id, quantity)
        print(f"SOLD -{quantity} {symbol} @ {fill_price}")
        return order_id
    
    def long_bracket(self, symbol, quantity, stop_price, profit_price):
        order_dict = self.get_sell_order_dict(symbol, quantity, stop_price, profit_price)
        response = self.client.order_place(self.hash, order_dict)
        order_id = self.get_order_id(response)
        print(f"STP @ {stop_price} | LMT @ {profit_price}")
        return order_id

    def short_bracket(self, symbol, quantity, stop_price, profit_price):
        order_dict = self.get_buy_order_dict(symbol, quantity, stop_price, profit_price)
        response = self.client.order_place(self.hash, order_dict)
        order_id = self.get_order_id(response)
        print(f"STP @ {stop_price} | LMT @ {profit_price}")
        return order_id
    
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

    def get_order_id(self, response):
        order_id = response.headers.get('location', '/').split('/')[-1]
        return order_id

    def get_order_details(self, order_id):
        details = self.client.order_details(self.hash, order_id)
        details_json = details.json()
        return details_json

    def replace_order(self, symbol, position, quantity, stop_loss, take_profit, order_id):
        self.cancel_order(order_id)
        if position == "long":
            return self.long_bracket(symbol, quantity, stop_loss, take_profit)
        elif position == "short":
            return self.short_bracket(symbol, quantity, stop_loss, take_profit)

    def cancel_order(self, order_id, polling_rate=0.05):
        response = self.client.order_cancel(self.hash, order_id)
        time.sleep(polling_rate)
        return response.status_code # 200 == success; 500 == failed
        
    def get_fill_price(self, order_id, quantity, type="single", timeout=5, polling_rate=0.25): 
        start = time.time()
        while True:
            order_details = self.get_order_details(order_id)
            if type == "oco":
                order_details = next(
                    (c for c in order_details.get('childOrderStrategies', []) if c.get('status') == 'FILLED'),
                    None
                )

            if order_details and order_details.get('orderActivityCollection'):
                legs = order_details['orderActivityCollection'][0]['executionLegs']
                total_qty = sum(leg['quantity'] for leg in legs)
                if total_qty == quantity:
                    fill_price = sum(leg['price'] * leg['quantity'] for leg in legs) / total_qty
                    return round(fill_price, 2)
            
            if time.time() - start > timeout:
                return None
            time.sleep(polling_rate)

    def get_liquidation_value(self):
        details = self.client.account_details(self.hash)
        details_json = details.json()
        liquidationValue = details_json["securitiesAccount"]["currentBalances"]["liquidationValue"]
        return liquidationValue
    
    def await_stream_start(self):
        now = datetime.datetime.now(self.timezone)
        while not self.streamer.active:
            time.sleep(5)
        # check time at 6:15am
        # if not self.symbols:
        #     perform IMAP protocol position check here
        #     symbols = fetch_symbols
        #     self.initialize_strategies(symbols, self.strategy_class) 

    def stream_duration(self):
        now = datetime.datetime.now(self.timezone)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        time.sleep((market_close - now).total_seconds())
    
    def initialize_strategies(self, symbols, strategy_class):
        self.symbols = [s.split(":")[0] for s in symbols]
        self.entry_ids = {}
        self.exit_ids = {}
        self.strategies = {}
        prices = fetch_latest_prices(self.symbols)
        self.shares_to_buy = allocate_positions(symbols, prices, cash=self.cash)

        for symbol in self.symbols:
            self.entry_ids[symbol] = None
            self.exit_ids[symbol] = None

            strategy_instance = strategy_class(symbol)
            cash_allocation = prices[symbol] * self.shares_to_buy[symbol]
            strategy_instance.get_risk_manager().set_start_cash(cash_allocation)

            self.strategies[symbol] = strategy_instance

    # def initialize_strategies(self, symbols, strategy_class):
    #     self.symbols = [s.split(":")[0] for s in symbols]
    #     self.entry_ids = {}
    #     self.exit_ids = {}
    #     self.strategies = {}

    #     for symbol in self.symbols:
    #         self.entry_ids[symbol] = None
    #         self.exit_ids[symbol] = None

    #         strategy_instance = strategy_class(symbol)
    #         self.strategies[symbol] = strategy_instance

    # def allocate_cash(self, symbol, price):
    #     cash_allocation = price * self.shares_to_buy[symbol]
    #     self.strategies[symbol].get_risk_manager().set_start_cash(cash_allocation)
    #     self.prices.append(price)