import os
import argparse
import shutil
import time
from datetime import date, datetime, timedelta

from symbols import *
from core import *
from metrics import *
from utils import *
from strategies import strategy_map

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--quote", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--sync", action="store_true")

    parser.add_argument("--strategy", nargs="+", type=str, default=None, help="'eod_reversion stochastic' or 'eod_reversion:SPY spread_diff:SPY-QQQ'")
    parser.add_argument("--symbols", nargs="+", type=str, default=None, help="'QQQ AAPL MSFT' or 'SPY-QQQ GOOG-GOOGL'")

    parser.add_argument("--daily", action="store_true")

    parser.add_argument("--start_date", type=str, default="2007-1-01")
    parser.add_argument("--end_date", type=str, default=str(date.today()))
    parser.add_argument("--grid", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--show_trade", action="store_true")
    parser.add_argument("--cash", type=int, default=25000)
    parser.add_argument("--margin", type=float, default=1.0)
    parser.add_argument("--commission", type=float, default=0.0)
    parser.add_argument("--slippage", type=float, default=0.1)

    parser.add_argument("--service", type=str, default="level1")
    parser.add_argument("--duration", type=int, default=300)

    parser.add_argument("--file", type=str, default="trade_logs.json")
    args = parser.parse_args()

    if not args.live and not args.backtest and not args.fetch and not args.stream and not args.quote and not args.stats and not args.backup and not args.sync:
        raise ValueError("You must provide one of the following arguments: --live, --backtest, --fetch, --stream, --quote, --stats, --backup, --sync")
    if not args.strategy and (args.live or args.backtest):
        raise ValueError(f"You must provide a strategy, e.g., --strategy eod_reversion or eod_reversion:AAPL,MSFT or spread_diff:SPY-QQQ,GOOG-GOOGL")
    colon_used = any(":" in s for s in args.strategy) if args.strategy else None
    if colon_used and args.symbols:
        raise ValueError("Cannot mix colon syntax with --symbol arguments")
    if not colon_used and not args.symbols and not args.stats and not args.backup and not args.sync:
        raise ValueError("Either use colon syntax in --strategy or provide --symbol")
    if args.symbols and len(args.symbols) == 1 and args.symbols[0] in SYMBOL_MAP:
        args.symbols = SYMBOL_MAP[args.symbols[0]]

    strategy_dict = {}
    symbols = args.symbols if args.symbols else []
    if colon_used:
        for item in args.strategy:
            name, sym_str = item.split(":", 1)
            syms = sym_str.split(",")
            strategy_dict[strategy_map[name]] = syms
            for sym in syms:
                if "-" in sym:  
                    a, b = sym.split("-")
                    symbols.extend([a, b])
                else:
                    symbols.append(sym)
        args.strategy = list(strategy_dict)[0] 
        args.symbols = strategy_dict[args.strategy]
    if args.strategy and not strategy_dict:
        args.strategy = strategy_map[args.strategy[0]]
        strategy_dict[args.strategy] = symbols

    dh = DataHandler()

    if args.live:
        now = datetime.datetime.now(ZoneInfo("America/New_York"))
        market_close = now.replace(hour=20, minute=0, second=0, microsecond=0)
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=15, second=0, microsecond=0)
        target = midnight if market_close <= now < midnight else None
        if target:
            wait_seconds = int((target - now).total_seconds())
            hours, rem = divmod(wait_seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            print(f"[WAIT] Data not ready. Time remaining: {hours}h {minutes}m {seconds}s")
            time.sleep(wait_seconds)
        dh.intraday_data(symbols)
        del dh

        dfc = DataFeedController(strategy_dict, margin=args.margin)
        dfc.run()
    elif args.backtest:
        pairs = True if "-" in args.symbols[0] else False
        bt = create_backtest(args.symbols, args.strategy, pairs=pairs, cash=args.cash, margin=args.margin, commission=args.commission, slippage=args.slippage)
        bt.run(start_date=args.start_date, end_date=args.end_date, grid=args.grid, train=args.train, show_trade=args.show_trade)
    elif args.fetch:
        if args.daily:
            dh.daily_data(args.symbols)
        else:
            dh.intraday_data(args.symbols)
    elif args.stream:
        dh.stream_data(args.symbols, args.service, args.duration)
    elif args.quote:
        dh.get_quote(args.symbols)
    elif args.stats:
        trade_manager = TradeManager(log_file=args.file, live=True)
        trade_manager.load_logs()
        trade_history = [
            t for t in trade_manager.trade_history
            if (
                args.start_date <= t["entry_time"].split("T")[0] <= args.end_date
                and (not symbols or t["symbol"] in symbols)
            )
        ]
        intraday_equity = {
            ts: v
            for ts, v in trade_manager.intraday_equity.items()
            if args.start_date <= ts.split("T")[0] <= args.end_date
        }
        stats = Stats("AGGREGATE")
        plotting = Plotting("AGGREGATE")
        stats.update_data(trade_history, intraday_equity)
        plotting.update_data(trade_history, intraday_equity)
        stats.summary()
        plotting.overview()
    elif args.backup or args.sync:
        if args.backup:
            source = "data"
            destination = "/mnt/d/market data"
        elif args.sync:
            source = "/mnt/d/market data"
            destination = "data"

        for folder in os.listdir(source):
            src_folder = os.path.join(source, folder)
            if not os.path.isdir(src_folder):
                continue

            for file in os.listdir(src_folder):          
                dest_folder = os.path.join(destination, folder)
                os.makedirs(dest_folder, exist_ok=True)
                shutil.copyfile(os.path.join(src_folder, file), os.path.join(dest_folder, file))
                print(f"Copied {os.path.join(src_folder, file)} → {dest_folder}")

if __name__ == "__main__":
    main()