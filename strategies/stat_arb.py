import numpy as np
from collections import deque

from strategies import StrategyPair
from models import *
from utils import *

class StatArb(StrategyPair):
    def __init__(self, pair, ema_window=5, start_time=(16, 00), end_time=(20, 00), decay_start=1000, decay_end=2000,
                 stop_loss=0.0001, take_profit=0.00001, pnl_target=0.01, pnl_loss=-0.01, trade_max=400):
        super().__init__(pair, start_time, end_time, stop_loss, take_profit, 
                         pnl_target, pnl_loss, trade_max)
        self.ema_window = ema_window
        self.decay_start = decay_start
        self.decay_end = decay_end

        self.ema1 = None
        self.ema2 = None
        
        self.rolling_spread = deque(maxlen=50)

        self.saved = False
        self.history = []