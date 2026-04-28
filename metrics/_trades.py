import os
import json

class TradeManager:
    def __init__(self, log_file="trade_logs.json", live=False):
        file_path = os.path.join("trade_logs", log_file)
        self.log_file = file_path

        self.open_trades = {}
        self.trade_history = []
        self.intraday_equity = {}
        
        if live:
            self.load_logs()
    
    def update_data(self, trade_history, intraday_equity):
        self.trade_history = trade_history
        self.intraday_equity = intraday_equity

    def update_intraday_equity(self, ts, equity):
        self.intraday_equity[ts.isoformat()] = equity

    def log_entry(self, name, leg, symbol, direction, position_size, shares, entry_time, entry_price, fill_price, stop_price, target_price, features=None):
        trade = {
            "strategy": name,
            "symbol": symbol,
            "direction": direction,
            "position_size": position_size,
            "shares": shares,
            "entry_time": entry_time,
            "entry_price": entry_price,
            "entry_fill": entry_price if fill_price is None else round(fill_price, 2),
            "stop_price": stop_price,
            "target_price": target_price,
            "exit_time": None,
            "exit_price": None,
            "exit_fill": None,
            "pnl": None,
            "pnl_pct": None,
            "features": features.copy() if features else {}
        }
        self.open_trades[leg] = trade
    
    def update_exit(self, leg, exit_time, exit_price, fill_price):
        trade = self.open_trades.pop(leg)
        trade["entry_time"] = trade["entry_time"].isoformat()
        trade["exit_time"] = exit_time.isoformat()
        trade["exit_price"] = exit_price
        trade["exit_fill"] = exit_price if fill_price is None else round(fill_price, 2)

        trade["pnl"] = round((trade["direction"] * (trade["exit_fill"] - trade["entry_fill"]) * trade["shares"]), 2)
        trade["pnl_pct"] = round(trade["pnl"] / (trade["entry_fill"] * trade["shares"]), 10)

        self.trade_history.append(trade)

    def save_logs(self):
        with open(self.log_file, "w") as f:
            json.dump({
                "trade_history": self.trade_history,
                "intraday_equity": self.intraday_equity
            }, f, indent=4)
            print(f"Saved {len(self.trade_history)} trades to {self.log_file}")
    
    def load_logs(self):
        try:
            with open(self.log_file, "r") as f:
                data = json.load(f)

            self.trade_history = data.get("trade_history", [])
            self.intraday_equity = data.get("intraday_equity", [])

        except (FileNotFoundError, json.JSONDecodeError):
            self.trade_history = []
            self.intraday_equity = {}
        