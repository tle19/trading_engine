class RiskManager:
    def __init__(self, pnl_target=0.02, pnl_loss=-0.01, trade_max=3):
        self.pnl_target = pnl_target
        self.pnl_loss = pnl_loss
        self.trade_max = trade_max
        
        self._start_cash = 0
        self.curr_cash = 0
        self.peak_cash = 0
        self.trades = 0
        self.pnl = 0
        self._day_pause = False
        self.position_size = 1.0

    def update_trade(self, pnl):
        self.pnl += pnl
        self.curr_cash += pnl
        self.peak_cash = max(self.curr_cash, self.peak_cash)
        self.trades += 1

        if self.trades >= self.trade_max:
            self._day_pause = True

        if self.pnl / self.curr_cash >= self.pnl_target:
            self._day_pause = True

        if self.pnl / self.curr_cash <= self.pnl_loss:
            self._day_pause = True

    @property
    def start_cash(self):
        return self._start_cash

    @start_cash.setter
    def start_cash(self, value):
        if value <= 0:
            raise ValueError("start_cash must be positive")
        self._start_cash = value
        self.curr_cash = value
        self.peak_cash = value

    def reset(self):
        self.trades = 0
        self.pnl = 0
        self._day_pause = False