from collections import deque

from metrics import *
from utils import *

class Backtest:
    def __init__(self, symbol, strategy_class, cash=25_000, shares=50, 
                 margin=1.0, commission=0.0, slippage=0.1):
        self.symbol = symbol
        self.strategy = strategy_class
        self.cash = cash
        self.shares = shares
        self.margin = margin
        self.commission = commission
        self.slippage = slippage

        self.entry_price = None
        self.spread_window = deque(maxlen=10)
        self.slip_up = 0
        self.slip_dn = 0

        self.stats = Stats(symbol)
        self.plotting = Plotting(symbol)
        # self.trade_log = TradeLogger()
        self.risk_manager = self.strategy.get_risk_manager()

    def run(self, start_date="2023-11-01", end_date="2025-11-01", plot=False, save_plot=False):
        df = open_data(self.symbol, start_date, end_date, start_time="9:30", end_time="16:00")
        rows = df.itertuples(index=False)

        for row in rows:
            self.open = row.open
            self.close = row.close
            self.high = row.high
            self.low = row.low
            self.ts = row.timestamp

            if (self.ts.hour, self.ts.minute) == (9, 30):
                self.risk_manager.set_start_cash(self.cash)
                self.shares = self.cash // self.open

            signal = self.strategy.generate_signal(row)
            self.dynamic_slippage(signal)
            self.interpret_signal(signal)
            
        self.stats.update_dates(start_date, end_date)
        self.stats.summary()
        if plot:
            self.plotting.update_dates(start_date, end_date)
            self.plotting.plot_equity(save_plot, overlay=True)

    def interpret_signal(self, signal):
        stop_price = self.strategy.get_stop_price()
        profit_price = self.strategy.get_profit_price()
        position = self.strategy.get_position()
        position_size = self.strategy.get_position_size()
        shares = max(1, int(self.shares * position_size))
        
        # --- Enter Long ---
        if signal == 1 and position == "long":
            self.entry_price = self.close * self.slip_up
            self.strategy.update_entry_price(self.entry_price)

        # --- Enter Short ---
        elif signal == -1 and position == "short":
            self.entry_price = self.close * self.slip_dn
            self.strategy.update_entry_price(self.entry_price)

        # --- Exit Position ---
        elif signal == 0 and position is not None:
            exit_price = None
            pnl = 0

            if position == "long":
                if self.low <= stop_price:
                    exit_price = stop_price * self.slip_dn
                elif self.high >= profit_price:
                    exit_price = profit_price
                elif (self.ts.hour, self.ts.minute) >= (15, 58):
                    exit_price = self.close * self.slip_dn
                else:
                    exit_price = self.close * self.slip_dn
                pnl = (exit_price - self.entry_price) * shares
    
            elif position == "short":
                if self.high >= stop_price:
                    exit_price = stop_price * self.slip_up
                elif self.low <= profit_price:
                    exit_price = profit_price
                elif (self.ts.hour, self.ts.minute) >= (15, 58):
                    exit_price = self.close * self.slip_up
                else:
                    exit_price = self.close * self.slip_up
                pnl = (self.entry_price - exit_price) * shares

            self.cash += pnl
            self.risk_manager.update_risk(pnl)
            self.stats.update_trade(pnl)
            self.strategy.flatten()
            position = None
            # print(self.ts, ": ", pnl)

        self.update_equity(position, shares)

    def dynamic_slippage(self, signal):
        self.spread_window.append((self.high - self.low) / self.close)
        if signal is not None and self.spread_window:
            avg_spread = sum(self.spread_window) / len(self.spread_window)
            slippage = avg_spread * self.slippage
            self.slip_up = 1 + slippage
            self.slip_dn = 1 - slippage

    def update_equity(self, position, shares):
        current_equity = self.cash
        
        if position == "long":
            current_equity += (self.close - self.entry_price) * shares
        elif position == "short":
            current_equity += (self.entry_price - self.close) * shares

        self.stats.update_intraday_equity(self.ts, current_equity)
        self.plotting.update_intraday_equity(current_equity)

    def get_stats_class(self):
        return self.stats