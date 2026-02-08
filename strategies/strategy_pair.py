from .risk import RiskManager
import datetime
LONG = 1
SHORT = -1
EXIT = 0
HOLD = None

class StrategyPair:
    def __init__(self, pair, start_time=(14, 30), end_time=(21, 00), 
                 take_profit=0.0001, pnl_target=0.01, pnl_loss=-0.01, trade_max=100):
        self.pair = pair
        if "-" not in pair:
            raise ValueError(f"Invalid pair format: '{pair}'. Expected format 'SYMBOL1-SYMBOL2'.")
        self.symbol1, self.symbol2 = pair.split("-")
        self.start_time = (start_time[0] * 3600 + start_time[1] * 60) * 1000
        self.end_time = (end_time[0] * 3600 + end_time[1] * 60) * 1000
        # Summer (EDT) start_time=(13, 30), end_time=(20, 00)
        # Winter (EST) start_time=(14, 30), end_time=(21, 00)
        self.take_profit = take_profit

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
                "updated": False,
                "activated": False,
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
                "updated": False,
                "activated": False,
                "latency": 0
            }
        }
        
        self.s1 = self.data[self.symbol1]
        self.s2 = self.data[self.symbol2]
        self.activated = False
        self.received = False
        self.last_processed = 0
        self.ticks = 0
        
        self.latency = 0  # network latency in milliseconds

        self.risk_manager = RiskManager(pnl_target=pnl_target, pnl_loss=pnl_loss, trade_max=trade_max)

    def generate_signal(self, row, symbol=None):
        raise NotImplementedError
    
    def enter_trade(self):
        raise NotImplementedError
    
    def exit_trade(self):
        return self.exit()
    
    def compute_indicators(self):
        raise NotImplementedError
    
    def update(self, symbol, row=None): 
        s = self.data[symbol]
        if s["direction"]:
            if self.s1["entry_price"] is None:
                self.s1["entry_price"] = self.s1["ask"] if self.s1["direction"] > 0 else self.s1["bid"]
            if self.s2["entry_price"] is None:  
                self.s2["entry_price"] = self.s2["ask"] if self.s2["direction"] > 0 else self.s1["bid"]

        if row.timestamp is not None: s["ts"] = row.timestamp
        if row.bid is not None: s["bid"] = row.bid
        if row.ask is not None: s["ask"] = row.ask
        if row.last is not None: s["last"] = row.last
        if row.bid_size is not None: s["bid_size"] = row.bid_size
        if row.ask_size is not None: s["ask_size"] = row.ask_size
        s["latency"] = self.latency
                
        if not self.activated:
            for attr in ("bid", "ask", "last", "bid_size", "ask_size"):
                if s[attr] is None:
                    return
            s["activated"] = True
            if self.s1["activated"] and self.s2["activated"]:
                self.activated = True
        else:
            self.received = False
            if self.s1["ts"] > self.last_processed and self.s2["ts"] > self.last_processed:
                self.last_processed = max(self.s1["ts"], self.s2["ts"])
                self.received = True 

        self.ticks += 1

    def trade_window(self):
        ts = self.s1["ts"] or self.s2["ts"]
        return self.start_time <= (ts % (24 * 3600 * 1000)) <= self.end_time
    
    def buy_pair(self):
        if self.s1["direction"] == 0:
            # self.compute_share_split()
            self.s1["shares"] = 10 # testing
            self.s2["shares"] = 10 # testing
            self.s1["direction"] = 1
            self.s2["direction"] = -1
            self.ticks = 0
            return LONG
        return HOLD
        
    def sell_pair(self):
        if self.s1["direction"] == 0:
            # self.compute_share_split()
            self.s1["shares"] = 10 # testing
            self.s2["shares"] = 10 # testing
            self.s1["direction"] = -1
            self.s2["direction"] = 1
            self.ticks = 0
            return SHORT
        return HOLD
          
    def exit(self):
        if self.s1["direction"]:
            self.ticks = 0
            return EXIT
        return HOLD
    
    def flatten(self):
        self.s1["direction"] = 0 
        self.s2["direction"] = 0
        self.s1["entry_price"] = None
        self.s2["entry_price"] = None
    
    def compute_share_split(self, buffer=0.01):
        cash = self.risk_manager.curr_cash / 2
        self.s1["shares"] = max(1, int(cash * (1 - buffer) / self.s1["last"]))
        self.s2["shares"] = max(1, int(cash * (1 - buffer) / self.s2["last"]))
        # change for partial shares/small arb
        
    def compute_ema(self, prev_ema, new_value, window=10):
        if prev_ema is None:
            return new_value
        alpha = 2.0 / (window + 1.0)
        return alpha * new_value + (1.0 - alpha) * prev_ema