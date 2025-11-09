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

        self.client = schwabdev.Client(config['app_key'], config['app_secret'])
        self.hash = self.client.account_linked().json()[0]['hashValue']
        self.streamer = self.client.stream

        self.timezone = ZoneInfo("America/New_York")
        self.cash = self.get_liquidation_value() * margin
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

        self.force_close = False
        self.trade_logger = TradeLogger()
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

        self.streamer.start(response_handler) # start_auto for full automation
        self.streamer.send(self.streamer.chart_equity(self.symbols, "0,1,2,3,4,5,6,7,8", command="SUBS"))
        time.sleep(duration) # duration is time to market close
        self.streamer.stop()

        self.trade_logger.output_logs()

    def interpret_signal(self, signal, strategy, symbol):
        is_trailing_stop = strategy.is_trailing_stop()
        stop_price = str(strategy.get_stop_price())
        profit_price = str(strategy.get_profit_price())
        position = strategy.get_position()
        position_size = strategy.get_position_size()
        shares = max(1, int(self.shares_to_buy[symbol] * position_size))
        shares = 1 # for testing
        
        # --- Enter Long ---
        if signal == 1 and position == "long":
            self.entry_responses[symbol] = self.buy_market(symbol, shares, "BUY")
            self.hold_responses[symbol] = self.long_bracket(symbol, shares, stop_price, profit_price)
            fill_price = self.get_fill_price(self.entry_responses[symbol])
            self.trade_logger.log_entry(symbol, position, shares, strategy.get_time(), strategy.get_price(), fill_price)
            strategy.update_entry_price(fill_price)

        # --- Enter Short ---
        elif signal == -1 and position == "short":
            self.entry_responses[symbol] = self.sell_market(symbol, shares, "SELL_SHORT")
            self.hold_responses[symbol] = self.short_bracket(symbol, shares, stop_price, profit_price)
            fill_price = self.get_fill_price(self.entry_responses[symbol])
            self.trade_logger.log_entry(symbol, position, shares, strategy.get_time(), strategy.get_price(), fill_price)
            strategy.update_entry_price(fill_price)

        # --- Holding ---
        elif signal is None and position is not None:
            if is_trailing_stop:
                if position == "long":
                    self.hold_responses[symbol] = self.replace_order(symbol, shares, position, stop_price, profit_price, self.hold_responses[symbol])
                elif position == "short":
                    self.hold_responses[symbol] = self.replace_order(symbol, shares, position, stop_price, profit_price, self.hold_responses[symbol])
                
        # --- Exit (Auto) --- 
        elif signal == 0 and position is not None:
            fill_price = self.get_fill_price(self.hold_responses[symbol])

            if position == "long":
                self.trade_logger.update_exit(symbol, position, strategy.get_time(), strategy.get_price(), fill_price)
                print(f"SELL -{shares} {symbol} @ {fill_price}")
            elif position == "short":
                self.trade_logger.update_exit(symbol, position, strategy.get_time(), strategy.get_price(), fill_price)
                print(f"BOT +{shares} {symbol} @ {fill_price}")
            
            self.update_pnl(strategy, position, fill_price, shares)
            self.flatten(symbol, strategy)

        # --- Exit (Manual) --- 
        elif False:
            response = self.cancel_order(self.hold_responses[symbol])
            # Empty if successful (meaning if it exists still)
            if response is empty:
                if position == "long":
                    response = self.sell_market(symbol, shares, "SELL")
                    fill_price = self.get_fill_price(response)
                    self.trade_logger.update_exit(symbol, position, strategy.get_time(), strategy.get_price(), fill_price)
                elif position == "short":
                    response = self.buy_market(symbol, shares, "BUY_TO_COVER")
                    fill_price = self.get_fill_price(response)
                    self.trade_logger.update_exit(symbol, position, strategy.get_time(), strategy.get_price(), fill_price)

        # --- Exit (Force Close) ---
        elif self.force_close and position is not None:
            self.cancel_order(self.hold_responses[symbol])

            if position == "long":
                response = self.sell_market(symbol, shares, "SELL")
                fill_price = self.get_fill_price(response)
                self.trade_logger.update_exit(symbol, position, strategy.get_time(), strategy.get_price(), fill_price)
            elif position == "short":
                response = self.buy_market(symbol, shares, "BUY_TO_COVER")
                fill_price = self.get_fill_price(response)
                self.trade_logger.update_exit(symbol, position, strategy.get_time(), strategy.get_price(), fill_price)

            self.update_pnl(strategy, position, fill_price, shares)
            self.flatten(symbol, strategy)
        
    def update_pnl(self, strategy, position, fill_price, shares):
        if position == "long":
            pnl = (fill_price - strategy.get_entry_price()) * shares
        elif position == "short":
            pnl = (strategy.get_entry_price() - fill_price) * shares
        self.cash += pnl
        strategy.get_risk_manager().update_risk(pnl)

    def flatten(self, symbol, strategy):
        self.entry_responses[symbol] = None
        self.hold_responses[symbol] = None
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
        fill_price = self.get_fill_price(response)
        print(f"BOT +{quantity} {symbol} @ {fill_price}")
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
        fill_price = self.get_fill_price(response)
        print(f"SELL -{quantity} {symbol} @ {fill_price}")
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
        time.sleep(0.05)
        if position == "long":
            return self.long_bracket(symbol, quantity, stop_loss, take_profit)
        elif position == "short":
            return self.short_bracket(symbol, quantity, stop_loss, take_profit)

    def cancel_order(self, response):
        order_id = response.headers.get('location', '/').split('/')[-1]
        response = self.client.order_cancel(self.hash, order_id)
        return response

    def get_liquidation_value(self):
        details = self.client.account_details(self.hash)
        details_json = details.json()
        liquidationValue = details_json["securitiesAccount"]["currentBalances"]["liquidationValue"]
        return liquidationValue

class TradeLogger:
    def __init__(self, log_file="trade_logs.json"):
        self.open_trades = {}
        self.trade_history = []
        self.log_file = log_file

        try:
            with open("trade_logs.json", "r") as f:
                self.trade_history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.trade_history = []

    def log_entry(self, symbol, position, shares, entry_time, entry_price, fill_price):
        if position not in ("long", "short"):
            raise ValueError("Position must be 'long' or 'short'")
        if symbol in self.open_trades:
            raise ValueError(f"Trade already open for symbol {symbol}")
        
        trade = {
            "symbol": symbol,
            "position": position,
            "shares": shares,
            "entry_time": entry_time.isoformat(),
            "entry_price": entry_price,
            "entry_fill": fill_price,
            "exit_time": None,
            "exit_price": None,
            "exit_fill": None,
            "pnl_real": None,
            "pnl_real_pct": None,
            "pnl_theoretical": None,
            "pnl_theoretical_pct": None
        }

        self.open_trades[symbol] = trade
    
    def update_exit(self, symbol, exit_time, exit_price, fill_price):
        if symbol not in self.open_trades:
            raise ValueError(f"No open trade for symbol {symbol}")

        trade = self.open_trades.pop(symbol)
        trade["exit_time"] = exit_time.isoformat()
        trade["exit_price"] = exit_price
        trade["exit_fill"] = fill_price

        if trade["position"] == "long":
            trade["pnl_real"] = (fill_price - trade["entry_fill"]) * trade["shares"]
            trade["pnl_theoretical"] = (exit_price - trade["entry_price"]) * trade["shares"]
        elif trade["position"] == "short":
            trade["pnl_real"] = (trade["entry_fill"] - fill_price) * trade["shares"]
            trade["pnl_theoretical"] = (trade["entry_price"] - exit_price) * trade["shares"]

        trade["pnl_real"] = round(trade["pnl_real"], 2)
        trade["pnl_real_pct"] = round(trade["pnl_real"] / trade["entry_fill"] * 100, 2)
        trade["pnl_theoretical"] = round(trade["pnl_theoretical"], 2)
        trade["pnl_theoretical_pct"] = round(trade["pnl_theoretical"] / trade["entry_price"] * 100, 2)

        self.trade_history.append(trade)

    def output_logs(self):
        with open(self.log_file, "w") as f:
            json.dump(self.trade_history, f, indent=4)
        print(f"Saved {len(self.trade_history)} trades to {self.log_file}")