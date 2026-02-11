from strategies import StrategyPair
from models import *
from utils import *

class SpreadScalp(StrategyPair):
    def __init__(self, pair, ema_window=5, start_time=(15, 00), end_time=(20, 00),
                 take_profit=0.000025, pnl_target=0.01, pnl_loss=-0.01, trade_max=400):
        super().__init__(pair, start_time, end_time, take_profit, 
                         pnl_target, pnl_loss, trade_max)
        self.ema_window = ema_window

        self.ema1 = None
        self.ema2 = None
    
    def generate_signal(self, row, symbol):
        self.update(symbol, row)

        if self.risk_manager._day_pause: 
            return None
        if not self.trade_window() and not self.s1["direction"]:
            return None

        signal = None
        if self.activated:
            self.compute_indicators()
            if self.received and self.ticks > 10:
                if self.s1["direction"]:
                    signal = self.exit_trade()
                else:
                    signal = self.enter_trade()
        return signal
    
    def enter_trade(self, ms=500):
        signal = None
        if self.s1["latency"] > ms or self.s2["latency"] > ms:
            return signal
        
        if self.mid1 < self.ema1 and self.mid2 > self.ema2:
            signal = self.buy_pair()
        elif self.mid1 > self.ema1 and self.mid2 < self.ema2:
            signal = self.sell_pair()
        return signal
        
    def exit_trade(self, ms=500):
        if self.s1["latency"] > ms or self.s2["latency"] > ms:
            return

        exit1 = self.s1["bid"] if self.s1["direction"] > 0 else self.s1["ask"]
        exit2 = self.s2["bid"] if self.s2["direction"] > 0 else self.s2["ask"]
        pnl1 = self.s1["direction"] * (exit1 - self.s1["entry_price"]) * self.s1["shares"]
        pnl2 = self.s2["direction"] * (exit2 - self.s2["entry_price"]) * self.s2["shares"]

        position_value = (self.s1["shares"] * self.s1["entry_price"]) + (self.s2["shares"] * self.s2["entry_price"])
        if (pnl1 + pnl2) / position_value > self.take_profit or (self.ticks > 1000 and (pnl1 + pnl2) / position_value > self.take_profit / 2):
            return self.exit()
        
    def compute_indicators(self):
        self.mid1 = (self.s1["bid"] + self.s1["ask"]) * 0.5
        self.mid2 = (self.s2["bid"] + self.s2["ask"]) * 0.5

        self.ema1 = self.compute_ema(self.ema1, self.mid1, self.ema_window)
        self.ema2 = self.compute_ema(self.ema2, self.mid2, self.ema_window)