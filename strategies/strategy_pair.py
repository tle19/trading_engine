from .risk import RiskManager

LONG = 1
SHORT = -1
EXIT = 0
HOLD = None

class PairStrategy:
    def __init__(self, pair, time_start, time_end, take_profit=0.001, position_size=1.0,
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=200):
        self.pair = pair
        self.symbol1, self.symbol2 = pair.split("-")
        self.take_profit = take_profit
        self.position_size = position_size
        self.time_start = time_start[0] * 60 + time_start[1]
        self.time_end = time_end[0] * 60 + time_end[1]

        self.data = {
            self.symbol1: {
                "ts": None,
                "bid": None,
                "ask": None,
                "last": None,
                "bid_size": None,
                "ask_size": None,
                "entry_price": None,
                "exit_price": None,
                "direction": 0,
                "shares": 0,
                "position_size": 1.0,
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
                "exit_price": None,
                "direction": 0,
                "shares": 0,
                "position_size": 1.0,
                "activated": False
            }
        }
        
        self.activated = False

        self.risk_manager = RiskManager(pnl_target=pnl_target, pnl_loss=pnl_loss, trade_max=trade_max)
        self.cash = self.risk_manager.curr_cash / 2

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
            if self.data[self.symbol1]["activated"] and self.data[self.symbol2]["activated"]:
                self.activated = True

    def trade_window(self):
        ts = self.data[self.symbol1]["ts"] or self.data[self.symbol2]["ts"]
        return self.time_start <= (ts // 1000 // 60) <= self.time_end
    
    def buy_pair(self):
        s1, s2 = self.data[self.symbol1], self.data[self.symbol2]
        if s1["direction"] == 0:
            shares1 = int(self.cash / s1["last"])
            shares2 = int(self.cash / s2["last"])
            s1["direction"], s1["shares"] = 1, shares1
            s2["direction"], s2["shares"] = -1, shares2
            return LONG
        return HOLD
        
    def sell_pair(self):
        s1, s2 = self.data[self.symbol1], self.data[self.symbol2]
        if s1["direction"] == 0:
            shares1 = int(self.cash / s1["last"])
            shares2 = int(self.cash / s2["last"])
            s1["direction"], s1["shares"] = -1, shares1
            s2["direction"], s2["shares"] = 1, shares2
            return SHORT
        return HOLD
          
    def exit(self):
        if self.data[self.symbol1]["direction"]:
            return EXIT
        return HOLD
    
    def compute_ema(self, prev_ema, new_value, window=10):
        if prev_ema is None:
            return new_value
        alpha = 2.0 / (window + 1.0)
        return alpha * new_value + (1.0 - alpha) * prev_ema