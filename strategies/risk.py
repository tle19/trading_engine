import numpy as np
import pandas as pd

class RiskManager:
    def __init__(self, pnl_target=0.02, pnl_loss=-0.01, trade_max=3, drawdown_max=0.25):
        self.pnl_target = pnl_target
        self.pnl_loss = pnl_loss
        self.trade_max = trade_max
        self.drawdown_max = drawdown_max
        
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
        
        drawdown = self.calculate_drawdown()
        if drawdown > self.drawdown_max:
            self.position_size = 0.75
        else:
            self.position_size = 1.0

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

    def calculate_drawdown(self):
        drawdown = (self.peak_cash - self.curr_cash) / self.peak_cash
        return drawdown

    def reset(self):
        self.trades = 0
        self.pnl = 0
        self._day_pause = False

    def equity_slope(self, intraday_equity, lookback=10): # find all other drawdowns to compare
        df = pd.DataFrame(list(intraday_equity.items()), columns=['timestamp', 'equity'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        start_time = df['timestamp'].iloc[-1] - pd.Timedelta(days=lookback)
        df = df[df['timestamp'] >= start_time]
        x = (df['timestamp'] - df['timestamp'].iloc[0]).dt.total_seconds()
        y = df['equity'].values
        return np.polyfit(x, y, 1)[0]
        
    def drawdown_rebalance(self, drawdown, slope, day_rebalance=7):
        if drawdown > 0.05:
            days = 3
        else:
            days = day_rebalance
        return days