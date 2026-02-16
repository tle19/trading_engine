from .risk import RiskManager

LONG = 1
SHORT = -1
EXIT = 0
HOLD = None
# Summer (EDT) start_time=(13, 30), end_time=(20, 00)
# Winter (EST) start_time=(14, 30), end_time=(21, 00)

class StrategyPair:
    def __init__(self, symbol, start_time=(14, 30), end_time=(21, 00), 
                 stop_loss=0.01, take_profit=0.01, pnl_target=0.01, pnl_loss=-0.01, trade_max=100):
        self.symbol = symbol
        self.start_time = (start_time[0] * 3600 + start_time[1] * 60) * 1000
        self.end_time = (end_time[0] * 3600 + end_time[1] * 60) * 1000
        self.take_profit = take_profit
        self.stop_loss = stop_loss

        self.ts = None
        self.bid_side = None
        self.ask_side = None
        self.entry_price = None
        self.direction = 0
        self.shares = 0

        self.activated = False
        self.ticks = 0
        
        self.latency = 0  # network latency in milliseconds

        self.risk_manager = RiskManager(pnl_target=pnl_target, pnl_loss=pnl_loss, trade_max=trade_max)

    def generate_signal(self, row, symbol):
        raise NotImplementedError
    
    def enter_trade(self, ms=500):
        raise NotImplementedError
    
    def exit_trade(self, ms=500):
        return self.exit()
    
    def compute_indicators(self):
        raise NotImplementedError
    
    def update(self, row=None): 
        if row.timestamp is not None: self.ts = row.timestamp
        if row.bid is not None: self.bid_side = row.bid
        if row.ask is not None: self.ask_side = row.ask

        if not self.activated:
            if self.bid_side is None or self.ask_side is None:
                return
            self.activated = True

        self.ticks += 1

    def trade_window(self):
        return self.start_time <= (self.ts % (24 * 3600 * 1000)) <= self.end_time
    
    def buy(self):
        if self.direction == 0:
            self.entry_price = self.ask_side["ask"]
            self.direction = 1
            self.shares = 0
            self.ticks = 0
            return LONG
        return HOLD
        
    def sell(self):
        if self.direction == 0:
            self.entry_price = self.bid_side["bid"]
            self.direction = -1
            self.shares = 0
            self.ticks = 0
            return SHORT
        return HOLD
          
    def exit(self):
        if self.direction:
            self.ticks = 0
            return EXIT
        return HOLD
    
    def flatten(self):
        self.entry_price = None
        self.direction = 0
        self.shares = 0

    def compute_ema(self, prev_ema, new_value, window=10):
        if prev_ema is None:
            return new_value
        alpha = 2.0 / (window + 1.0)
        return alpha * new_value + (1.0 - alpha) * prev_ema