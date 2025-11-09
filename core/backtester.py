from collections import deque

from metrics import *
from utils import *

class Backtest:
    def __init__(self, symbol, strategy_class, cash=25_000, shares=30, 
                 margin=1.0, commission=0.0, slippage=0.1):
        self.symbol = symbol
        self.strategy = strategy_class
        self.cash = cash
        self.shares = shares
        self.margin = margin
        self.commission = commission
        self.slippage = slippage

        self.stats = Stats(symbol)
        self.plotting = Plotting(symbol)
        self.risk_manager = self.strategy.get_risk_manager()

    def run(self, start_date="2023-11-01", end_date="2025-11-01", plot=False, save_plot=False):
        df = open_data(self.symbol, start_date, end_date, start_time="9:30", end_time="16:00")

        spread_window = deque(maxlen=10)

        self.risk_manager.set_start_cash(self.cash) # for testing purposes

        entry_price = None

        rows = df.itertuples(index=False)
        for row in rows:
            open = row.open
            close = row.close
            high = row.high
            low = row.low
            ts = row.timestamp

            self.shares = self.cash // close # for consistent testing

            signal = self.strategy.generate_signal(row)

            stop_price = self.strategy.get_stop_price()
            profit_price = self.strategy.get_profit_price()
            position = self.strategy.get_position()
            position_size = self.strategy.get_position_size()
            shares = max(1, int(self.shares * position_size))

            spread_window.append((high - low) / close)
            if signal is not None and spread_window:
                avg_spread = sum(spread_window) / len(spread_window)
                slippage = avg_spread * self.slippage
                slip_up = 1 + slippage
                slip_dn = 1 - slippage

            # --- Enter Long ---
            if signal == 1 and position == "long":
                entry_price = close * slip_up

            # --- Enter Short ---
            elif signal == -1 and position == "short":
                entry_price = close * slip_dn

            # --- Exit Position ---
            elif signal == 0 and position is not None:
                pnl = 0
                exit_price = None
                if position == "long":
                    if low <= stop_price:
                        exit_price = stop_price * slip_dn
                    elif high >= profit_price:
                        exit_price = profit_price
                    elif (ts.hour, ts.minute) >= (15, 58):
                        exit_price = close * slip_dn

                    pnl = (exit_price - entry_price) * shares
     
                elif position == "short":
                    if high >= stop_price:
                        exit_price = stop_price * slip_up
                    elif low <= profit_price:
                        exit_price = profit_price
                    elif (ts.hour, ts.minute) >= (15, 58):
                        exit_price = close * slip_up

                    pnl = (entry_price - exit_price) * shares

                self.cash += pnl
                # print(pnl)
                self.strategy.flatten()
                self.risk_manager.update_risk(pnl)
                self.stats.update_trade(pnl)
                
            self.update_equity(self.cash, position, shares, close, entry_price, ts)
            
        self.stats.update_dates(start_date, end_date)
        self.stats.summary()
        # print(sum(self.strategy.trades) / len(self.strategy.trades))
        if plot:
            self.plotting.update_dates(start_date, end_date)
            self.plotting.plot_equity(save_plot, overlay=True)

    def update_equity(self, cash, position, shares, close, entry_price, ts):
        current_equity = cash
        
        if position == "long":
            current_equity += (close - entry_price) * shares
        elif position == "short":
            current_equity += (entry_price - close) * shares

        self.stats.update_intraday_equity(ts, current_equity)
        self.plotting.update_intraday_equity(current_equity)

    def get_stats_class(self):
        return self.stats