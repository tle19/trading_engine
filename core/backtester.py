import pandas as pd
from metrics import *
from utils import *

PESS = "pess"
OPT = "opt"

class Backtest:
    def __init__(self, symbol, strategy_class, cash=25_000, shares=10, 
                 margin=1.0, commission=0.0, slippage=0.0002, force_close=True):
        self.symbol = symbol
        self.strategy = strategy_class
        self.cash = cash
        self.shares = shares * margin
        self.margin = margin
        self.commission = commission
        self.slippage = slippage
        self.force_close = force_close

        self.stats = Stats(symbol)
        self.plotting = Plotting(symbol)
        self.risk_manager = self.strategy.get_risk_manager()

    def run(self, start_date="2023-10-02", end_date="2024-10-02", plot=False):
        df = open_data(self.symbol, start_date, end_date, start_time="9:30", end_time="16:00")

        pess_cash = opt_cash = avg_cash = self.cash
        position = None
        entry_price = None

        for _, row in df.iterrows():
            stop_loss = self.strategy.get_stop_loss()
            take_profit = self.strategy.get_take_profit()

            signal = self.strategy.generate_signal(row)

            close = row['close']
            high = row['high']
            low = row['low']
            ts = row["timestamp"]

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
                if position == "long":
                    stop_price = entry_price * (1 - stop_loss) * (1 - self.slippage)
                    profit_price = entry_price * (1 + take_profit)
                    pnl = 0

                    # --- Force Close ---
                    if self.force_close and (ts.hour, ts.minute) >= (15, 58):
                        pnl = (close * (1 - self.slippage) - entry_price) * self.shares
                        self.stats.update_trade(pnl, PESS)
                        self.stats.update_trade(pnl, OPT)
                        pess_cash += pnl
                        opt_cash += pnl
                    else:
                        # --- Pessimistic Case ---
                        if low <= stop_price:
                            pnl = (stop_price - entry_price) * self.shares
                        elif high >= profit_price:
                            pnl = (profit_price - entry_price) * self.shares
                        self.stats.update_trade(pnl, PESS)
                        pess_cash += pnl

                        # --- Optimistic Case ---
                        if high >= profit_price:
                            pnl = (profit_price - entry_price) * self.shares
                        elif low <= stop_price:
                            pnl = (stop_price - entry_price) * self.shares
                        self.stats.update_trade(pnl, OPT)
                        opt_cash += pnl

                    self.risk_manager.check_risk(pnl)
                   
                elif position == "short":
                    stop_price = entry_price * (1 + stop_loss) * (1 + self.slippage)
                    profit_price = entry_price * (1 - take_profit)
                    pnl = 0

                    # --- Force Close ---   
                    if self.force_close and (ts.hour, ts.minute) >= (15, 58):
                        pnl = (entry_price - close * (1 + self.slippage)) * self.shares
                        self.stats.update_trade(pnl, PESS)
                        self.stats.update_trade(pnl, OPT)
                        pess_cash += pnl
                        opt_cash += pnl
                    else:
                        # --- Pessimistic Case ---
                        if high >= stop_price:
                            pnl = (entry_price - stop_price) * self.shares
                        elif low <= profit_price:
                            pnl = (entry_price - profit_price) * self.shares
                        self.stats.update_trade(pnl, PESS)
                        pess_cash += pnl

                        # --- Optimistic Case ---
                        if low <= profit_price:
                            pnl = (entry_price - profit_price) * self.shares
                        elif high >= stop_price:
                            pnl = (entry_price - stop_price) * self.shares
                        self.stats.update_trade(pnl, OPT)
                        opt_cash += pnl

                    self.risk_manager.check_risk(pnl)

                position = None
                entry_price = None
                avg_cash = (pess_cash + opt_cash) / 2

            self.update_equity(position, pess_cash, opt_cash, avg_cash, close, entry_price)

        self.stats.update_cash_vals(self.cash, pess_cash, opt_cash, avg_cash)
        self.stats.update_dates(start_date, end_date)
        self.plotting.update_dates(start_date, end_date)

        self.stats.summary()
        self.plotting.plot_equity() if plot else None

    def update_equity(self, position, pess_cash, opt_cash, avg_cash, close, entry_price, mode=""):
        if mode == "pess":
            cash = pess_cash
        elif mode == "opt":
            cash = opt_cash
        else:
            cash = avg_cash

        current_equity = cash
        if position == "long":
            current_equity = self.shares * (close - entry_price) + cash
        elif position == "short":
            current_equity = self.shares * (entry_price - close) + cash
        self.stats.update_intraday_equity(current_equity)
        self.plotting.update_intraday_equity(current_equity)

    def get_stats_class(self):
        return self.stats