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
        self.hash = self.client.linked_accounts().json()[0].get('hashValue')
        self.stream = schwabdev.Stream(self.client)

        self.cash = self.get_liquidation_value() * margin
        self.timezone = ZoneInfo("America/New_York")
        self.symbols = symbols if isinstance(symbols, list) else [symbols]
        self.initialize(symbols, strategy_class)

        self.trade_manager = TradeManager(log_file="trade_logs_live.json", live=True)
        self.Row = namedtuple("Row", ["timestamp", "open", "high", "low", "close", "volume"])
        
        # new trade manager with backtest files and put into here
        # self.strategy.trade_manager = self.trade_manager

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
                print(f"[{symbol}] {row}")

                signal = strategy.generate_signal(row)
                self.interpret_signal(signal, strategy, symbol)

        self.stream.start_auto(
            receiver=response_handler, 
            start_time=datetime.time(9, 30, 0), 
            stop_time=datetime.time(16, 0, 0), 
            on_days=(0,1,2,3,4))
        self.await_market_open()
        self.stream.send(self.stream.chart_equity(self.symbols, "0,1,2,3,4,5,6,7,8", command="SUBS"))
        self.stream_duration()

        self.trade_manager.save_logs()

    def interpret_signal(self, signal, strategy, symbol):
        name = strategy.__class__.__name__
        position_manager = strategy.position_manager
        direction = position_manager.direction()
        if direction:
            leg = position_manager.legs[-1]
            entry_price = leg.entry_price
            stop_price = leg.stop_price
            target_price = leg.target_price
            position_size = leg.position_size
            shares = leg.shares
        
        # --- Enter Long ---
        if signal == 1:
            self.entry_ids[leg], fill_price = self.buy_market(symbol, shares, "BUY")
            self.exit_ids[leg] = self.long_bracket(symbol, shares, stop_price, target_price)
            leg.entry_price = fill_price
            self.trade_manager.log_entry(name, leg, symbol, direction, position_size, shares, strategy.ts, entry_price, fill_price, stop_price, target_price, strategy.features)

        # --- Enter Short ---
        elif signal == -1:
            self.entry_ids[leg], fill_price = self.sell_market(symbol, shares, "SELL_SHORT")
            self.exit_ids[leg] = self.short_bracket(symbol, shares, stop_price, target_price)
            leg.entry_price = fill_price
            self.trade_manager.log_entry(name, leg, symbol, direction, position_size, shares, strategy.ts, entry_price, fill_price, stop_price, target_price, strategy.features)

        # --- Adjust Stops / Targets ---
        elif signal == 9:
            raise NotImplementedError
            if direction == 1:
                self.exit_ids[leg] = self.replace_order(symbol, direction, shares, stop_price, target_price, self.exit_ids[leg])
            elif direction == -1:
                self.exit_ids[leg] = self.replace_order(symbol, direction, shares, stop_price, target_price, self.exit_ids[leg])
                
        # --- Exit Position --- 
        elif signal == 0:
            for leg in position_manager.legs.copy():
                if leg.check_exit(strategy.ts, strategy.low, strategy.high) == signal:
                    entry_price = leg.entry_price
                    stop_price = leg.stop_price
                    target_price = leg.target_price
                    shares = leg.shares

                    fill_price = self.get_fill_price(self.exit_ids[leg], shares, type="oco", timeout=0.25)
                    # implement partial fill check
                    
                    if fill_price is None:
                        self.cancel_order(self.exit_ids[leg])
                        if direction == 1:
                            _, fill_price = self.sell_market(symbol, shares, "SELL")
                        elif direction == -1:
                            _, fill_price = self.buy_market(symbol, shares, "BUY_TO_COVER")
                        exit_price = strategy.price
                    else:
                        if direction == 1:
                            print(f" [SOLD] -{shares} {symbol} @ {fill_price}")
                        elif direction == -1:
                            print(f" [BOT] +{shares} {symbol} @ {fill_price}")
                        exit_price = min([stop_price, target_price], key=lambda x: abs(fill_price - x))
                
                    self.update_pnl(strategy, direction, entry_price, fill_price, shares)
                    self.trade_manager.update_exit(leg, strategy.ts, exit_price, fill_price)
                    self.entry_ids.pop(leg)
                    self.exit_ids.pop(leg)
                    position_manager.remove_leg(leg)

    def update_pnl(self, strategy, direction, entry_price, exit_price, shares):
        pnl = direction * (exit_price - entry_price) * shares
        self.cash += pnl
        strategy.risk_manager.update_trade(pnl)

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

        response = self.client.place_order(self.hash, order_dict)
        order_id = self.get_order_id(response)
        fill_price = self.get_fill_price(order_id, quantity)
        print(f" [BOT] +{quantity} {symbol} @ {fill_price}")
        return order_id, fill_price
    
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

        response = self.client.place_order(self.hash, order_dict)
        order_id = self.get_order_id(response)
        fill_price = self.get_fill_price(order_id, quantity)
        print(f" [SOLD] -{quantity} {symbol} @ {fill_price}")
        return order_id, fill_price
    
    def long_bracket(self, symbol, quantity, stop_price, target_price):
        order_dict = self.get_sell_order_dict(symbol, quantity, stop_price, target_price)
        response = self.client.place_order(self.hash, order_dict)
        order_id = self.get_order_id(response)
        print(f" STP={stop_price} | LMT={target_price}")
        return order_id

    def short_bracket(self, symbol, quantity, stop_price, target_price):
        order_dict = self.get_buy_order_dict(symbol, quantity, stop_price, target_price)
        response = self.client.place_order(self.hash, order_dict)
        order_id = self.get_order_id(response)
        print(f" STP={stop_price} | LMT={target_price}")
        return order_id
    
    def get_buy_order_dict(self, symbol, quantity, stop_price, target_price):
        order_dict = {
            "orderStrategyType": "OCO",
            "childOrderStrategies": [
                {
                    "orderType": "LIMIT",
                    "session": "NORMAL",
                    "price": str(target_price),
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
                    "stopPrice": str(stop_price),
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
    
    def get_sell_order_dict(self, symbol, quantity, stop_price, target_price):
        order_dict = {
            "orderStrategyType": "OCO",
            "childOrderStrategies": [
                {
                    "orderType": "LIMIT",
                    "session": "NORMAL",
                    "price": str(target_price),
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
                    "stopPrice": str(stop_price),
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

    def replace_order(self, symbol, direction, quantity, stop_loss, take_profit, order_id):
        self.cancel_order(order_id)
        if direction == 1:
            return self.long_bracket(symbol, quantity, stop_loss, take_profit)
        elif direction == -1:
            return self.short_bracket(symbol, quantity, stop_loss, take_profit)

    def cancel_order(self, order_id, polling_rate=0.05):
        response = self.client.cancel_order(self.hash, order_id)
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
                # implement partial fill check
            
            if time.time() - start > timeout:
                return None
            time.sleep(polling_rate)

    def get_liquidation_value(self):
        details = self.client.account_details(self.hash)
        details_json = details.json()
        liquidationValue = details_json["securitiesAccount"]["currentBalances"]["liquidationValue"]
        return liquidationValue
    
    def await_market_open(self):
        print("[WAIT] Market open pending")
        while not self.stream.active:
            time.sleep(5)
        print("[ACTIVE] Market is open")

    def stream_duration(self):
        now = datetime.datetime.now(self.timezone)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        time.sleep((market_close - now).total_seconds())
    
    def initialize(self, symbols, strategy_class):
        self.entry_ids = {}
        self.exit_ids = {}
        self.strategies = {}

        for symbol in symbols:
            strat = strategy_class(symbol)
            cash_allocation = round(self.cash / len(symbols), 2)
            strat.risk_manager.start_cash = cash_allocation
            self.strategies[symbol] = strat
            print(
                f"[INIT] {strat.__class__.__name__:10} | "
                f"symbol={symbol:5} | cash=${cash_allocation}"
            )
