import os
import json

from .risk import RiskManager

LONG = 1
SHORT = -1
EXIT = 0
HOLD = None
# Summer (EDT) start_time=(13, 30), end_time=(20, 00)
# Winter (EST) start_time=(14, 30), end_time=(21, 00)

class StrategyPair:
    def __init__(self, pair, start_time=(14, 30), end_time=(21, 00), latency_ms=500,
                 stop_loss=0.0001, take_profit=0.0001, pnl_target=0.01, pnl_loss=-0.01, trade_max=100):
        self.pair = pair
        if "-" not in pair:
            raise ValueError(f"Invalid pair format: '{pair}'. Expected format 'SYMBOL1-SYMBOL2'.")
        self.symbol1, self.symbol2 = pair.split("-")
        self.start_time = (start_time[0] * 3600 + start_time[1] * 60) * 1000
        self.end_time = (end_time[0] * 3600 + end_time[1] * 60) * 1000
        self.latency_ms = latency_ms
        self.take_profit = take_profit
        self.stop_loss = stop_loss

        self.data = {
            self.symbol1: {
                "ts": None,
                "bid": None,
                "ask": None,
                "last": None,
                "bid_size": None,
                "ask_size": None,
                "entry_price": None,
                "direction": 0,
                "shares": 0,
                "latency": 0
            },
            self.symbol2: {
                "ts": None,
                "bid": None,
                "ask": None,
                "last": None,
                "bid_size": None,
                "ask_size": None,
                "entry_price": None,
                "direction": 0,
                "shares": 0,
                "latency": 0
            }
        }
        
        self.s1 = self.data[self.symbol1]
        self.s2 = self.data[self.symbol2]

        self.activated = False
        self.received = False
        self.ticks = 0
        
        self.latency = 0  # network latency in milliseconds

        self.saved = False
        self.history = []

        self.features = None

        self.risk_manager = RiskManager(pnl_target=pnl_target, pnl_loss=pnl_loss, trade_max=trade_max)

    def generate_signal(self, row, symbol):
        raise NotImplementedError
    
    def enter_trade(self, ms=500):
        raise NotImplementedError
    
    def exit_trade(self, ms=500):
        return self.exit()
    
    def compute_indicators(self):
        raise NotImplementedError
    
    def update(self, row, symbol): 
        s = self.data[symbol]

        if row.timestamp is not None: s["ts"] = row.timestamp
        if row.bid is not None: s["bid"] = row.bid
        if row.ask is not None: s["ask"] = row.ask
        if row.last is not None: s["last"] = row.last
        if row.bid_size is not None: s["bid_size"] = row.bid_size
        if row.ask_size is not None: s["ask_size"] = row.ask_size
        s["latency"] = self.latency

        if not self.activated:
            for attr in ("bid", "ask", "last", "bid_size", "ask_size"):
                if self.s1[attr] is None or self.s2[attr] is None:
                    return
            self.activated = True
        else:
            if abs(self.s1["ts"] - self.s2["ts"]) <= 1000:
                self.received = True
            else:
                self.received = False

        self.ticks += 1

    def trade_window(self):
        ts = self.s1["ts"] or self.s2["ts"]
        return self.start_time <= (ts % (24 * 3600 * 1000)) <= self.end_time
    
    def buy_pair(self):
        if self.s1["direction"] == 0:
            self.s1["entry_price"] = self.s1["ask"]
            self.s2["entry_price"] = self.s1["bid"]
            self.s1["direction"] = 1
            self.s2["direction"] = -1
            self.compute_share_split()
            self.ticks = 0
            return LONG
        return HOLD
        
    def sell_pair(self):
        if self.s1["direction"] == 0:
            self.s1["entry_price"] = self.s1["bid"]
            self.s2["entry_price"] = self.s1["ask"]
            self.s1["direction"] = -1
            self.s2["direction"] = 1
            self.compute_share_split()
            self.ticks = 0
            return SHORT
        return HOLD
          
    def exit(self):
        if self.s1["direction"]:
            self.ticks = 0
            return EXIT
        return HOLD
    
    def flatten(self):
        self.s1["entry_price"] = None
        self.s2["entry_price"] = None
        self.s1["direction"] = 0 
        self.s2["direction"] = 0
        self.s1["shares"] = 0
        self.s2["shares"] = 0
    
    def compute_share_split(self, min_pct=0.85):
        cash = self.risk_manager.curr_cash / 2
        price1 = self.s1["last"]
        price2 = self.s2["last"]

        max_s1 = int(cash // self.s1["last"])
        max_s2 = int(cash // self.s2["last"])
        min_s1 = int(max_s1 * min_pct)
        min_s2 = int(max_s2 * min_pct)

        best_diff = float('inf')
        shares1, shares2 = max_s1, max_s2

        for s1 in range(min_s1, max_s1 + 1):
            cash1 = s1 * price1
            for s2 in range(min_s2, max_s2 + 1):
                cash2 = s2 * price2
                diff = abs(cash1 - cash2)
                if diff < best_diff:
                    best_diff = diff
                    shares1, shares2 = s1, s2

        self.s1["shares"] = max(1, shares1)
        self.s2["shares"] = max(1, shares2)
        if self.pair == "GOOG-GOOGL":
            self.s1["shares"] = 5
            self.s2["shares"] = 5
        if self.pair == "SPY-QQQ":
            self.s1["shares"] = 7
            self.s2["shares"] = 8

    def save_data(self, symbol):
        if self.activated and not self.saved:
            self.history.append({
                "symbol": symbol,
                "timestamp": self.data[symbol]["ts"],
                "bid": self.data[symbol]["bid"],
                "ask": self.data[symbol]["ask"],
                "last": self.data[symbol]["last"],
                "bid_size": self.data[symbol]["bid_size"],
                "ask_size": self.data[symbol]["ask_size"],
            })
            if self.s1["ts"] % (24 * 3600 * 1000) > self.end_time:
                file_path = os.path.join("data", f"{self.pair}_quote.json")
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        existing_history = json.load(f)
                else:
                    existing_history = []
                existing_history.extend(self.history)
                with open(file_path, "w") as f:
                    json.dump(existing_history, f, indent=2)
                self.saved = True
        
    def compute_ema(self, prev_ema, new_value, window=10):
        if prev_ema is None:
            return new_value
        alpha = 2.0 / (window + 1.0)
        return alpha * new_value + (1.0 - alpha) * prev_ema