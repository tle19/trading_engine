import json
import numpy as np
from datetime import timedelta

from .risk import RiskManager
from utils import open_data

LONG = 1
SHORT = -1
EXIT = 0
HOLD = None
# Summer (EDT) start_time=(13, 30), end_time=(20, 00)
# Winter (EST) start_time=(14, 30), end_time=(21, 00)

class StrategyPair:
    def __init__(self, pair, 
                 start_time=(10, 00), end_time=(15, 00), quote_delta_ms=500, max_latency_ms=500, 
                 position_size=1.0, stop_loss=0.0001, take_profit=0.0001, 
                 pnl_target=0.01, pnl_loss=-0.01, trade_max=100):
        if "-" not in pair:
            raise ValueError(f"Invalid pair format: '{pair}'. Expected format 'SYMBOL1-SYMBOL2'.")
        self.pair = pair
        self.symbol1, self.symbol2 = pair.split("-")
        self.start_time = start_time
        self.end_time = end_time
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
        self.sync_check = False
        self.latency_check = False
        self.force_close = False
        self.features = None

        self.hedge_ratio = 1.0
        self.curr_steps = 0
        self.max_steps = 1
        self.latency = 0  # network latency in milliseconds

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
            self.compute_max_steps()
            # self.hedge_ratio_distribution() # FIX DIV BY 0 ERROR
        else:
            fresher_quote = self.s1 if self.s1["ts"] > self.s2["ts"] else self.s2
            self.latency_check = fresher_quote["latency"] < self.max_latency_ms
            self.sync_check = abs(self.s1["ts"] - self.s2["ts"]) <= timedelta(milliseconds=self.quote_delta_ms)

            if self.trade_window((15, 45), (15, 45)):
                self.force_close = True
            else:
                self.force_close = False

    def trade_window(self, start=(9, 30), end=(16, 00)):
        ts = self.s1['ts'] or self.s2['ts']
        return start <= (ts.hour, ts.minute) <= end
    
    def buy_pair(self):
        direction = self.position_manager.direction()
        if direction in (1, 0) and self.curr_steps < self.max_steps:
            shares1, shares2 = self.compute_share_split()
            if shares1 == 0 or shares2 == 0:
                return HOLD
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
                self.curr_steps += 1
                return LONG
            return HOLD
        elif direction == -1:
            return HOLD
        
    def sell_pair(self):
        direction = self.position_manager.direction()
        if direction in (-1, 0) and self.curr_steps < self.max_steps:
            shares1, shares2 = self.compute_share_split()
            if shares1 == 0 or shares2 == 0:
                return HOLD
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
                self.curr_steps += 1
                return SHORT
            return HOLD
        elif direction == 1:
            return HOLD
          
    def exit(self):
        if self.position_manager.direction():
            self.curr_steps = 0
            return EXIT
        return HOLD
    
    def compute_max_steps(self):
        price1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        price2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        total_cash = self.risk_manager.curr_cash
        expensive = max(price1, price2)
        cheaper = min(price1, price2)

        k = int(expensive / cheaper) + 1
        min_cash_per_step = expensive + (cheaper * k)
        feasible_steps = int(total_cash // min_cash_per_step)
        max_steps = 1 / self.position_size
        self.max_steps = max(1, min(max_steps, feasible_steps))
    
    def compute_share_split(self):
        curr_cash = self.risk_manager.curr_cash - self.position_manager.cost_basis()
        curr_s1, curr_s2 = self.position_manager.total_shares()

        price1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        price2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        alloc_cash = curr_cash / (self.max_steps - self.curr_steps)
        target_value = curr_s1 * price1 + curr_s2 * price2 + alloc_cash

        denom = price1 + self.hedge_ratio * price2
        if denom <= 0:
            return 0, 0

        target_s1 = max(1, int(target_value // denom))
        target_s2 = max(1, int(self.hedge_ratio * target_s1))
        cost = target_s1 * price1 + target_s2 * price2
        remaining_cash = target_value - cost

        best_s2 = target_s2
        max_adj = int(remaining_cash // price2)
        for i in range(1, max_adj):
            adj_s2 = target_s2 + i
            if abs(self.hedge_ratio - (adj_s2 / target_s1)) < abs(self.hedge_ratio - (best_s2 / target_s1)):
                best_s2 = adj_s2
        target_s2 = best_s2

        shares1 = target_s1 - curr_s1
        shares2 = target_s2 - curr_s2

        return shares1, shares2
   
    def compute_position_value(self):
        direction = self.position_manager.direction()
        shares1, shares2 = self.position_manager.total_shares()
        entry1, entry2 = self.position_manager.average_entry()

        exit1 = self.s1["bid"] if direction > 0 else self.s1["ask"]
        exit2 = self.s2["bid"] if direction > 0 else self.s2["ask"]

        pnl = (direction * (exit1 - entry1) * shares1) - (direction * (exit2 - entry2) * shares2)
        position_value = shares1 * entry1 + shares2 * entry2

        return pnl / position_value
    
    def beta_distribution(self, window=15):
        df1 = open_data(self.symbol1, mode="intraday")
        df2 = open_data(self.symbol2, mode="intraday")
        df = (
            df1[['timestamp', 'close']].rename(columns={'close': 'y'})
            .merge(df2[['timestamp', 'close']].rename(columns={'close': 'x'}), on='timestamp')
            .sort_values('timestamp')
        )
        df['date'] = df['timestamp'].dt.date

        def compute_beta(x, y):
            x_mean = np.mean(x)
            y_mean = np.mean(y)
            return np.sum((x - x_mean)*(y - y_mean)) / np.sum((x - x_mean)**2)
        
        hr = []
        for _, g in df.groupby('date'):
            x = g['x'].to_numpy()
            y = g['y'].to_numpy()

            for i in range(window, len(x)):
                hr.append(compute_beta(
                    x[i-window:i],
                    y[i-window:i]
                ))

        hr = np.array(hr)
        self.hedge_ratio_mean = np.mean(hr)
        self.hedge_ratio_std = np.std(hr, ddof=1)

    def save_data(self, ts, data, save_time=(15, 30)):
        if not self.saved:
            self.data_history[ts.isoformat()] = data
            if self.trade_window(save_time, save_time):
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
            weighted_sum1 += leg1.entry_price * leg1.shares
            total1 += leg1.shares

            weighted_sum2 += leg2.entry_price * leg2.shares
            total2 += leg2.shares

        avg1 = weighted_sum1 / total1 if total1 > 0 else 0
        avg2 = weighted_sum2 / total2 if total2 > 0 else 0

        return avg1, avg2
    
    def total_shares(self):
        shares1 = shares2 = 0
        for leg1, leg2 in self.pairs:
            shares1 += leg1.shares
            shares2 += leg2.shares
        return shares1, shares2
    
    def cost_basis(self):
        value = 0
        for leg1, leg2 in self.pairs:
            value += leg1.shares * leg1.entry_price
            value += leg2.shares * leg2.entry_price
        return value
    
    def reset(self):
        self.pairs = []
    
    def in_trade(self):
        return bool(self.pairs)