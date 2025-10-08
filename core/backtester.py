import pandas as pd
from metrics import *
from utils import *

class Backtest:
    def __init__(self, symbol, strategy_class, cash=30_000, margin=1.0, 
                 shares=1, commission=0.0, slippage=0.0005, force_close=True):
        self.symbol = symbol
        self.strategy = strategy_class(symbol)
        self.cash = cash
        self.shares = shares
        self.margin = margin
        self.commission = commission
        self.slippage = slippage
        self.force_close = force_close

        self.stats = Stats()

    def run(self, start_date="2025-1-03", end_date="2025-1-03", plot=False):
        df = open_data(self.symbol, start_date, end_date, start_time="9:30", end_time="16:00")

        pess_cash = opt_cash = avg_cash = self.cash
        pess_trades = []
        opt_trades = []
        
        position = None
        entry_price = None
        intraday_equity = []

        for _, row in df.iterrows():
            position_size = self.strategy.get_position_size()
            stop_loss = self.strategy.get_stop_loss()
            take_profit = self.strategy.get_take_profit()

            signal = self.strategy.generate_signal(row)

            close = row['close']
            high = row['high']
            low = row['low']
            ts = row["timestamp"]

            # self.shares = ((avg_cash * position_size) // close) * self.margin
            self.shares = 30

            # --- Enter Long ---
            if signal == 1 and position is None:
                position = "long"
                entry_price = close

            # --- Enter Short ---
            elif signal == -1 and position is None:
                position = "short"
                entry_price = close

            # --- Exit ---
            elif signal == 0 and position is not None:
                if position == "long":
                    stop_price = entry_price * (1 - stop_loss)
                    profit_price = entry_price * (1 + take_profit)
                    pnl = 0

                    if self.force_close and (ts.hour, ts.minute) >= (15, 58):
                        pnl = (close - entry_price) * self.shares
                        if close > entry_price:
                            pess_trades.append(1)
                            opt_trades.append(1)
                        elif close <= entry_price:
                            pess_trades.append(0)
                            opt_trades.append(0)
                        pess_cash += pnl
                        opt_cash += pnl
                    else:
                        # pessimistic
                        if low <= stop_price:
                            pnl = (stop_price - entry_price) * self.shares
                            pess_trades.append(0)
                        elif high >= profit_price:
                            pnl = (profit_price - entry_price) * self.shares
                            pess_trades.append(1)
                        pess_cash += pnl

                        # optimistic
                        if high >= profit_price:
                            pnl = (profit_price - entry_price) * self.shares
                            opt_trades.append(1)
                        elif low <= stop_price:
                            pnl = (stop_price - entry_price) * self.shares
                            opt_trades.append(0)
                        opt_cash += pnl
                        
                elif position == "short":
                    stop_price = entry_price * (1 + stop_loss)
                    profit_price = entry_price * (1 - take_profit)
                    pnl = 0

                    if self.force_close and (ts.hour, ts.minute) >= (15, 58):
                        pnl = (entry_price - close) * self.shares
                        if close < entry_price:
                            pess_trades.append(1)
                            opt_trades.append(1)
                        elif close >= entry_price:
                            pess_trades.append(0)
                            opt_trades.append(0)
                        pess_cash += pnl
                        opt_cash += pnl
                    else:
                        # pessimistic
                        if high >= stop_price:
                            pnl = (entry_price - stop_price) * self.shares
                            pess_trades.append(0)
                        elif low <= profit_price:
                            pnl = (entry_price - profit_price) * self.shares
                            pess_trades.append(1)
                        pess_cash += pnl

                        # optimistic
                        if low <= profit_price:
                            pnl = (entry_price - profit_price) * self.shares
                            opt_trades.append(1)
                        elif high >= stop_price:
                            pnl = (entry_price - stop_price) * self.shares
                            opt_trades.append(0)
                        opt_cash += pnl

                position = None
                entry_price = None
                avg_cash = (pess_cash + opt_cash) / 2

            current_equity = avg_cash
            if position == "long":
                current_equity = self.shares * (close - entry_price) + avg_cash
            elif position == "short":
                current_equity = self.shares * (entry_price - close) + avg_cash
            intraday_equity.append(current_equity)

        self.stats.summary(
            self.cash, pess_cash, opt_cash, avg_cash,
            pess_trades, opt_trades, intraday_equity
        )   #caclulate average win rate in function
        
        if plot:
            plot_equity(intraday_equity, self.symbol, start_date, end_date)