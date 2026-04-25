import time
import numpy as np
from collections import deque
from itertools import product

from core import OHLCVRow, Level1Row, Level2Row
from metrics import *
from strategies import *
from models import *
from utils import *

def create_backtest(symbols, strategy_class, pairs=False, **kwargs):
    if pairs:
        return BacktestPairs(symbols, strategy_class, **kwargs)
    else:
        return Backtest(symbols, strategy_class, **kwargs)

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
        self.slip_up = 1
        self.slip_dn = 1

        self.train_time = 0
        self.train_wait = True

        self.elapsed_times = []

    def run(self, start_date="2024-1-10", end_date="2027-1-10", 
            grid=False, train=False, display=True, show_trade=False):
        start_time = time.perf_counter()

        self.start_date = start_date
        self.show_trade = show_trade
        self.trade_history = []
        self.intraday_equity = []
        for symbol in self.symbols:
            self.initialize(symbol)
            mode = "daily" if self.strategy.swing else "intraday" 
            df = open_data(symbol, start_date, end_date, mode)
            
            if grid:
                self.grid_search(symbol, df, train)
            else:
                self.run_simulation(symbol, df, train, display, display)

            self.trade_history.extend(self.trade_manager.trade_history)
            self.intraday_equity.append(self.trade_manager.intraday_equity)
            
        elapsed_time = time.perf_counter() - start_time

        self.trade_history = self.sort_trade_history(self.trade_history)
        self.intraday_equity = self.combine_equity_dicts(self.intraday_equity)

        if len(self.symbols) == 1:
            self.plotting.overview(display=display)
        else:
            stats = Stats("AGGREGATE")
            stats.update_data(self.trade_history, self.intraday_equity)
            stats.summary(display=display)

            plotting = Plotting("AGGREGATE")
            plotting.update_data(self.trade_history, self.intraday_equity)
            plotting.overview(display=display)

        self.trade_manager.update_data(self.trade_history, self.intraday_equity)
        self.trade_manager.save_logs()
        
        print(f"Elapsed Backtest Time: {elapsed_time:.3f} seconds")
        print(f"Average Compute Time: {np.mean(self.elapsed_times):.2f} ms/tick ({1000/np.mean(self.elapsed_times):.0f} ticks/s)")

    def run_simulation(self, symbol, df, train, display_stats=True, display_plot=True):
        for row in df.itertuples(index=False):
            start_time = time.perf_counter()

            self.ts = row.timestamp
            self.open = row.open
            self.high = row.high
            self.low = row.low
            self.close = row.close

            if train and (self.ts.hour, self.ts.minute) == (9, 30): # adjust to be first data point in new day
                self.train_model(symbol)

            signal = self.strategy.generate_signal(row, symbol)
            self.dynamic_slippage(signal)
            self.interpret_signal(signal, self.strategy)
            self.update_equity()
                
            if self.cash * self.margin < self.close:
                break

            self.elapsed_times.append((time.perf_counter() - start_time) * 1000)

        self.stats.update_data(self.trade_manager.trade_history, self.trade_manager.intraday_equity)
        self.stats.summary(display=display_stats)

        if display_plot:
            self.plotting.update_data(self.trade_manager.trade_history, self.trade_manager.intraday_equity)
            self.plotting.overview(display=False)

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
            if self.show_trade:
                print(f"[{self.ts}] | ENTRY (L): {fill_price}, STOP: {stop_price}, TARGET: {target_price}")

        # --- Enter Short ---
        elif signal == -1:
            fill_price = entry_price * self.slip_dn
            leg.entry_price = fill_price
            self.trade_manager.log_entry(name, leg, symbol, direction, position_size, shares, self.ts, entry_price, fill_price, stop_price, target_price, strategy.features)
            if self.show_trade:
                print(f"[{self.ts}] | ENTRY (S): {fill_price}, STOP: {stop_price}, TARGET: {target_price}")

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

                    pnl = direction * (fill_price - entry_price) * shares
                    self.trade_manager.update_exit(leg, self.ts, exit_price, fill_price)
                    self.update_pnl(pnl)
                    position_manager.remove_leg(leg)
                    if self.show_trade:
                        print(f"[{self.ts}] | EXIT: {fill_price}, PnL: {pnl}")

    def initialize(self, symbol, **params):
        self.strategy = self.strategy_class(symbol, **params)
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
            current_equity += leg.direction * (self.close - leg.entry_price) * leg.shares * self.margin

        self.trade_manager.update_intraday_equity(self.ts, current_equity)

    def sort_trade_history(self, trade_history):
        trade_history.sort(key=lambda x: x["entry_time"])
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
            self.initialize(symbol, **params)
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
            required_date = pd.Timestamp(self.start_date) + pd.DateOffset(days=train_period + validation_period)
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
            if start_date < pd.Timestamp(trade["entry_time"]).normalize() < curr_date
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


class BacktestPairs:
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
        self.slip_up = 1
        self.slip_dn = 1

        self.train_time = 0
        self.train_wait = True

        self.ts = None
        self.ts1 = None
        self.bid1 = None
        self.ask1 = None
        self.last1 = None
        self.bid_size1 = None
        self.ask_size1 = None
        self.ts2 = None
        self.bid2 = None
        self.ask2 = None
        self.last2 = None
        self.bid_size2 = None
        self.ask_size2 = None

        self.row1 = Level1Row()
        self.row2 = Level1Row()

        self.elapsed_times = []

    def run(self, start_date="2024-1-10", end_date="2026-1-10", 
            grid=False, train=False, display=True, show_trade=False):
        start_time = time.perf_counter()

        self.start_date = start_date
        self.show_trade = show_trade
        self.trade_history = []
        self.intraday_equity = []

        for pair in self.symbols:
            self.initialize(pair)

            symbol1, symbol2 = pair.split("-")
            df1 = open_data(symbol1, start_date, end_date, mode="quote")
            df2 = open_data(symbol2, start_date, end_date, mode="quote")
            df1["symbol"] = symbol1
            df2["symbol"] = symbol2
            df = pd.concat([df1, df2]).sort_values("timestamp")

            if grid:
                self.grid_search(pair, df, train)
            else:
                self.run_simulation(pair, df, train, display, display)

            self.trade_history.extend(self.trade_manager.trade_history)
            self.intraday_equity.append(self.trade_manager.intraday_equity)
        
        elapsed_time = time.perf_counter() - start_time

        self.trade_history = self.sort_trade_history(self.trade_history)
        self.intraday_equity = self.combine_equity_dicts(self.intraday_equity)

        if len(self.symbols) == 1:
            self.plotting.overview(display=display)
        else:
            stats = Stats("AGGREGATE")
            stats.update_data(self.trade_history, self.intraday_equity)
            stats.summary(display=display)

            plotting = Plotting("AGGREGATE")
            plotting.update_data(self.trade_history, self.intraday_equity)
            plotting.overview(display=display)

        self.trade_manager.update_data(self.trade_history, self.intraday_equity)
        self.trade_manager.save_logs()
        
        print(f"Elapsed Backtest Time: {elapsed_time:.3f} seconds")
        print(f"Average Compute Time: {np.mean(self.elapsed_times):.2f} ms/tick ({1000/np.mean(self.elapsed_times):.0f} ticks/s)")

    def run_simulation(self, pair, df, train, display_stats=True, display_plot=True):
        last_day = pd.Timestamp(self.start_date).date()
        symbol1, symbol2 = pair.split("-")
        for row in df.itertuples(index=False):
            start_time = time.perf_counter()
            symbol = row.symbol
            if symbol == symbol1:
                self.ts1 = row.timestamp
                self.bid1 = row.bid
                self.ask1 = row.ask
                self.last1 = row.last
                self.bid_size1 = row.bid_size
                self.ask_size1 = row.ask_size
            elif symbol == symbol2:
                self.ts2 = row.timestamp
                self.bid2 = row.bid
                self.ask2 = row.ask
                self.last2 = row.last
                self.bid_size2 = row.bid_size
                self.ask_size2 = row.ask_size

            if self.ts1 and self.ts2:
                self.ts = max(self.ts1, self.ts2)
            else:
                self.ts = row.timestamp

            current_day = self.ts.date() 
            if current_day != last_day:
                self.risk_manager.reset()
                last_day = current_day
            
            signal = self.strategy.generate_signal(row, symbol)
            # self.dynamic_slippage(signal)
            self.interpret_signal(signal, self.strategy)
            self.update_equity()
            
            if self.bid1 and self.bid2 and self.ask1 and self.ask2:
                if self.cash * self.margin < (self.bid1 + self.ask1) / 2:
                    break
            
            self.elapsed_times.append((time.perf_counter() - start_time) * 1000)
            
        self.stats.update_data(self.trade_manager.trade_history, self.trade_manager.intraday_equity)
        self.stats.summary(display=display_stats)

        if display_plot:
            self.plotting.update_data(self.trade_manager.trade_history, self.trade_manager.intraday_equity)
            self.plotting.overview(display=False)

    def interpret_signal(self, signal, strategy):
        name = strategy.__class__.__name__
        symbol1, symbol2 = strategy.symbol1, strategy.symbol2
        s1, s2 = strategy.s1, strategy.s2
        position_manager = strategy.position_manager
        if position_manager.in_trade():
            leg1, leg2 = position_manager.pairs[-1]
            direction1 = leg1.direction
            direction2 = leg2.direction
            entry_price1 = leg1.entry_price
            entry_price2 = leg2.entry_price
            position_size1 = leg1.position_size
            position_size2 = leg2.position_size
            shares1 = leg1.shares * self.margin
            shares2 = leg2.shares * self.margin

        # --- Enter Long ---
        if signal == 1:
            fill_price1, fill_price2 = entry_price1 * self.slip_up, entry_price2 * self.slip_dn
            leg1.entry_price = fill_price1
            leg2.entry_price = fill_price2
            self.trade_manager.log_entry(name, leg1, symbol1, direction1, position_size1, shares1, self.ts, entry_price1, fill_price1, None, None, strategy.features)
            self.trade_manager.log_entry(name, leg2, symbol2, direction2, position_size2, shares2, self.ts, entry_price2, fill_price2, None, None, strategy.features)
            if self.show_trade:
                print(f"[{self.ts}] | ENTRY (L): {fill_price1}")
                print(f"[{self.ts}] | ENTRY (S): {fill_price2}")

        # --- Enter Short ---
        elif signal == -1:
            fill_price1, fill_price2 = entry_price1 * self.slip_dn, entry_price2 * self.slip_up
            leg1.entry_price = fill_price1
            leg2.entry_price = fill_price2
            self.trade_manager.log_entry(name, leg1, symbol1, direction1, position_size1, shares1, self.ts, entry_price1, fill_price1, None, None, strategy.features)
            self.trade_manager.log_entry(name, leg2, symbol2, direction2, position_size2, shares2, self.ts, entry_price2, fill_price2, None, None, strategy.features)
            if self.show_trade:
                print(f"[{self.ts}] | ENTRY (S): {fill_price1}")
                print(f"[{self.ts}] | ENTRY (L): {fill_price2}")
        
        # --- Exit Position ---
        elif signal == 0:
            shares1, shares2 = position_manager.total_shares()
            if direction1 == 1:
                exit_price1 = (s1["bid"] + s1["ask"]) / 2  # s1["bid"]
                exit_price2 = (s2["bid"] + s2["ask"]) / 2  # s2["ask"]
                fill_price1, fill_price2 = exit_price1 * self.slip_dn, exit_price2 * self.slip_up
            elif direction1 == -1:
                exit_price1 = (s1["bid"] + s1["ask"]) / 2  # s1["ask"]
                exit_price2 = (s2["bid"] + s2["ask"]) / 2  # s2["bid"]
                fill_price1, fill_price2 = exit_price1 * self.slip_up, exit_price2 * self.slip_dn

            for leg1, leg2 in position_manager.pairs.copy():
                entry_price1 = leg1.entry_price
                entry_price2 = leg2.entry_price
                shares1 = leg1.shares * self.margin
                shares2 = leg2.shares * self.margin

                pnl1 = direction1 * (fill_price1 - entry_price1) * shares1
                pnl2 = direction2 * (fill_price2 - entry_price2) * shares2

                self.trade_manager.update_exit(leg1, self.ts, exit_price1, fill_price1)
                self.trade_manager.update_exit(leg2, self.ts, exit_price2, fill_price2)
                self.update_pnl(pnl1)
                self.update_pnl(pnl2)
                position_manager.remove_pair(leg1, leg2)
                if self.show_trade:
                    print(f"[{self.ts}] | EXIT: {fill_price1}, PnL: {pnl1}")
                    print(f"[{self.ts}] | EXIT: {fill_price2}, PnL: {pnl2}")

    def initialize(self, symbol, **params):
        self.strategy = self.strategy_class(symbol, **params)
        self.train_wait = True
        self.cash = self.cash_allocation
        self.strategy.risk_manager.start_cash = self.cash_allocation
        
        self.risk_manager = self.strategy.risk_manager
        self.position_manager = self.strategy.position_manager

        self.trade_manager = TradeManager(live=False)
        self.stats = Stats(symbol)
        self.plotting = Plotting(symbol)

    def dynamic_slippage(self, signal):
        raise NotImplementedError
        self.spread_window.append(abs(self.bid - self.ask))
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

        for leg1, leg2 in self.position_manager.pairs:
            p1 = self.bid1 if leg1.direction > 0 else self.ask1
            p2 = self.bid2 if leg2.direction > 0 else self.ask2
            current_equity += leg1.direction * (p1 - leg1.entry_price) * leg1.shares * self.margin
            current_equity += leg2.direction * (p2 - leg2.entry_price) * leg2.shares * self.margin
                
        self.trade_manager.update_intraday_equity(self.ts, current_equity)
   
    def sort_trade_history(self, trade_history):
        trade_history.sort(key=lambda x: x["entry_time"])
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

    def grid_search(self, pair, df, train, optimize_period=100, rebalance_period=50, target_metric="Net Profit", top_n=5):
        param_grid = self.strategy.param_grid()
        combos = list(product(*param_grid.values()))
        total = len(combos)
        results = []

        best_score = -np.inf
        best_trade_manager = None

        for i, combo in enumerate(combos, 1):
            params = dict(zip(param_grid.keys(), combo))
            self.initialize(pair, **params)
            self.run_simulation(pair, df, train, display_stats=False, display_plot=False)

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

        with open(f"{pair}_{self.strategy.__class__.__name__}_grid_search.json", "w") as f:
            json.dump(results, f, indent=4)