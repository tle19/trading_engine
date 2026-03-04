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
    def __init__(self, pair, 
                 start_time=(14, 30), end_time=(21, 00), quote_delta_ms=1000, max_latency_ms=500, 
                 position_size=1.0, stop_loss=0.0001, take_profit=0.0001, 
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=100):
        if "-" not in pair:
            raise ValueError(f"Invalid pair format: '{pair}'. Expected format 'SYMBOL1-SYMBOL2'.")
        self.pair = pair
        self.symbol1, self.symbol2 = pair.split("-")
        self.start_time = (start_time[0] * 3600 + start_time[1] * 60) * 1000
        self.end_time = (end_time[0] * 3600 + end_time[1] * 60) * 1000
        self.quote_delta_ms = quote_delta_ms
        self.max_latency_ms = max_latency_ms
        self.position_size = position_size
        self.stop_loss = stop_loss
        self.take_profit = take_profit

        self.data = {
            self.symbol1: {
                "ts": None,
                "bid": None,
                "ask": None,
                "last": None,
                "bid_size": None,
                "ask_size": None,
                "latency": 0
            },
            self.symbol2: {
                "ts": None,
                "bid": None,
                "ask": None,
                "last": None,
                "bid_size": None,
                "ask_size": None,
                "latency": 0
            }
        }
        
        self.s1 = self.data[self.symbol1]
        self.s2 = self.data[self.symbol2]

        self.activated = False
        self.dca_plan = []
        self.dca_step = 0

        self.latency_check = False
        self.latency = 0  # network latency in milliseconds
        self.ticks = 0

        self.features = None

        self.position_manager = PositionManager()
        self.risk_manager = RiskManager(pnl_target=pnl_target, pnl_loss=pnl_loss, trade_max=trade_max)

    def generate_signal(self, row, symbol):
        raise NotImplementedError
    
    def enter_trade(self):
        raise NotImplementedError
    
    def exit_trade(self):
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
            for attr in ("ts", "bid", "ask", "last", "bid_size", "ask_size"):
                if self.s1[attr] is None or self.s2[attr] is None:
                    return
            self.activated = True
            shares1, shares2 = self.compute_share_split()
            self.dca_plan = self.compute_dca_plan(shares1, shares2)
        else:
            fresher_quote = self.s1 if self.s1["ts"] >= self.s2["ts"] else self.s2
            self.latency_check = abs(self.s1["ts"] - self.s2["ts"]) <= self.quote_delta_ms and fresher_quote["latency"] < self.max_latency_ms

        self.ticks += 1
        
    def trade_window(self):
        ts = self.s1["ts"] or self.s2["ts"]
        return self.start_time <= (ts % (24 * 3600 * 1000)) <= self.end_time
    
    def buy_pair(self):
        direction = self.position_manager.direction()
        if direction in (1, 0) and self.dca_step < len(self.dca_plan):
            shares1, shares2 = self.dca_plan[self.dca_step]
            pos_leg1 = PositionLeg(
                direction=1,
                timestamp=self.s1["ts"],
                entry_price=self.s1["ask"],
                position_size=self.position_size,
                shares=shares1
            )
            pos_leg2 = PositionLeg(
                direction=-1,
                timestamp=self.s2["ts"],
                entry_price=self.s2["bid"],
                position_size=self.position_size,
                shares=shares2
            )
            if self.position_manager.add_pair(pos_leg1, pos_leg2):
                self.dca_step += 1
                return LONG
            return HOLD
        elif direction == -1:
            return HOLD
        
    def sell_pair(self):
        direction = self.position_manager.direction()
        if direction in (-1, 0) and self.dca_step < len(self.dca_plan):
            shares1, shares2 = self.dca_plan[self.dca_step]
            pos_leg1 = PositionLeg(
                direction=-1,
                timestamp=self.s1["ts"],
                entry_price=self.s1["bid"],
                position_size=self.position_size,
                shares=shares1
            )
            pos_leg2 = PositionLeg(
                direction=1,
                timestamp=self.s2["ts"],
                entry_price=self.s2["ask"],
                position_size=self.position_size,
                shares=shares2
            )
            if self.position_manager.add_pair(pos_leg1, pos_leg2):
                self.dca_step += 1
                return SHORT
            return HOLD
        elif direction == 1:
            return HOLD
          
    def exit(self):
        direction = self.position_manager.direction()
        if direction:
            self.dca_step = 0
            return EXIT
        return HOLD
    
    def compute_share_split(self, min_pct=0.85):
        cash = self.risk_manager.curr_cash / 2
        price1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        price2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        max_s1 = int(cash // price1)
        max_s2 = int(cash // price2)
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

        # TEST MIN SHARES
        if self.pair == "SPY-QQQ":
            shares1 = 8
            shares2 = 9
        if self.pair == "GLD-SLV":
            shares1 = 10
            shares2 = 63
        if self.pair == "IBIT-ETHA":
            shares1 = 10
            shares2 = 26
        if self.pair == "XLE-VDE":
            shares1 = 17
            shares2 = 6
        if self.pair == "GOOG-GOOGL":
            shares1 = 1
            shares2 = 1

        return shares1, shares2
    
    def compute_dca_plan(self, shares1, shares2):
        plan = []

        max_steps = max(1, int(1 / self.position_size))
        num_passes = min(max_steps, min(shares1, shares2))

        for _ in range(num_passes):
            plan.append([1, 1])

        rem1 = shares1 - num_passes
        rem2 = shares2 - num_passes

        for i in range(rem1):
            plan[i % num_passes][0] += 1
        for i in range(rem2):
            plan[i % num_passes][1] += 1

        plan.reverse()
        plan = [tuple(p) for p in plan]

        return plan
    
    def compute_ema(self, prev_ema, new_value, window=10):
        if prev_ema is None:
            return new_value
        alpha = 2.0 / (window + 1.0)
        return alpha * new_value + (1.0 - alpha) * prev_ema

class PositionLeg:
    __slots__ = ("entry_time", "direction", "_entry_price", "position_size", "shares")
    
    def __init__(self, timestamp, direction, entry_price, position_size, shares):
        self.entry_time = timestamp
        self.direction = direction
        self._entry_price = entry_price
        self.position_size = position_size
        self.shares = shares

        if direction not in (1, -1):
            raise ValueError(f"Invalid direction: {direction}")
    
    @property
    def entry_price(self):
        return self._entry_price

    @entry_price.setter
    def entry_price(self, value):
        if value is None:
            return
        if value <= 0:
            raise ValueError("entry_price must be positive")
        self._entry_price = float(value)
            
class PositionManager:
    def __init__(self):
        self.pairs = [] # list of PositionLeg

    def add_pair(self, leg1: PositionLeg, leg2: PositionLeg):
        if 0.0 < self.total_size() + leg1.position_size <= 1.0:
            self.pairs.append((leg1, leg2))
            return True

    def remove_pair(self, leg1, leg2):
        self.pairs.remove((leg1, leg2))

    def total_size(self):
        return sum(pair[0].position_size for pair in self.pairs)
    
    def direction(self):
        return self.pairs[0][0].direction if self.pairs else 0
    
    def average_entry(self, symbol):
        total = 0.0
        weighted_sum = 0.0
        for leg1, leg2 in self.pairs:
            if leg1.symbol == symbol:
                weighted_sum += leg1.entry_price * leg1.position_size
                total += leg1.position_size
            elif leg2.symbol == symbol:
                weighted_sum += leg2.entry_price * leg2.position_size
                total += leg2.position_size
        return weighted_sum / total if total > 0 else 0
    
    def total_shares(self):
        shares1 = shares2 = 0
        for leg1, leg2 in self.pairs:
            shares1 += leg1.shares
            shares2 += leg2.shares
        return shares1, shares2

    def reset(self):
        self.pairs = []
    
    def in_trade(self):
        return bool(self.pairs)