import time
import numpy as np
from collections import deque
from itertools import product
import datetime

from core import *
from metrics import *
from strategies import *
from models import *
from utils import *

class Backtest:
    def __init__(self, symbols, strategy_class, cash=25_000, 
                 margin=1.0, commission=0.0, slippage=0.1):
        self.cash = cash
        self.margin = margin
        self.symbols = symbols if isinstance(symbols, list) else [symbols]
        self.strategy_class = strategy_class

        self.commission = commission
        self.slippage = slippage  # execution time + bid/ask spread
        self.cash_allocation = round(self.cash / len(self.symbols), 2)

        self.spread_window = deque(maxlen=5)
        self.slip_up = 0
        self.slip_dn = 0

        self.train_time = 0
        self.train_wait = True

    def run(self, start_date="2024-1-10", end_date="2026-1-10", 
            grid=False, train=False, display_stats=True, display_plot=True, data_type=False):
        start_time = time.perf_counter()

        self.start_date = start_date
        self.trade_history = []
        self.intraday_equity = []
        for symbol in self.symbols:
            mode = "daily" if data_type else "intraday"
            df = open_data(symbol, start_date, end_date, mode)
            self.initialize(symbol, self.strategy_class)
            
            if grid:
                self.grid_search(symbol, df, train)
            else:
                self.run_simulation(symbol, df, train, display_stats, display_plot)

            self.trade_history.extend(self.trade_manager.trade_history)
            self.intraday_equity.append(self.trade_manager.intraday_equity)

        self.trade_history = self.sort_trade_history(self.trade_history)
        self.intraday_equity = self.combine_equity_dicts(self.intraday_equity)

        stats = Stats("AGGREGATE")
        stats.update_data(self.trade_history, self.intraday_equity)
        stats.summary(display_stats)

        self.trade_manager.update_data(self.trade_history, self.intraday_equity)
        self.trade_manager.save_logs()

        elapsed_time = time.perf_counter() - start_time
        print(f"Elapsed Backtest Time: {elapsed_time:.3f} seconds")

        plotting = Plotting("AGGREGATE")
        plotting.update_data(self.intraday_equity)
        plotting.plot_equity(display=display_plot, overlay=False)

    def run_simulation(self, symbol, df, train, display_stats, display_plot):
        for row in df.itertuples(index=False):
            self.ts = row.timestamp
            self.open = row.open
            self.high = row.high
            self.low = row.low
            self.close = row.close

            if train and (self.ts.hour, self.ts.minute) == (9, 30):
                self.train_model(symbol)
            
            signal = self.strategy.generate_signal(row, symbol)
            self.dynamic_slippage(signal)
            self.interpret_signal(signal, self.strategy)
            self.update_equity()

        self.stats.update_data(self.trade_manager.trade_history, self.trade_manager.intraday_equity)
        self.stats.summary(display=display_stats)

        if display_plot:
            self.plotting.update_data(self.trade_manager.intraday_equity)
            self.plotting.plot_equity(display=False)

    def interpret_signal(self, signal, strategy):
        name = strategy.__class__.__name__
        symbol = strategy.symbol
        position_manager = self.position_manager
        direction = position_manager.direction()
        if direction:
            leg = position_manager.legs[-1]
            entry_price = leg.entry_price
            stop_price = leg.stop_price
            target_price = leg.target_price
            position_size = leg.position_size
            shares = leg.shares * self.margin

        # --- Enter Long ---
        if signal == 1:
            fill_price = entry_price * self.slip_up
            leg.entry_price = fill_price
            self.trade_manager.log_entry(name, leg, symbol, direction, position_size, shares, self.ts, entry_price, fill_price, stop_price, target_price, strategy.features)
            # print(f"[{self.ts}] | ENTRY (L): {fill_price}, STOP: {stop_price}, TARGET: {target_price}")

        # --- Enter Short ---
        elif signal == -1:
            fill_price = entry_price * self.slip_dn
            leg.entry_price = fill_price
            self.trade_manager.log_entry(name, leg, symbol, direction, position_size, shares, self.ts, entry_price, fill_price, stop_price, target_price, strategy.features)
            # print(f"[{self.ts}] | ENTRY (S): {fill_price}, STOP: {stop_price}, TARGET: {target_price}")

        # --- Adjust Stops / Targets ---
        elif signal == 9:
            raise NotImplementedError
        
        # --- Exit Position ---
        elif signal == 0:
            for leg in position_manager.legs.copy():
                if leg.check_exit(self.ts, self.low, self.high) == 0:
                    entry_price = leg.entry_price
                    stop_price = leg.stop_price
                    target_price = leg.target_price
                    shares = leg.shares * self.margin

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
                    
                    self.trade_manager.update_exit(leg, self.ts, exit_price, fill_price)
                    self.update_pnl(pnl)
                    position_manager.remove_leg(leg)
                    # print(f"[{self.ts}] | EXIT: {fill_price}, PnL: {pnl}")

    def initialize(self, symbol, strategy_class, **params):
        self.strategy = strategy_class(symbol, **params)
        self.train_wait = True
        self.cash = self.cash_allocation
        self.strategy.risk_manager.start_cash = self.cash_allocation
        
        self.risk_manager = self.strategy.risk_manager
        self.position_manager = self.strategy.position_manager

        self.trade_manager = TradeManager(live=False)
        self.stats = Stats(symbol)
        self.plotting = Plotting(symbol)

    def dynamic_slippage(self, signal):
        self.spread_window.append((self.high - self.low) / self.close)
        if signal is not None:
            avg_spread = sum(self.spread_window) / len(self.spread_window)
            slippage = avg_spread * self.slippage
            self.slip_up = 1 + slippage
            self.slip_dn = 1 - slippage

    def update_pnl(self, pnl):
        self.cash += pnl
        self.risk_manager.update_trade(pnl)

    def update_equity(self):
        current_equity = self.cash
        
        for leg in self.position_manager.legs:
            if leg.direction == 1:
                current_equity += (self.close - leg.entry_price) * leg.shares * self.margin
            elif leg.direction == -1:
                current_equity += (leg.entry_price - self.close) * leg.shares * self.margin

        self.trade_manager.update_intraday_equity(self.ts, current_equity)

    def sort_trade_history(self, trade_history):
        trade_history.sort(key=lambda x: datetime.datetime.fromisoformat(x["exit_time"]))
        return trade_history

    def combine_equity_dicts(self, dicts):
        all_ts = sorted({ts for d in dicts for ts in d})
        combined = {ts: 0 for ts in all_ts}
        for d in dicts:
            last_eq = self.cash_allocation
            for ts in all_ts:
                eq = d.get(ts, 0)
                if eq == 0:
                    eq = last_eq
                else:
                    last_eq = eq
                combined[ts] += eq
        return combined
    
    def grid_search(self, symbol, df, train, optimize_period=100, rebalance_period=50, target_metric="Net Profit", top_n=5):
        param_grid = self.strategy.param_grid()
        combos = list(product(*param_grid.values()))
        total = len(combos)
        results = []

        best_score = -np.inf
        best_trade_manager = None

        for i, combo in enumerate(combos, 1):
            params = dict(zip(param_grid.keys(), combo))
            self.initialize(symbol, self.strategy_class, **params)
            self.run_simulation(symbol, df, train, display_stats=False, display_plot=False)

            stats_dict = self.stats.get_data_dict()
            if stats_dict[target_metric] > best_score:
                best_score = stats_dict[target_metric]
                best_trade_manager = self.trade_manager

            results.append({"PARAMS": params, "STATS": stats_dict})
            print(f"[{i}/{total}] Params: {params}")
        
        self.trade_manager = best_trade_manager
        top_results = sorted(results, key=lambda x: x["STATS"][target_metric], reverse=True)[:top_n]

        print("{symbol} TOP RESULTS:\n")
        for r in top_results:
            print(f"{target_metric}: {r['STATS'][target_metric]:.4f} | Params: {r['PARAMS']}")

        with open(f"{symbol}_{self.strategy.__class__.__name__}_grid_search.json", "w") as f:
            json.dump(results, f, indent=4)

    def train_model(self, symbol, train_period=100, validation_period=100, rebalance_period=3):
        self.train_time += 1
        if self.train_wait:
            required_date = pd.to_datetime(self.start_date) + pd.DateOffset(days=train_period + validation_period)
            required_date = required_date.tz_localize(self.ts.tz)
            if self.ts < required_date:
                return
            self.train_wait = False

        if self.train_time < rebalance_period:
            return
        self.train_time = 0

        curr_date = self.ts.normalize() 
        start_date = curr_date - pd.DateOffset(days=train_period + validation_period)

        trade_history = self.trade_manager.trade_history
        self.trade_manager.trade_history = [
            trade for trade in trade_history
            if start_date < pd.to_datetime(trade["entry_time"]).normalize() < curr_date
        ]
        self.trade_manager.save_logs()

        mdl = XGBModel(symbol=symbol, strategy=self.strategy.__class__.__name__, live=False)
        # mdl = RFModel(symbol=symbol, strategy=self.strategy.__class__.__name__, live=False)
        # mdl = KNNModel(symbol=symbol, strategy=self.strategy.__class__.__name__, live=False)
        mdl.initialize()
        X_train, X_test, y_train, y_test = train_test_split(mdl.df, n_days=train_period)
        if validation_period > 0:
            mdl.grid_search(X_train, X_test, y_train, y_test)
        else:
            mdl.train(X_train, y_train)
        self.strategy.model = mdl

        self.trade_manager.trade_history = trade_history