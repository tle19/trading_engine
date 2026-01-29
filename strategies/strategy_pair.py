from .risk import RiskManager

LONG = 1
SHORT = -1
EXIT = 0
HOLD = None

class StrategyPair:
    def __init__(self, pair, start_time, end_time, take_profit=0.001,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=200):
        self.pair = pair
        self.symbol1, self.symbol2 = pair.split("-")
        self.start_time = start_time[0] * 60 + start_time[1]
        self.end_time = end_time[0] * 60 + end_time[1]
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
                "activated": False
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
                "activated": False
            }
        }
        
        self.s1 = self.data[self.symbol1]
        self.s2 = self.data[self.symbol2]
        self.activated = False

        self.risk_manager = RiskManager(pnl_target=pnl_target, pnl_loss=pnl_loss, trade_max=trade_max)

    def generate_signal(self):
        raise NotImplementedError
    
    def enter_trade(self):
        raise NotImplementedError
    
    def exit_trade(self):
        return self.exit()
    
    def compute_indicators(self):
        raise NotImplementedError
    
    def update(self, symbol, row=None): 
        s = self.data[symbol]
        
        if row.timestamp is not None: s["ts"] = row.timestamp
        if row.bid is not None: s["bid"] = row.bid
        if row.ask is not None: s["ask"] = row.ask
        if row.last is not None: s["last"] = row.last
        if row.bid_size is not None: s["bid_size"] = row.bid_size
        if row.ask_size is not None: s["ask_size"] = row.ask_size
                
        if not self.activated:
            for attr in ("bid", "ask", "last", "bid_size", "ask_size"):
                if s[attr] is None:
                    return
            s["activated"] = True
            if self.s1["activated"] and self.s2["activated"]:
                self.compute_share_split()
                self.activated = True

    def trade_window(self):
        ts = self.s1["ts"] or self.s2["ts"]
        return self.start_time <= (ts // 1000 // 60) <= self.end_time
    
    def buy_pair(self):
        if self.s1["direction"] == 0:
            self.s1["direction"] = 1
            self.s2["direction"] = -1
            return LONG
        return HOLD
        
    def sell_pair(self):
        if self.s1["direction"] == 0:
            self.s1["direction"] = -1
            self.s2["direction"] = 1
            return SHORT
        return HOLD
          
    def exit(self):
        if self.s1["direction"]:
            return EXIT
        return HOLD
    
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