import json
from datetime import datetime
import pandas as pd

class TradeManager:
    def __init__(self, position_manager, log_file="trade_logs.json", live=False):
        self.position_manager = position_manager
        self.log_file = log_file

        self.open_trades = {}
        self.intraday_equity = {}
        self.trade_history = []
        
        if live:
            self.load_logs()
    
    def update_intraday_equity(self, ts, equity):
        self.intraday_equity[ts] = equity

    def log_entry(self, leg, symbol, direction, position_size, shares, entry_time, entry_price, fill_price):
        trade = {
            "symbol": symbol,
            "direction": direction,
            "position_size": position_size,
            "shares": shares,
            "entry_time": entry_time,
            "entry_price": entry_price,
            "entry_fill": fill_price,
            "exit_time": None,
            "exit_price": None,
            "exit_fill": None,
            "pnl": None,
            "pnl_pct": None
        }
        self.open_trades[leg] = trade
    
    def update_exit(self, leg, exit_time, exit_price, fill_price):
        trade = self.open_trades.pop(leg)
        trade["exit_time"] = exit_time
        trade["exit_price"] = exit_price
        trade["exit_fill"] = fill_price

        trade["pnl"] = round(trade["direction"] * (fill_price - trade["entry_fill"]) * trade["shares"], 2)
        trade["pnl_pct"] = round(trade["pnl"] / trade["entry_fill"] * 100, 2)

        self.trade_history.append(trade)

    def save_logs(self):
        history_to_save = []
        for trade in self.trade_history:
            trade_copy = trade.copy()
            for key in ["entry_time", "exit_time"]:
                if isinstance(trade_copy.get(key), datetime):
                    trade_copy[key] = trade_copy[key].isoformat()
            history_to_save.append(trade_copy)

        with open(self.log_file, "w") as f:
            json.dump({
                "trade_history": history_to_save,
                "intraday_equity": self.intraday_equity
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

            self.trade_history = []
            for trade in data.get("trade_history", []):
                trade_parsed = trade.copy()
                for key in ("entry_time", "exit_time"):
                    if key in trade_parsed:
                        trade_parsed[key] = pd.Timestamp(trade_parsed[key])
                self.trade_history.append(trade_parsed)

        except (FileNotFoundError, json.JSONDecodeError):
            self.trade_history = []
            self.intraday_equity = {}
        