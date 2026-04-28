import sys
import re
import time
import datetime
import orjson

import schwabdev

from strategies import Strategy, StrategyPair, StrategyBook
from core import OHLCVRow, Level1Row, Level2Row
from metrics import TradeManager
from utils import *

class DataFeedController:
    def __init__(self, strategy_dict, margin=1.0):
        config = load_config()

        self.client = schwabdev.Client(config['app_key'], config['app_secret'])
        self.stream = schwabdev.Stream(self.client)
        
        self.initialize(strategy_dict, margin)

        self.log_file = open(f"market_logs/market_logs_{datetime.datetime.now(timezone).date()}.jsonl", "ab")

        self.ohlcv_row = OHLCVRow()
        self.level1_row = Level1Row()
        self.level2_row = Level2Row()

    def run(self):
        def response_handler(response):
            data = orjson.loads(response).get("data")
            if not data:
                return

            for entry in data:
                service = entry["service"]
                content = entry["content"]
                timestamp = entry["timestamp"]
                for item in content:
                    symbol = item["key"]
                    if service == "CHART_EQUITY":
                        ts = item.get("7") or timestamp
                        row = self.ohlcv_row.update(
                            convert_epoch_ms(ts),
                            item.get("2"),
                            item.get("3"),
                            item.get("4"),
                            item.get("5"),
                            item.get("6")
                        )
                    elif service == "LEVELONE_EQUITIES":
                        ts = item.get('34') or item.get('37') or item.get('38') or item.get('35') or timestamp
                        row = self.level1_row.update(
                            convert_epoch_ms(ts),
                            item.get("1"),
                            item.get("2"),
                            item.get("3"),
                            item.get("4"),
                            item.get("5")
                        )
                    elif service == "NASDAQ_BOOK" or service == "NYSE_BOOK":
                        ts = item.get("1") or timestamp
                        row = self.level2_row.update(
                            convert_epoch_ms(ts),
                            item.get("2"),
                            item.get("3")
                        )
                    self.log_buffer.append(f"[{symbol}] {row}")

                    feed = self.strategy_dict[symbol]
                    strategy = feed.strategies[symbol]
                    strategy.latency = timestamp - ts
                    signal = strategy.generate_signal(row, symbol)
                    feed.interpret_signal(signal, strategy)

            if self.log_buffer:
                sys.stdout.write("\n".join(self.log_buffer) + "\n")
                self.log_file.write(orjson.dumps(self.log_buffer) + b"\n")
                self.log_buffer.clear()

        self.stream.start_auto(
            receiver=response_handler, 
            start_time=datetime.time(9, 29, 0), 
            stop_time=datetime.time(16, 0, 0), 
            on_days=[0,1,2,3,4],
            now_timezone=timezone)
        self.await_market_open()
        for feed in self.feeds:
            feed.subscribe_symbols()
        self.stream_duration()
        for feed in self.feeds:
            feed.trade_manager.save_logs()
        self.log_file.close() 
        self.construct_quote()
    
    def await_market_open(self):
        print("[PENDING] Market open pending")
        while not self.stream.active:
            time.sleep(1)
        print("[ACTIVE] Market is open")

    def stream_duration(self):
        now = datetime.datetime.now(timezone)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        time.sleep((market_close - now).total_seconds())
        while self.stream.active:
            time.sleep(1)
        print("[INACTIVE] Market is closed")

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
            elif issubclass(strategy_cl, StrategyBook):
                eb = EquityBook(items, strategy_cl, margin=margin, log_buffer=self.log_buffer, client=self.client, stream=self.stream)
                self.feeds.append(eb)
                for symbol in items:
                    self.strategy_dict[symbol] = eb

    def construct_quote(self):
        with open(f"market_logs/market_logs_{datetime.datetime.now(timezone).date()}.jsonl") as f:
            market_logs = [json.loads(line) for line in f]
        market_logs = [item for packet in market_logs for item in packet]

        quote_pattern = re.compile(
            r"\[(?P<symbol>[A-Z]+)\]\s*"
            r"timestamp=(?P<timestamp>[^,]+),\s*"
            r"bid=(?P<bid>[\d\.]+|None),\s*"
            r"ask=(?P<ask>[\d\.]+|None),\s*"
            r"last=(?P<last>[\d\.]+|None),\s*"
            r"bid_size=(?P<bid_size>\d+|None),\s*"
            r"ask_size=(?P<ask_size>\d+|None)"
        )

        parsed_data = []
        for line in market_logs:
            data = quote_pattern.search(line)
            if not data:
                continue

            quote = data.groupdict()
            quote["timestamp"] = None if quote["timestamp"] == "None" else datetime.datetime.fromisoformat(quote["timestamp"])
            for key in ["bid", "ask", "last"]:
                quote[key] = None if quote[key] == "None" else float(quote[key])
            for key in ["bid_size", "ask_size"]:
                quote[key] = None if quote[key] == "None" else int(quote[key])

            parsed_data.append(quote)

        df_quotes = pd.DataFrame(parsed_data)
        for symbol, df in df_quotes.groupby("symbol"):
            df = df.sort_values("timestamp").reset_index(drop=True)
            
            cols = ["bid", "ask", "last", "bid_size", "ask_size"]
            df[cols] = df[cols].ffill().bfill()
            df.drop(columns=['symbol'], inplace=True)
            
            try:
                old_df = open_data(symbol, mode="quote")
            except FileNotFoundError:
                old_df = pd.DataFrame()
            df = pd.concat([old_df, df], ignore_index=True)
            df.drop_duplicates(subset='timestamp', inplace=True)
            df.sort_values('timestamp', inplace=True)
            df.reset_index(drop=True, inplace=True)
            save_data(df, symbol, mode="quote")

class Instrument:
    def __init__(self, symbols, strategy_class, margin=1.0, log_buffer=None, client=None, stream=None, log_file="trade_logs_live.json"):
        config = load_config()
        self.client = client or schwabdev.Client(config['app_key'], config['app_secret'])
        self.hash = self.client.linked_accounts().json()[0].get('hashValue')
        self.stream = stream or schwabdev.Stream(self.client)

        self.cash = self.get_cash_balance() * margin
        day_trading_power = self.get_day_trading_power()
        if day_trading_power < self.cash:
            self.cash = day_trading_power
        
        if "-" in symbols[0]:
            self.symbols = [symbol for pair in symbols for symbol in pair.split("-")]
        else:
            self.symbols = symbols
        
        self.log_buffer = log_buffer if log_buffer is not None else []

        self.trade_manager = TradeManager(log_file=log_file, live=True)
        self.strategies = {}
        self.exit_ids = {}

        self.ohlcv_row = OHLCVRow()
        self.level1_row = Level1Row()
        self.level2_row = Level2Row()
 
    def initialize(self, symbols, strategy_class):
        raise NotImplementedError
       
    def subscribe_symbols(self):
        raise NotImplementedError
        
    def interpret_signal(self):
        raise NotImplementedError
        
    def update_pnl(self, strategy, direction, entry_price, exit_price, shares):
        pnl = direction * (exit_price - entry_price) * shares
        strategy.risk_manager.update_trade(pnl)

    def buy_pair(self, signal, symbol1, symbol2, shares1, shares2):
        instruction1, instruction2 = ("BUY", "SELL_SHORT") if signal else ("BUY_TO_COVER", "SELL")

        response1 = self.market_order(symbol1, shares1, instruction1)
        response2 = self.market_order(symbol2, shares2, instruction2)
        order_id1 = self.get_order_id(response1)
        order_id2 = self.get_order_id(response2)
        fill_price1 = self.get_fill_price(order_id1, timeout=0.3, polling_rate=0.1)
        fill_price2 = self.get_fill_price(order_id2, timeout=0.3, polling_rate=0.1)

        self.log_buffer.append(f"{' ' * (len(symbol1) + 3)}[BOT] +{shares1} {symbol1} @ {fill_price1}")
        self.log_buffer.append(f"{' ' * (len(symbol1) + 3)}[SOLD] -{shares2} {symbol2} @ {fill_price2}")
        return fill_price1, fill_price2

    def sell_pair(self, signal, symbol1, symbol2, shares1, shares2):
        instruction1, instruction2 = ("SELL_SHORT", "BUY") if signal else ("SELL", "BUY_TO_COVER")

        response1 = self.market_order(symbol1, shares1, instruction1)
        response2 = self.market_order(symbol2, shares2, instruction2)
        order_id1 = self.get_order_id(response1)
        order_id2 = self.get_order_id(response2)
        fill_price1 = self.get_fill_price(order_id1, timeout=0.3, polling_rate=0.1)
        fill_price2 = self.get_fill_price(order_id2, timeout=0.3, polling_rate=0.1)

        self.log_buffer.append(f"{' ' * (len(symbol1) + 3)}[SOLD] -{shares1} {symbol1} @ {fill_price1}")
        self.log_buffer.append(f"{' ' * (len(symbol1) + 3)}[BOT] +{shares2} {symbol2} @ {fill_price2}")
        return fill_price1, fill_price2
        
    def buy(self, signal, symbol, shares):
        instruction = "BUY" if signal else "BUY_TO_COVER"
        
        response = self.market_order(symbol, shares, instruction)  
        order_id = self.get_order_id(response)
        fill_price = self.get_fill_price(order_id)

        self.log_buffer.append(f"{' ' * (len(symbol) + 3)}[BOT] +{shares} {symbol} @ {fill_price}")
        return fill_price

    def sell(self, signal, symbol, shares):
        instruction = "SELL_SHORT" if signal else "SELL"

        response = self.market_order(symbol, shares, instruction)
        order_id = self.get_order_id(response)
        fill_price = self.get_fill_price(order_id)

        self.log_buffer.append(f"{' ' * (len(symbol) + 3)}[SOLD] -{shares} {symbol} @ {fill_price}")
        return fill_price
    
    def buy_oco(self, symbol, quantity, stop_price, target_price):
        response = self.oco_order(symbol, quantity, stop_price, target_price, "BUY_TO_COVER")
        order_id = self.get_order_id(response)

        self.log_buffer.append(f"{' ' * (len(symbol) + 4)}STP @ {stop_price} | LMT @ {target_price}")  
        return order_id

    def sell_oco(self, symbol, quantity, stop_price, target_price):
        response = self.oco_order(symbol, quantity, stop_price, target_price, "SELL")
        order_id = self.get_order_id(response)

        self.log_buffer.append(f"{' ' * (len(symbol) + 4)}STP @ {stop_price} | LMT @ {target_price}")  
        return order_id
    
    def market_order(self, symbol, quantity, instruction="BUY"):
        order = {
            "session": "NORMAL",
            "duration": "DAY",
            "orderType": "MARKET",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": instruction,
                    "quantity": quantity,
                    "instrument": {
                        "symbol": symbol,
                        "assetType": "EQUITY"
                    }
                }
            ]
        }

        response = self.client.place_order(self.hash, order)
        return response
    
    # def market_order(self, symbol, quantity, instruction="BUY", timeout=1, polling_rate=0.2):
    #     order = {
    #         "session": "NORMAL",
    #         "duration": "DAY",
    #         "orderType": "MARKET",
    #         "orderStrategyType": "SINGLE",
    #         "orderLegCollection": [
    #             {
    #                 "instruction": instruction,
    #                 "quantity": quantity,
    #                 "instrument": {
    #                     "symbol": symbol,
    #                     "assetType": "EQUITY"
    #                 }
    #             }
    #         ]
    #     }
        
    #     start = time.perf_counter()
    #     while True:
    #         response = self.client.place_order(self.hash, order)
    #         order_id = self.get_order_id(response)
    #         status = self.get_order_details(order_id).get('status')

    #         if status == "FILLED":
    #             return response
            
    #         if time.perf_counter() - start > timeout:
    #             return response
    #         time.sleep(polling_rate)
       
    def limit_order(self, symbol, price, quantity, instruction="BUY"):
        order = {
            "session": "NORMAL",
            "duration": "DAY",
            "orderType": "LIMIT",
            "orderStrategyType": "SINGLE",
            "price": str(price),
            "orderLegCollection": [
                {
                    "instruction": instruction,
                    "quantity": quantity,
                    "instrument": {
                        "symbol": symbol,
                        "assetType": "EQUITY",
                    },
                }
            ],
        }

        response = self.client.place_order(self.hash, order)
        return response
    
    def oco_order(self, symbol, quantity, stop_price, target_price, instruction="SELL"):
        order = {
            "orderStrategyType": "OCO",
            "childOrderStrategies": [
                {
                    "session": "NORMAL",
                    "duration": "DAY",
                    "orderType": "LIMIT",
                    "orderStrategyType": "SINGLE",
                    "price": str(target_price),
                    "orderLegCollection": [
                        {
                            "instruction": instruction,
                            "quantity": quantity,
                            "instrument": {
                                "symbol": symbol,
                                "assetType": "EQUITY"
                            }
                        }
                    ]
                },
                {
                    "session": "NORMAL",
                    "duration": "DAY",
                    "orderType": "STOP",
                    "orderStrategyType": "SINGLE",
                    "stopPrice": str(stop_price),
                    "orderLegCollection": [
                        {
                            "instruction": instruction,
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

        response = self.client.place_order(self.hash, order)
        return response

    def cancel_order(self, order_id, timeout=1, polling_rate=0.2, settle_delay=0.1):
        start = time.perf_counter()
        while True:
            self.debug_order(None, order_id) # DEBUG
            response = self.client.cancel_order(self.hash, order_id)
            status_code = response.status_code
            self.debug_order(response, order_id) # DEBUG

            if status_code == 200:
                time.sleep(settle_delay)
                return status_code
            
            if time.perf_counter() - start > timeout:
                return status_code
            time.sleep(polling_rate)
    
    def replace_order(self, order_id, direction, symbol, quantity, stop_price, target_price):
        self.cancel_order(order_id)
        if direction == 1:
            return self.sell_oco(self, symbol, quantity, stop_price, target_price)
        elif direction == -1:
            return self.buy_oco(self, symbol, quantity, stop_price, target_price)
    
    def get_order_id(self, response):
        order_id = response.headers.get('location', '/').split('/')[-1]
        return order_id

    def get_order_details(self, order_id):
        details = self.client.order_details(self.hash, order_id)
        details_json = details.json()
        return details_json
            
    def get_fill_price(self, order_id, instruction="single", timeout=5, polling_rate=0.25): 
        start = time.perf_counter()
        while True:
            order_details = self.get_order_details(order_id)
            if instruction == "oco":
                order_details = next(
                    (c for c in order_details.get('childOrderStrategies', []) if c.get('status') == 'FILLED'),
                    None
                )

            if order_details and order_details.get("status") == "FILLED":
                legs = order_details['orderActivityCollection'][0]['executionLegs']
                quantity = order_details['orderActivityCollection']["quantity"]
                total_qty = sum(leg['quantity'] for leg in legs)
                if total_qty == quantity:
                    fill_price = sum(leg['price'] * leg['quantity'] for leg in legs) / total_qty
                    return round(fill_price, 2)
                
            if order_details and order_details.get("status") == "REJECTED":
                return "REJECTED"
                             
            if time.perf_counter() - start > timeout:
                return None
            time.sleep(polling_rate)

    def debug_order(self, response=None, order_id=None):
        if response:
            self.log_buffer.append(str(response.status_code))
        if order_id:
            self.log_buffer.append(self.get_order_details(order_id).get('status'))

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

    def get_shares_owned(self, symbol):
        raise NotImplementedError

class Equities(Instrument):
    def __init__(self, symbols, strategy_class, margin=1.0, log_buffer=None, client=None, stream=None, log_file="trade_logs_live_eq.json"):
        super().__init__(symbols, strategy_class, margin, log_buffer, client, stream, log_file)
        self.initialize(symbols, strategy_class)
    
    def initialize(self, symbols, strategy_class):
        self.exit_ids = {}

        for symbol in symbols:
            strat = strategy_class(symbol)
            cash_allocation = round(self.cash / len(symbols), 2)
            strat.risk_manager.start_cash = cash_allocation
            self.strategies[symbol] = strat
            print(
                f"[INIT] {strat.__class__.__name__:15} | "
                f"symbol={symbol:10} | cash=${cash_allocation}"
            )

    def subscribe_symbols(self):
        self.stream.send(self.stream.chart_equity(self.symbols, "0,1,2,3,4,5,6,7", command="ADD"))

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
            fill_price = self.buy(signal, symbol, shares)
            if fill_price == "REJECTED":
                position_manager.remove_leg(leg)
                return
            self.exit_ids[leg] = self.sell_oco(symbol, shares, stop_price, target_price)
            leg.entry_price = fill_price if fill_price is not None else entry_price
            self.trade_manager.log_entry(name, leg, symbol, direction, position_size, shares, strategy.ts, entry_price, fill_price, stop_price, target_price, strategy.features)

        # --- Enter Short ---
        elif signal == -1:
            fill_price = self.sell(signal, symbol, shares)
            if fill_price == "REJECTED":
                position_manager.remove_leg(leg)
                return
            self.exit_ids[leg] = self.buy_oco(symbol, shares, stop_price, target_price)
            leg.entry_price = fill_price if fill_price is not None else entry_price
            self.trade_manager.log_entry(name, leg, symbol, direction, position_size, shares, strategy.ts, entry_price, fill_price, stop_price, target_price, strategy.features)

        # --- Adjust Stops / Targets ---
        elif signal == 9:
            self.exit_ids[leg] = self.replace_order(self.exit_ids[leg], direction, symbol, shares, stop_price, target_price)
                
        # --- Exit Position --- 
        elif signal == 0:
            for leg in position_manager.legs.copy():
                if leg.check_exit(strategy.ts, strategy.low, strategy.high) == signal:
                    entry_price = leg.entry_price
                    stop_price = leg.stop_price
                    target_price = leg.target_price
                    shares = leg.shares

                    fill_price = self.get_fill_price(self.exit_ids[leg], instruction="oco", timeout=1)

                    if fill_price is None:
                        self.cancel_order(self.exit_ids[leg])

                        # TODO: handle partial fills
                        # shares_remaining = shares - self.get_shares_owned(symbol)
                        if direction == 1:
                            fill_price = self.sell(signal, symbol, shares)
                        elif direction == -1:
                            fill_price = self.buy(signal, symbol, shares)
                        exit_price = strategy.close
                    else:
                        if direction == 1:
                            self.log_buffer.append(f"{' ' * (len(symbol) + 3)}[SOLD] -{shares} {symbol} @ {fill_price}")
                        elif direction == -1:
                            self.log_buffer.append(f"{' ' * (len(symbol) + 3)}[BOT] +{shares} {symbol} @ {fill_price}")
                        exit_price = min([stop_price, target_price], key=lambda x: abs(fill_price - x))
                    
                    fill_price = fill_price if fill_price is not None else exit_price
                    self.trade_manager.update_exit(leg, strategy.ts, exit_price, fill_price)
                    self.update_pnl(strategy, direction, entry_price, fill_price, shares)
                    self.exit_ids.pop(leg)
                    position_manager.remove_leg(leg)

class EquityPairs(Instrument):
    def __init__(self, pairs, strategy_class, margin=1.0, log_buffer=None, client=None, stream=None, log_file="trade_logs_live_pt.json"):
        super().__init__(pairs, strategy_class, margin, log_buffer, client, stream, log_file)
        self.initialize(pairs, strategy_class)
 
    def initialize(self, pairs, strategy_class):
        for pair in pairs:
            strat = strategy_class(pair)
            cash_allocation = round(self.cash / len(pairs), 2)
            strat.risk_manager.start_cash = cash_allocation
            symbol1, symbol2 = pair.split("-")
            self.strategies[symbol1] = strat
            self.strategies[symbol2] = strat
            print(
                f"[INIT] {strat.__class__.__name__:15} | "
                f"pair={pair:12} | cash=${cash_allocation}"
            )

    def subscribe_symbols(self):
        self.stream.send(self.stream.level_one_equities(self.symbols, "0,1,2,3,4,5,34,35,37,38", command="ADD"))

    def interpret_signal(self, signal, strategy):
        name = strategy.__class__.__name__
        symbol1, symbol2 = strategy.symbol1, strategy.symbol2
        s1, s2 = strategy.s1, strategy.s2
        position_manager = strategy.position_manager
        if position_manager.in_trade():
            leg1, leg2 = position_manager.pairs[-1]
            direction1 = leg1.direction
            direction2 = leg2.direction
            entry_price1 = leg1.entry_price
            entry_price2 = leg2.entry_price
            position_size1 = leg1.position_size
            position_size2 = leg2.position_size
            shares1 = leg1.shares
            shares2 = leg2.shares

        # --- Enter Long/Short ---
        if signal == 1:
            fill_price1, fill_price2 = self.buy_pair(signal, symbol1, symbol2, shares1, shares2)
            if fill_price1 == "REJECTED" or fill_price2 == "REJECTED":
                position_manager.remove_pair(leg1, leg2)
                if fill_price1 == "REJECTED" and fill_price2 == "REJECTED":
                    return
                if fill_price1 == "REJECTED":
                    self.buy(0, symbol2, shares2)
                if fill_price2 == "REJECTED":
                    self.sell(0, symbol1, shares1)
                return
            leg1.entry_price = fill_price1 if fill_price1 is not None else entry_price1
            leg2.entry_price = fill_price2 if fill_price2 is not None else entry_price2
            self.trade_manager.log_entry(name, leg1, symbol1, direction1, position_size1, shares1, s1["ts"], entry_price1, fill_price1, None, None, strategy.features)
            self.trade_manager.log_entry(name, leg2, symbol2, direction2, position_size2, shares2, s2["ts"], entry_price2, fill_price2, None, None, strategy.features)

        # --- Enter Short/Long ---
        elif signal == -1:
            fill_price1, fill_price2 = self.sell_pair(signal, symbol1, symbol2, shares1, shares2)
            if fill_price1 == "REJECTED" or fill_price2 == "REJECTED":
                position_manager.remove_pair(leg1, leg2)
                if fill_price1 == "REJECTED" and fill_price2 == "REJECTED":
                    return
                if fill_price1 == "REJECTED":
                    self.sell(0, symbol2, shares2)
                if fill_price2 == "REJECTED":
                    self.buy(0, symbol1, shares1)
                return
            leg1.entry_price = fill_price1 if fill_price1 is not None else entry_price1
            leg2.entry_price = fill_price2 if fill_price2 is not None else entry_price2
            self.trade_manager.log_entry(name, leg1, symbol1, direction1, position_size1, shares1, s1["ts"], entry_price1, fill_price1, None, None, strategy.features)
            self.trade_manager.log_entry(name, leg2, symbol2, direction2, position_size2, shares2, s2["ts"], entry_price2, fill_price2, None, None, strategy.features)
        
        # --- Exit Position --- 
        elif signal == 0:
            shares1, shares2 = position_manager.total_shares()
            if direction1 == 1:
                fill_price1, fill_price2 = self.sell_pair(signal, symbol1, symbol2, shares1, shares2)
                exit_price1, exit_price2 = s1["bid"], s2["ask"]
            elif direction1 == -1:
                fill_price1, fill_price2 = self.buy_pair(signal, symbol1, symbol2, shares1, shares2)
                exit_price1, exit_price2 = s1["ask"], s2["bid"]

            for leg1, leg2 in position_manager.pairs.copy():
                entry_price1 = leg1.entry_price
                entry_price2 = leg2.entry_price
                shares1 = leg1.shares
                shares2 = leg2.shares
                    
                fill_price1 = fill_price1 if fill_price1 is not None else exit_price1
                fill_price2 = fill_price2 if fill_price2 is not None else exit_price2
                self.trade_manager.update_exit(leg1, s1["ts"], exit_price1, fill_price1)
                self.trade_manager.update_exit(leg2, s2["ts"], exit_price2, fill_price2)
                self.update_pnl(strategy, direction1, entry_price1, fill_price1, shares1)
                self.update_pnl(strategy, direction2, entry_price2, fill_price2, shares2)
                position_manager.remove_pair(leg1, leg2)

class EquityBook(Instrument):
    def __init__(self, symbols, strategy_class, margin=1.0, log_buffer=None, client=None, stream=None, log_file="trade_logs_live_eb.json"):
        super().__init__(symbols, strategy_class, margin, log_buffer, client, stream, log_file)
        self.initialize(symbols, strategy_class)
    
    def initialize(self, symbols, strategy_class):
        for symbol in symbols:
            strat = strategy_class(symbol)
            cash_allocation = round(self.cash / len(symbols), 2)
            strat.risk_manager.start_cash = cash_allocation
            self.strategies[symbol] = strat
            print(
                f"[INIT] {strat.__class__.__name__:15} | "
                f"symbol={symbol:10} | cash=${cash_allocation}"
            )

    def subscribe_symbols(self):
        self.stream.send(self.stream.nasdaq_book(self.symbols, "0,1,2,3,4", command="ADD"))

    def interpret_signal(self, signal, strategy):
        # TODO: complete this
        return