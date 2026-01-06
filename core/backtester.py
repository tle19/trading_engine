import time
from collections import deque

from metrics import *
from utils import *

class Backtest:
    def __init__(self, symbol, strategy_class, cash=25_000, 
                 margin=1.0, commission=0.0, slippage=0.1):
        self.symbol = symbol
        self.strategy = strategy_class
        self.cash = cash * margin
        self.commission = commission
        self.slippage = slippage  # execution time + spread

        self.spread_window = deque(maxlen=10)
        self.slip_up = 0
        self.slip_dn = 0

        self.position_manager = self.strategy.position_manager
        self.risk_manager = self.strategy.risk_manager
        
        self.trade_manager = TradeManager(live=True)
        self.stats = Stats(symbol)
        self.plotting = Plotting(symbol)

        self.strategy.trade_manager = self.trade_manager

    def run(self, start_date="2023-11-10", end_date="2025-11-01", plot=False, save_plot=False, stats=True):
        start_time = time.perf_counter()
        df = open_data(self.symbol, start_date, end_date, start_time="9:30", end_time="16:00")

        for row in df.itertuples(index=False):
            self.open = row.open
            self.close = row.close
            self.high = row.high
            self.low = row.low
            self.ts = row.timestamp

            if (self.ts.hour, self.ts.minute) == (9, 30):
                self.risk_manager.start_cash = self.cash

            signal = self.strategy.generate_signal(row)
            self.dynamic_slippage(signal)
            self.interpret_signal(signal)

        self.stats.intraday_equity = self.trade_manager.intraday_equity
        self.stats.trade_history = self.trade_manager.trade_history
        self.stats.summary()

        elapsed_time = time.perf_counter() - start_time
        print(f"Elapsed Backtest Time: {elapsed_time:.6f} seconds")
        self.trade_manager.save_logs()
        
        if plot:
            self.plotting.intraday_equity = self.trade_manager.intraday_equity
            self.plotting.update_dates()
            self.plotting.plot_equity(save_plot, overlay=True)
        
    def interpret_signal(self, signal):
        direction = self.position_manager.direction()
        if direction:
            name = self.strategy.__class__.__name__
            leg = self.position_manager.legs[-1]
            entry_price = leg.entry_price
            stop_price = leg.stop_price
            target_price = leg.target_price
            position_size = leg.position_size
            shares = leg.shares

        # --- Enter Long ---
        if signal == 1:
            fill_price = entry_price * self.slip_up
            leg.entry_price = fill_price
            self.trade_manager.log_entry(name, leg, self.symbol, direction, position_size, shares, self.ts, entry_price, fill_price, stop_price, target_price, self.strategy.features)
            # print(f"{self.ts} | ENTRY (L): {fill_price}, STOP: {stop_price}, PROFIT: {target_price}")

        # --- Enter Short ---
        elif signal == -1:
            fill_price = entry_price * self.slip_dn
            leg.entry_price = fill_price
            self.trade_manager.log_entry(name, leg, self.symbol, direction, position_size, shares, self.ts, entry_price, fill_price, stop_price, target_price, self.strategy.features)
            # print(f"{self.ts} | ENTRY (S): {fill_price}, STOP: {stop_price}, PROFIT: {target_price}")

        # --- Exit Position ---
        elif signal == 0:
            for leg in self.position_manager.legs.copy():
                if leg.check_exit(self.ts, self.low, self.high) == 0:
                    entry_price = leg.entry_price
                    stop_price = leg.stop_price
                    target_price = leg.target_price
                    shares = leg.shares

                    if direction == 1:
                        if self.low <= stop_price:
                            fill_price = stop_price * self.slip_dn
                            exit_price = stop_price
                        elif self.high >= target_price:
                            fill_price = target_price
                            exit_price = target_price
                        elif (self.ts.hour, self.ts.minute) >= (15, 58):
                            fill_price = self.close * self.slip_dn
                            exit_price = self.close
                        else:
                            fill_price = self.close * self.slip_dn
                            exit_price = self.close
                        pnl = (fill_price - entry_price) * shares
            
                    elif direction == -1:
                        if self.high >= stop_price:
                            fill_price = stop_price * self.slip_up
                            exit_price = stop_price
                        elif self.low <= target_price:
                            fill_price = target_price
                            exit_price = target_price
                        elif (self.ts.hour, self.ts.minute) >= (15, 58):
                            fill_price = self.close * self.slip_up
                            exit_price = self.close
                        else:
                            fill_price = self.close * self.slip_up
                            exit_price = self.close
                        pnl = (entry_price - fill_price) * shares

                    self.cash += pnl
                    self.trade_manager.update_exit(leg, self.ts, exit_price, fill_price)
                    self.risk_manager.update_trade(pnl)
                    self.position_manager.remove_leg(leg)
                    # print(f"{self.ts} | EXIT: {fill_price}, PnL: {pnl}")

        self.update_equity()

    def dynamic_slippage(self, signal):
        self.spread_window.append((self.high - self.low) / self.close) # normalize by average of close and open?
        if signal is not None:
            avg_spread = sum(self.spread_window) / len(self.spread_window)
            slippage = avg_spread * self.slippage
            self.slip_up = 1 + slippage
            self.slip_dn = 1 - slippage

    def update_equity(self):
        current_equity = self.cash
        
        for leg in self.position_manager.legs:
            if leg.direction == 1:
                current_equity += (self.close - leg.entry_price) * leg.shares
            elif leg.direction == -1:
                current_equity += (leg.entry_price - self.close) * leg.shares

        self.trade_manager.update_intraday_equity(self.ts, current_equity)
