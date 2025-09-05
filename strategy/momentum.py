import pandas as pd

class Momentum:
    def __init__(self,
                 hod_json="hod_results.json",
                 overnight_json="overnight_results.json",
                 profit_ratio=0.01,
                 max_holding_days=1):
        self.profit_ratio = profit_ratio
        self.max_holding_days = max_holding_days

        self.in_position = False
        self.entry_price = 0
        self.holding_days = 0
        self.trade_done_today = False
        self.bullish_trade_done = False
        self.bearish_trade_done = False
        self.last_date = None

        # Load stats
        hod_stats = pd.read_json(hod_json)
        self.avg_hod_return = hod_stats["average_hod_return_pct"].iloc[0] / 100.0
        self.avg_hod_prob = hod_stats["average_hod_prob"].iloc[0]

        overnight_stats = pd.read_json(overnight_json)
        self.avg_pct_return = overnight_stats["average_pct_return"].iloc[0] / 100.0

    def update(self, row):
        close = row['close']
        low = row['low']
        current_date = row.name.date()

        if self.last_date != current_date:
            self.trade_done_today = False
            self.bullish_trade_done = False
            self.bearish_trade_done = False
            self.last_date = current_date

        signal = 0

        # ----------- Entry Logic -----------
        if not self.bullish_trade_done and not self.in_position:
            self.in_position = True
            self.entry_price = close
            self.holding_days = 0
            self.bullish_trade_done = True
            signal = 1

        elif not self.bearish_trade_done and not self.in_position:
            if low <= self.entry_price:
                self.in_position = True
                self.entry_price = low
                self.holding_days = 0
                self.bearish_trade_done = True
                signal = 1

        # ----------- Exit Logic -----------
        if self.in_position:
            self.holding_days += 1
            if close >= self.entry_price * (1 + self.profit_ratio):
                signal = -1
                self._exit_trade()
            elif close >= self.entry_price * (1 + self.avg_pct_return):
                signal = -1
                self._exit_trade()
            elif self.holding_days >= self.max_holding_days:
                signal = -1
                self._exit_trade()

        return signal

    def _exit_trade(self):
        self.in_position = False
        self.entry_price = 0
        self.holding_days = 0
