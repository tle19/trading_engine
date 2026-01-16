import os
import time
from collections import deque

from metrics import *
from utils import *

class Backtest:
    def __init__(self, symbols, strategy_class, cash=25_000, 
                 margin=1.0, commission=0.0, slippage=0.1):
        self.cash = cash * margin
        self.symbols = symbols
        self.strategy_class = strategy_class

        self.commission = commission
        self.slippage = slippage  # execution time + bid/ask spread
        self.spread_window = deque(maxlen=10)
        self.slip_up = 0
        self.slip_dn = 0

    def run(self, start_date="2024-1-10", end_date="2026-1-10", display_plot=True, display_stats=True, save_plot=True):
        start_time = time.perf_counter()

        trade_history = []
        intraday_equity = []
        for symbol in self.symbols:
            self.initialize(symbol, self.strategy_class)
            df = open_data(symbol, start_date, end_date, start_time="9:30", end_time="15:59")

            for row in df.itertuples(index=False):
                self.ts = row.timestamp
                self.open = row.open
                self.high = row.high
                self.low = row.low
                self.close = row.close

                signal = self.strategy.generate_signal(row)
                self.dynamic_slippage(signal)
                self.interpret_signal(signal, symbol)

            trade_history.extend(self.trade_manager.trade_history)
            intraday_equity.append(self.trade_manager.intraday_equity)

            self.stats.update_data(self.trade_manager.trade_history, self.trade_manager.intraday_equity)
            self.stats.summary()

            self.plotting.update_data(self.trade_manager.intraday_equity)
            self.plotting.plot_equity(display=False, save=save_plot)
        
        # sort trade_history by "exit_time"
        intraday_equity = self.combine_equity_dicts(intraday_equity)

        if display_stats:
            stats = Stats("COMBINED")
            stats.update_data(trade_history, intraday_equity)
            stats.summary()

        self.trade_manager.update_data(trade_history, intraday_equity)
        self.trade_manager.save_logs()

        elapsed_time = time.perf_counter() - start_time
        print(f"Elapsed Backtest Time: {elapsed_time:.6f} seconds")

        if display_plot:
            plotting = Plotting("COMBINED")
            plotting.update_data(intraday_equity)
            plotting.plot_equity(display=display_plot, save=save_plot, overlay=False)
        
    def interpret_signal(self, signal, symbol):
        name = self.strategy.__class__.__name__
        direction = self.position_manager.direction()
        if direction:
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
            self.trade_manager.log_entry(name, leg, symbol, direction, position_size, shares, self.ts, entry_price, fill_price, stop_price, target_price, self.strategy.features)
            # print(f"{self.ts} | ENTRY (L): {fill_price}, STOP: {stop_price}, PROFIT: {target_price}")

        # --- Enter Short ---
        elif signal == -1:
            fill_price = entry_price * self.slip_dn
            leg.entry_price = fill_price
            self.trade_manager.log_entry(name, leg, symbol, direction, position_size, shares, self.ts, entry_price, fill_price, stop_price, target_price, self.strategy.features)
            # print(f"{self.ts} | ENTRY (S): {fill_price}, STOP: {stop_price}, PROFIT: {target_price}")

        # --- Adjust Stops / Targets ---
        elif signal == 9:
            raise NotImplementedError
        
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

                    self.cash_allocation += pnl
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
        current_equity = self.cash_allocation
        
        for leg in self.position_manager.legs:
            if leg.direction == 1:
                current_equity += (self.close - leg.entry_price) * leg.shares
            elif leg.direction == -1:
                current_equity += (leg.entry_price - self.close) * leg.shares

        self.trade_manager.update_intraday_equity(self.ts, current_equity)

    def initialize(self, symbol, strategy_class):
        self.strategy = strategy_class(symbol)
        self.cash_allocation = round(self.cash / len(self.symbols), 2)
        self.strategy.risk_manager.start_cash = self.cash_allocation
        
        self.risk_manager = self.strategy.risk_manager
        self.position_manager = self.strategy.position_manager

        self.trade_manager = TradeManager(live=False)
        self.stats = Stats(symbol)
        self.plotting = Plotting(symbol)

    def combine_equity_dicts(self, dicts):
        combined = {}
        for d in dicts:
            for ts, eq in d.items():
                combined[ts] = combined.get(ts, 0) + eq
        return combined
