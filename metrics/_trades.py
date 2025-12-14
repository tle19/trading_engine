import json
import pandas as pd

class TradeManager:
    def __init__(self, position_manager, log_file="trade_history.json", live=False):
        self.position_manager = position_manager
        self.log_file = log_file

        self.open_trades = {}
        self.intraday_equity = {}
        self.trade_history = []

        try:
            if live:
                with open(self.log_file, "r") as f:
                    self.trade_history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.intraday_equity = {}
            self.trade_history = []

    def update_intraday_equity(self, ts, equity):
        self.intraday_equity[ts] = equity

    def log_entry(self, symbol, direction, position_size, shares, entry_time, entry_price, fill_price):
        trade = {
            "symbol": symbol,
            "direction": direction,
            "position_size": position_size,
            "shares": shares,
            "entry_time": entry_time.isoformat(),
            "entry_price": entry_price,
            "entry_fill": fill_price,
            "exit_time": None,
            "exit_price": None,
            "exit_fill": None,
            "pnl": None,
            "pnl_pct": None
        }
        # re do to allow for multiple open trades on same ticker
        self.open_trades[symbol] = trade # self.position_manager.legs[-1]
    
    def update_exit(self, symbol, direction, shares, exit_time, exit_price, fill_price):

        if symbol not in self.open_trades:
            raise ValueError(f"No open trade for symbol {symbol}")

        trade = self.open_trades.pop(symbol) # change to remove for multiple open trades
        trade["exit_time"] = exit_time.isoformat()
        trade["exit_price"] = exit_price
        trade["exit_fill"] = fill_price

        if direction == "long":
            trade["pnl"] = (fill_price - trade["entry_fill"]) * shares
        elif direction == "short":
            trade["pnl"] = (trade["entry_fill"] - fill_price) * shares

        trade["pnl"] = round(trade["pnl"], 2)
        trade["pnl_pct"] = round(trade["pnl"] / trade["entry_fill"] * 100, 2)

        self.trade_history.append(trade)

    def output_logs(self):
        with open(self.log_file, "w") as f:
            json.dump(self.trade_history, f, indent=4)
        print(f"Saved {len(self.trade_history)} trades to {self.log_file}")