import json
from datetime import datetime
import pandas as pd

class TradeManager:
    def __init__(self, log_file="trade_logs.json", live=False):
        self.log_file = log_file

        self.open_trades = {}
        self.trade_history = []
        self.intraday_equity = {}
        
        if live:
            self.load_logs()
    
    def update_data(self, trade_history, intraday_equity):
        self.trade_history = trade_history
        self.intraday_equity = intraday_equity

    def update_intraday_equity(self, ts, equity):
        self.intraday_equity[ts] = equity

    def log_entry(self, name, leg, symbol, direction, position_size, shares, entry_time, entry_price, fill_price, stop_price, target_price, features=None):
        trade = {
            "strategy": name,
            "symbol": symbol,
            "direction": direction,
            "position_size": position_size,
            "shares": shares,
            "entry_time": entry_time.isoformat(),
            "entry_price": entry_price,
            "entry_fill": fill_price,
            "stop_price": stop_price,
            "target_price": target_price,
            "exit_time": None,
            "exit_price": None,
            "exit_fill": None,
            "pnl": None,
            "pnl_pct": None,
            "features": features.copy()
        }
        self.open_trades[leg] = trade
    
    def update_exit(self, leg, exit_time, exit_price, fill_price):
        trade = self.open_trades.pop(leg)
        trade["exit_time"] = exit_time.isoformat()
        trade["exit_price"] = exit_price
        trade["exit_fill"] = fill_price

        trade["pnl"] = round(trade["direction"] * (fill_price - trade["entry_fill"]) * trade["shares"], 2)
        trade["pnl_pct"] = round(trade["pnl"] / (trade["entry_fill"] * trade["shares"]), 5)

        self.trade_history.append(trade)

    def save_logs(self):
        intraday_equity = {ts.isoformat(): val for ts, val in self.intraday_equity.items()}

        with open(self.log_file, "w") as f:
            json.dump({
                "trade_history": self.trade_history,
                "intraday_equity": intraday_equity
            }, f, indent=4)
            print(f"Saved {len(self.trade_history)} trades to {self.log_file}")
    
    def load_logs(self):
        try:
            with open(self.log_file, "r") as f:
                data = json.load(f)

            self.intraday_equity = {
                pd.Timestamp(ts): val
                for ts, val in data.get("intraday_equity", {}).items()
            }

            self.trade_history = data.get("trade_history", [])

        except (FileNotFoundError, json.JSONDecodeError):
            self.trade_history = []
            self.intraday_equity = {}
        