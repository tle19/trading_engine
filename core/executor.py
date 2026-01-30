import json
import time
import datetime
import sys
import pandas as pd
from collections import namedtuple

from zoneinfo import ZoneInfo
import orjson
import schwabdev

from strategies import Strategy, StrategyPair
from core import OHLCVRow, BidAskRow
from metrics import *
from utils import *

class DataFeedController:
    def __init__(self, strategy_dict, margin=1.0):
        config = load_config()

        self.client = schwabdev.Client(config['app_key'], config['app_secret'])
        self.stream = schwabdev.Stream(self.client)
        
        self.timezone = ZoneInfo("America/New_York")
        self.initialize(strategy_dict, margin)

        self.ohlcv_Row = OHLCVRow()
        self.bidask_Row = BidAskRow()

    def run(self):
        def response_handler(response):
            data = orjson.loads(response).get("data")
            if not data:
                return

            for entry in data:
                service = entry["service"]
                content = entry["content"]
                for item in content:
                    symbol = item["key"]
                    if service == "CHART_EQUITY":
                        row = self.ohlcv_Row.update(
                            pd.to_datetime(item.get("7"), unit='ms', utc=True).tz_convert(self.timezone),
                            item.get("2"),
                            item.get("3"),
                            item.get("4"),
                            item.get("5"),
                            item.get("6")
                        )
                    elif service == "LEVELONE_EQUITIES":
                        row = self.bidask_Row.update(
                            item.get('34') or item.get('37') or item.get('38') or item.get('35'),
                            item.get("1"),
                            item.get("2"),
                            item.get("3"),
                            item.get("4"),
                            item.get("5")
                        )
                    self.log_buffer.append(f"[{symbol}] {row}")

                    feed = self.strategy_dict[symbol]
                    strategy = feed.strategies[symbol]
                    signal = strategy.generate_signal(row, symbol)
                    feed.interpret_signal(signal, strategy)
            
            if self.log_buffer:
                sys.stdout.write("\n".join(self.log_buffer) + "\n")
                self.log_buffer.clear()

        self.stream.start_auto(
            receiver=response_handler, 
            start_time=datetime.time(9, 30, 0), 
            stop_time=datetime.time(16, 0, 0), 
            on_days=(0,1,2,3,4))
        self.await_market_open()
        for feed in self.feeds:
            feed.subscribe_symbols()
        self.stream_duration()
        for feed in self.feeds:
            feed.save_logs()
    
    def await_market_open(self):
        print("[WAIT] Market open pending")
        while not self.stream.active:
            time.sleep(5)
        print("[ACTIVE] Market is open")

    def stream_duration(self):
        now = datetime.datetime.now(self.timezone)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        time.sleep((market_close - now).total_seconds())

    def initialize(self, strategy_dict, margin):
        self.strategy_dict = {}
        self.log_buffer = []
        self.feeds = []

        for strategy_cl, items in strategy_dict.items():
            if issubclass(strategy_cl, Strategy):
                eq = Equities(items, strategy_cl, margin=margin, log_buffer=self.log_buffer, client=self.client, stream=self.stream)
                self.feeds.append(eq)
                for symbol in items:
                    self.strategy_dict[symbol] = eq
            elif issubclass(strategy_cl, StrategyPair):
                ep = EquityPairs(items, strategy_cl, margin=margin, log_buffer=self.log_buffer, client=self.client, stream=self.stream)
                self.feeds.append(ep)
                for pair in items:
                    symbol1, symbol2 = pair.split("-")
                    self.strategy_dict[symbol1] = ep
                    self.strategy_dict[symbol2] = ep
                

class Equities:
    def __init__(self, symbols, strategy_class, margin=1.0, log_buffer=None, client=None, stream=None):
        config = load_config()

        self.client = client or schwabdev.Client(config['app_key'], config['app_secret'])
        self.hash = self.client.linked_accounts().json()[0].get('hashValue')
        self.stream = stream or schwabdev.Stream(self.client)

        self.cash = self.get_cash_balance() * margin
        day_trading_power = self.get_day_trading_power()
        if day_trading_power < self.cash:
            raise ValueError(f"Insufficient day trading power: available ${day_trading_power}")
        self.timezone = ZoneInfo("America/New_York")
        self.symbols = symbols if isinstance(symbols, list) else [symbols]
        self.initialize(symbols, strategy_class)

        self.trade_manager = TradeManager(log_file="trade_logs_live_eq.json", live=True)
        self.log_buffer = log_buffer if log_buffer is not None else []

        self.Row = OHLCVRow()

    def run(self):
        def response_handler(response):
            data = json.loads(response).get("data", [])
            if not data:
                return

            for entry in data:
                content = entry["content"]
                for item in content:
                    symbol = item["key"]

                    row = self.Row.update(
                        pd.to_datetime(item.get("7"), unit='ms', utc=True).tz_convert(self.timezone),
                        item.get("2"),
                        item.get("3"),
                        item.get("4"),
                        item.get("5"),
                        item.get("6")
                    )
                    self.log_buffer.append(f"[{symbol}] {row}")

                    strategy = self.strategies[symbol]
                    signal = strategy.generate_signal(row)
                    self.interpret_signal(signal, strategy)

            if self.log_buffer:
                sys.stdout.write("\n".join(self.log_buffer) + "\n")
                self.log_buffer.clear()

        self.stream.start_auto(
            receiver=response_handler, 
            start_time=datetime.time(9, 30, 0), 
            stop_time=datetime.time(16, 0, 0), 
            on_days=(0,1,2,3,4))
        self.await_market_open()
        self.stream.send(self.stream.chart_equity(self.symbols, "0,1,2,3,4,5,6,7", command="SUBS"))
        self.stream_duration()

        self.save_logs()

    def subscribe_symbols(self):
        self.stream.send(self.stream.chart_equity(self.symbols, "0,1,2,3,4,5,6,7", command="ADD"))
    
    def save_logs(self):
        self.trade_manager.save_logs()

    def interpret_signal(self, signal, strategy):
        name = strategy.__class__.__name__
        symbol = strategy.symbol
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

                    fill_price = self.get_fill_price(self.exit_ids[leg], shares, type="oco", timeout=1)
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
                            self.log_buffer.append(f" [SOLD] -{shares} {symbol} @ {fill_price}")
                        elif direction == -1:
                            self.log_buffer.append(f" [BOT] +{shares} {symbol} @ {fill_price}")
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
        self.log_buffer.append(f" [BOT] +{quantity} {symbol} @ {fill_price}")
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
        self.log_buffer.append(f" [SOLD] -{quantity} {symbol} @ {fill_price}")
        return order_id, fill_price
    
    def long_bracket(self, symbol, quantity, stop_price, target_price):
        order_dict = self.get_sell_order_dict(symbol, quantity, stop_price, target_price)
        response = self.client.place_order(self.hash, order_dict)
        order_id = self.get_order_id(response)
        self.log_buffer.append(f" STP={stop_price} | LMT={target_price}")
        return order_id

    def short_bracket(self, symbol, quantity, stop_price, target_price):
        order_dict = self.get_buy_order_dict(symbol, quantity, stop_price, target_price)
        response = self.client.place_order(self.hash, order_dict)
        order_id = self.get_order_id(response)
        self.log_buffer.append(f" STP={stop_price} | LMT={target_price}")
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
        
    def get_fill_price(self, order_id, quantity, type="single", timeout=10, polling_rate=0.25): 
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

    def get_cash_balance(self):
        details = self.client.account_details(self.hash)
        details_json = details.json()
        cash_balance = details_json["securitiesAccount"]["currentBalances"]["cashBalance"]
        return cash_balance
    
    def get_day_trading_power(self):
        details = self.client.account_details(self.hash)
        details_json = details.json()
        day_trading_power = details_json["securitiesAccount"]["currentBalances"]["dayTradingBuyingPower"]
        return day_trading_power
    
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



class EquityPairs:
    def __init__(self, pairs, strategy_class, margin=1.0, log_buffer=None, client=None, stream=None):
        config = load_config()

        self.client = client or schwabdev.Client(config['app_key'], config['app_secret'])
        self.hash = self.client.linked_accounts().json()[0].get('hashValue')
        self.stream = stream or schwabdev.Stream(self.client)

        self.cash = self.get_cash_balance() * margin
        day_trading_power = self.get_day_trading_power()
        if day_trading_power < self.cash:
            raise ValueError(f"Insufficient day trading power: available ${day_trading_power}")
        self.timezone = ZoneInfo("America/New_York")
        self.symbols = [symbol for pair in pairs for symbol in pair.split("-")]
        self.initialize(pairs, strategy_class)

        self.trade_manager = TradeManager(log_file="trade_logs_live_pt.json", live=True)
        self.log_buffer = log_buffer if log_buffer is not None else []

        self.Row = BidAskRow()

    def run(self):
        def response_handler(response):
            data = orjson.loads(response).get("data")
            if not data:
                return

            for entry in data:
                content = entry["content"]
                for item in content:
                    symbol = item["key"]

                    row = self.Row.update(
                        item.get('34') or item.get('37') or item.get('38') or item.get('35'),
                        item.get("1"),
                        item.get("2"),
                        item.get("3"),
                        item.get("4"),
                        item.get("5")
                    )
                    self.log_buffer.append(f"[{symbol}] {row}")

                    strategy = self.strategies[symbol]
                    signal = strategy.generate_signal(row, symbol)
                    self.interpret_signal(signal, strategy)
            
            if self.log_buffer:
                sys.stdout.write("\n".join(self.log_buffer) + "\n")
                self.log_buffer.clear()

            # timing
            # s = time.perf_counter()
            # sys.stdout.write(f"{1000*(time.perf_counter() - s):.3f}\n")

        self.stream.start_auto(
            receiver=response_handler, 
            start_time=datetime.time(9, 30, 0), 
            stop_time=datetime.time(16, 0, 0), 
            on_days=(0,1,2,3,4))
        self.await_market_open()
        self.stream.send(self.stream.level_one_equities(self.symbols, "0,1,2,3,4,5,34,35,37,38", command="SUBS"))
        self.stream_duration()

        self.save_logs()
    
    def subscribe_symbols(self):
        self.stream.send(self.stream.level_one_equities(self.symbols, "0,1,2,3,4,5,34,35,37,38", command="ADD"))
        
    def save_logs(self):
        self.trade_manager.save_logs()

    def interpret_signal(self, signal, strategy):
        name = strategy.__class__.__name__
        symbol1, symbol2 = strategy.symbol1, strategy.symbol2
        s1, s2 = strategy.s1, strategy.s2
        
        # --- Enter Long/Short ---
        if signal == 1:
            fill_price1, fill_price2 = self.buy_pair(signal, symbol1, symbol2, s1["shares"], s2["shares"])
            s1["entry_price"], s2["entry_price"] = fill_price1, fill_price2
            self.trade_manager.log_entry(name, symbol1, symbol1, s1["direction"], 1.0, s1["shares"], s1["ts"], s1["ask"], fill_price1, None, s1["target_price"])
            self.trade_manager.log_entry(name, symbol2, symbol2, s2["direction"], 1.0, s2["shares"], s2["ts"], s2["bid"], fill_price2, None, s2["target_price"])

        # --- Enter Short/Long ---
        elif signal == -1:
            fill_price1, fill_price2 = self.sell_pair(signal, symbol1, symbol2, s1["shares"], s2["shares"])
            s1["entry_price"], s2["entry_price"] = fill_price1, fill_price2
            self.trade_manager.log_entry(name, symbol1, symbol1, symbol1, s1["direction"], 1.0, s1["shares"], s1["ts"], s1["bid"], fill_price1, None, None)
            self.trade_manager.log_entry(name, symbol2, symbol2, symbol2, s2["direction"], 1.0, s2["shares"], s2["ts"], s2["ask"], fill_price2, None, None)
                
        # --- Exit Position --- 
        elif signal == 0:
            if s1["direction"] == 1:
                fill_price1, fill_price2 = self.sell_pair(signal, symbol1, symbol2, s1["shares"])
                self.trade_manager.update_exit(symbol1, s1["ts"], s1["bid"], fill_price1)
                self.trade_manager.update_exit(symbol2, s2["ts"], s2["ask"], fill_price2)
            elif s1["direction"] == -1:
                fill_price1, fill_price2 = self.buy_pair(signal, symbol1, symbol2, s1["shares"])
                self.trade_manager.update_exit(symbol1, s1["ts"], s1["ask"], fill_price1)
                self.trade_manager.update_exit(symbol2, s2["ts"], s2["bid"], fill_price2)

            self.update_pnl(strategy, s1["direction"], s1["entry_price"], fill_price1, s1["shares"])
            self.update_pnl(strategy, s2["direction"], s2["entry_price"], fill_price2, s2["shares"])
            s1["direction"], s2["direction"]  = 0, 0

    def update_pnl(self, strategy, direction, entry_price, exit_price, shares):
        pnl = direction * (exit_price - entry_price) * shares
        self.cash += pnl
        strategy.risk_manager.update_trade(pnl)

    def buy_pair(self, signal, symbol1, symbol2, shares1, shares2):
        if signal:
            response1 = self.market_order(symbol1, shares1, type="BUY")
            response2 = self.market_order(symbol2, shares2, type="SELL_SHORT")
        else:
            response1 = self.market_order(symbol1, shares1, type="BUY_TO_COVER")
            response2 = self.market_order(symbol2, shares2, type="SELL")

        order_id1 = self.get_order_id(response1)
        order_id2 = self.get_order_id(response2)
        fill_price1 = self.get_fill_price(order_id1, shares1)
        fill_price2 = self.get_fill_price(order_id2, shares2)
        self.log_buffer.append(f" [BOT] +{shares1} {symbol1} @ {fill_price1}")
        self.log_buffer.append(f" [SOLD] -{shares2} {symbol2} @ {fill_price2}")
        return fill_price1, fill_price2

    def sell_pair(self, signal, symbol1, symbol2, shares1, shares2):
        if signal:
            response1 = self.market_order(symbol1, shares1, type="SELL_SHORT")
            response2 = self.market_order(symbol2, shares2, type="BUY")
        else:
            response1 = self.market_order(symbol1, shares1, type="SELL")
            response2 = self.market_order(symbol2, shares2, type="BUY_TO_COVER")
        
        order_id1 = self.get_order_id(response1)
        order_id2 = self.get_order_id(response2)
        fill_price1 = self.get_fill_price(order_id1, shares1)
        fill_price2 = self.get_fill_price(order_id2, shares2)
        self.log_buffer.append(f" [SOLD] -{shares1} {symbol1} @ {fill_price1}")
        self.log_buffer.append(f" [BOT] +{shares2} {symbol2} @ {fill_price2}")
        return fill_price1, fill_price2

    def market_order(self, symbol, quantity, type="BUY"):
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
        return response

    def get_order_id(self, response):
        order_id = response.headers.get('location', '/').split('/')[-1]
        return order_id

    def get_order_details(self, order_id):
        details = self.client.order_details(self.hash, order_id)
        details_json = details.json()
        return details_json
        
    def get_fill_price(self, order_id, quantity, timeout=5, polling_rate=0.25): 
        start = time.time()
        while True:
            order_details = self.get_order_details(order_id)

            if order_details and order_details.get('orderActivityCollection'):
                legs = order_details['orderActivityCollection'][0]['executionLegs']
                total_qty = sum(leg['quantity'] for leg in legs)
                if total_qty == quantity:
                    fill_price = sum(leg['price'] * leg['quantity'] for leg in legs) / total_qty
                    return round(fill_price, 2)
            
            if time.time() - start > timeout:
                return None
            time.sleep(polling_rate)

    def get_cash_balance(self):
        details = self.client.account_details(self.hash)
        details_json = details.json()
        cash_balance = details_json["securitiesAccount"]["currentBalances"]["cashBalance"]
        return cash_balance
    
    def get_day_trading_power(self):
        details = self.client.account_details(self.hash)
        details_json = details.json()
        day_trading_power = details_json["securitiesAccount"]["currentBalances"]["dayTradingBuyingPower"]
        return day_trading_power
    
    def await_market_open(self):
        print("[WAIT] Market open pending")
        while not self.stream.active:
            time.sleep(5)
        print("[ACTIVE] Market is open")

    def stream_duration(self):
        now = datetime.datetime.now(self.timezone)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        time.sleep((market_close - now).total_seconds())
    
    def initialize(self, pairs, strategy_class):
        self.strategies = {}

        for pair in pairs:
            strat = strategy_class(pair)
            cash_allocation = round(self.cash / len(pairs), 2)
            strat.risk_manager.start_cash = cash_allocation
            symbol1, symbol2 = pair.split("-")
            self.strategies[symbol1] = strat
            self.strategies[symbol2] = strat
            print(
                f"[INIT] {strat.__class__.__name__:10} | "
                f"symbol={pair:5} | cash=${cash_allocation}"
            )