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
                 start_time=(14, 00), end_time=(20, 00), quote_delta_ms=500, max_latency_ms=500, 
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
        self.sync_check = False
        self.latency_check = False
        self.latency = 0  # network latency in milliseconds

        self.features = None

        self.data_history = {}
        self.saved = False

        self.position_manager = PositionManager()
        self.risk_manager = RiskManager(pnl_target=pnl_target, pnl_loss=pnl_loss, trade_max=trade_max)

    def generate_signal(self, row, symbol):
        raise NotImplementedError
    
    def enter_trade(self, signal=None):
        raise NotImplementedError
    
    def exit_trade(self, signal=None):
        return self.exit()
    
    def compute_indicators(self):
        raise NotImplementedError
    
    def reset_history(self, reset_time=(13, 31)):
        raise NotImplementedError

    def config(self):
        raise NotImplementedError
    
    def param_grid(self):
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
            self.latency_check = fresher_quote["latency"] < self.max_latency_ms
            self.sync_check = abs(self.s1["ts"] - self.s2["ts"]) <= self.quote_delta_ms

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
        if self.position_manager.direction():
            self.dca_step = 0
            return EXIT
        return HOLD
    
    def compute_share_split(self, min_pct=0.85):
        cash = self.risk_manager.curr_cash

        # FXIED CASH
        if self.pair == "SPY-QQQ":
            cash = 10000
        if self.pair == "IVV-IWM":
            cash = 10000
        # if self.pair == "GLD-SLV":
        #     cash = 20000
        if self.pair == "IAU-SIVR":
            cash = 3000
        if self.pair == "USO-BNO":
            cash = 3000
        if self.pair == "VT-VXUS":
            cash = 3000

        price1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        price2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        max_s1 = int(cash / 2 // price1)
        max_s2 = int(cash / 2 // price2)
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

        return shares1, shares2
    
    def compute_dca_plan(self, shares1, shares2):
        price1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        price2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        max_steps = max(1, int(1 / self.position_size))
        steps = min(max_steps, shares1, shares2)

        plan = [[1, 1] for _ in range(steps)]

        rem1 = shares1 - steps
        rem2 = shares2 - steps

        def score(p):
            ca = cb = 0
            total = 0
            for a, b in p:
                ca += a * price1
                cb += b * price2
                total += abs(ca - cb)
            return total

        def full_pass(rem, side):
            base = rem // steps
            rem = rem % steps

            for i in range(steps):
                plan[i][side] += base
            return rem

        rem1 = full_pass(rem1, 0)
        rem2 = full_pass(rem2, 1)

        for rem, side in [(rem1, 0), (rem2, 1)]:
            for _ in range(rem):
                best_i = 0
                best_score = None

                for i in range(steps):
                    plan[i][side] += 1
                    s = score(plan)
                    plan[i][side] -= 1

                    if best_score is None or s < best_score:
                        best_score = s
                        best_i = i

                plan[best_i][side] += 1

        plan = [tuple(p) for p in plan]

        return plan
       
    def compute_position_value(self):
        direction = self.position_manager.direction()
        shares1, shares2 = self.position_manager.total_shares()

        entry1, entry2 = self.position_manager.average_entry()

        exit1 = self.s1["bid"] if direction > 0 else self.s1["ask"]
        exit2 = self.s2["bid"] if direction > 0 else self.s2["ask"]

        pnl = (direction * (exit1 - entry1) * shares1) - (direction * (exit2 - entry2) * shares2)
        position_value = shares1 * entry1 + shares2 * entry2

        return pnl / position_value
    
    def save_data(self, ts, data, save_time=(19, 30)):
        if not self.saved:
            self.data_history[ts] = data
            end_time = (save_time[0] * 3600 + save_time[1] * 60) * 1000
            if ts % (24 * 3600 * 1000) > end_time:
                with open(f"{self.pair}_spread.json", "w") as f:
                    json.dump(self.data_history, f, indent=2)
                self.saved = True

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
    
    def average_entry(self):
        total1 = total2 = 0
        weighted_sum1 = weighted_sum2 = 0
        for leg1, leg2 in self.pairs:
            weighted_sum1 += leg1.entry_price * leg1.position_size
            total1 += leg1.position_size
            weighted_sum2 += leg2.entry_price * leg2.position_size
            total2 += leg2.position_size
        return weighted_sum1 / total1 if total1 > 0 else 0, weighted_sum2 / total2 if total2 > 0 else 0
    
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