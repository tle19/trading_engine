from metrics import *
from utils import *

class Backtest:
    def __init__(self, symbol, strategy_class, cash=25_000, shares=30, 
                 margin=1.0, commission=0.0, slippage=0.3):
        self.symbol = symbol
        self.strategy = strategy_class
        self.starting_cash = cash
        self.shares = shares
        self.margin = margin
        self.commission = commission
        self.slippage = slippage

        self.stats = Stats(symbol)
        self.plotting = Plotting(symbol)
        self.risk_manager = self.strategy.get_risk_manager()

    def run(self, start_date="2023-10-01", end_date="2024-10-01", plot=False):
        df = open_data(self.symbol, start_date, end_date, start_time="9:30", end_time="16:00")

        # Spread-Adjusted Slippage Calculation
        avg_spread = ((df["high"] - df["low"]) / df["close"]).mean() #deque (size 30)
        self.slippage *= avg_spread
        slip_up = 1 + self.slippage
        slip_dn = 1 - self.slippage
        curr_cash = self.starting_cash
        self.risk_manager.set_start_cash(self.starting_cash) # for testing purposes

        # total_entry_price = None
        entry_price = None

        # df.set_index('timestamp', inplace=True)
        # df = df.resample('5T').agg({
        #     'open': 'first',
        #     'high': 'max',
        #     'low': 'min',
        #     'close': 'last',
        #     'volume': 'sum'
        # }).dropna().reset_index()

        rows = df.itertuples(index=False)
        for row in rows:
            open = round(row.open, 2)
            close = round(row.close, 2)
            high = round(row.high, 2)
            low = round(row.low, 2)
            ts = row.timestamp

            self.shares = curr_cash // close # for consistent testing

            signal = self.strategy.generate_signal(row)

            stop_price = self.strategy.get_stop_price()
            profit_price = self.strategy.get_profit_price()
            position = self.strategy.get_position()
            position_size = self.strategy.get_position_size()
            shares = max(1, int(self.shares * position_size))

            # --- Enter Long ---
            if signal == 1 and position == "long":
                entry_price = close * slip_up
                # if entry_price is None: # multiple positions
                #     entry_price = close * slip_up
                #     total_entry_price = entry_price
                # else:
                #     total_entry_price += close * slip_up
                #     entry_price = round(total_entry_price / close)

            # --- Enter Short ---
            elif signal == -1 and position == "short":
                entry_price = close * slip_dn

            # --- Exit ---
            elif signal == 0 and position is not None:
                pnl = 0
                if position == "long":
                    if (ts.hour, ts.minute) >= (15, 58):
                        pnl = ((open * slip_dn) - entry_price) * shares
                    else:
                        if low <= stop_price:
                            pnl = ((stop_price * slip_dn) - entry_price) * shares
                        elif high >= profit_price:
                            pnl = (profit_price - entry_price) * shares
     
                elif position == "short":
                    if (ts.hour, ts.minute) >= (15, 58):
                        pnl = (entry_price - (open * slip_up)) * shares
                    else:
                        if high >= stop_price:
                            pnl = (entry_price - (stop_price * slip_up)) * shares
                        elif low <= profit_price:
                            pnl = (entry_price - profit_price) * shares

                curr_cash += pnl
                # print(ts, "STOP:", stop_price)
                # print(pnl)
                self.stats.update_trade(pnl)
                self.risk_manager.check_risk(pnl)
                self.strategy.flatten()

            self.update_equity(curr_cash, position, shares, close, entry_price, ts)
            
        self.stats.update_dates(start_date, end_date)
        self.stats.summary()
        if plot:
            self.plotting.update_dates(start_date, end_date)
            self.plotting.plot_equity(overlay=True)

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