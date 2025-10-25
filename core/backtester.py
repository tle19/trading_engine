import pandas as pd
from metrics import *
from utils import *

class Backtest:
    def __init__(self, symbol, strategy_class, cash=25_000, shares=30, 
                 margin=1.0, commission=0.0, slippage=0.1):
        self.symbol = symbol
        self.strategy = strategy_class
        self.starting_cash = cash
        self.shares = shares * margin
        self.shares = shares
        self.margin = margin
        self.commission = commission
        self.slippage = slippage
        self.force_close = self.strategy.is_force_close()

        self.stats = Stats(symbol)
        self.plotting = Plotting(symbol)
        self.risk_manager = self.strategy.get_risk_manager()

    def run(self, start_date="2023-10-01", end_date="2024-10-01", plot=False):
        df = open_data(self.symbol, start_date, end_date, start_time="9:30", end_time="16:00")
        df["spread"] = (df["high"] - df["low"]) / df["close"]
        avg_spread = df["spread"].mean()
        self.slippage *= avg_spread # pct of spread

        self.risk_manager.set_start_cash(self.starting_cash) # for testing purposes

        curr_cash = self.starting_cash
        position = None
        entry_price = None

        rows = df.itertuples(index=False)
        for row in rows:
            close = row.close
            high = row.high
            low = row.low
            ts = row.timestamp

            self.shares = 25_000 // close # for consistent testing
            position_size = self.strategy.get_position_size()
            shares = max(1, int(round(self.shares * position_size)))
            
            signal = self.strategy.generate_signal(row)

            stop_price = self.strategy.get_stop_price()
            profit_price = self.strategy.get_profit_price()

            # --- Enter Long ---
            if signal == 1 and position is None:
                position = "long"
                entry_price = close * (1 + self.slippage)

            # --- Enter Short ---
            elif signal == -1 and position is None:
                position = "short"
                entry_price = close * (1 - self.slippage)

            # --- Exit ---
            elif signal == 0 and position is not None:
                pnl = 0
                if position == "long":
                    if self.force_close and (ts.hour, ts.minute) == (15, 58):
                        pnl = ((close * (1 - self.slippage)) - entry_price) * shares
                    else:
                        if low <= stop_price:
                            pnl = ((stop_price * (1 - self.slippage)) - entry_price) * shares
                        elif high >= profit_price:
                            pnl = (profit_price - entry_price) * shares
                            
                elif position == "short":
                    if self.force_close and (ts.hour, ts.minute) == (15, 58):
                        pnl = (entry_price - (close * (1 + self.slippage))) * shares
                    else:
                        if high >= stop_price:
                            pnl = (entry_price - (stop_price * (1 + self.slippage))) * shares
                        elif low <= profit_price:
                            pnl = (entry_price - profit_price) * shares

                position = None
                entry_price = None
                curr_cash += pnl
                self.stats.update_trade(pnl)
                self.risk_manager.check_risk(pnl)

            self.update_equity(curr_cash, position, shares, close, entry_price, ts)
            if (ts.hour, ts.minute) == (15, 59):
                self.risk_manager.reset_risk()

        self.stats.update_cash_vals(self.starting_cash, curr_cash)
        self.stats.update_dates(start_date, end_date)
        self.plotting.update_dates(start_date, end_date)

        self.stats.summary()
        self.plotting.plot_equity() if plot else None

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