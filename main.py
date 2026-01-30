import argparse
from datetime import date, datetime, timedelta

from symbols import SYMBOLS
from core import *
from utils import *
from strategies import strategy_map

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--quote", action="store_true")

    parser.add_argument("--schwab", action="store_true")
    parser.add_argument("--grid", action="store_true")
    parser.add_argument("--train", action="store_true")

    parser.add_argument("--strategy", nargs="+", type=str, default=None, help="'eod_reversion stochastic' or 'eod_reversion:SPY spread_diff:SPY-QQQ'")
    parser.add_argument("--symbol", nargs="+", type=str, default=None, help="QQQ AAPL MSFT")
    parser.add_argument("--pair", nargs="+", type=str, default=None, help="SPY-QQQ GOOG-GOOGL")
    
    parser.add_argument("--cash", type=int, default=25000)
    parser.add_argument("--margin", type=float, default=1.0)
    parser.add_argument("--commission", type=float, default=0.0)
    parser.add_argument("--slippage", type=float, default=0.1)
    args = parser.parse_args()
    
    if not args.strategy and not args.fetch and not args.stream and not args.quote:
        raise ValueError(f"You must provide a strategy, e.g., --strategy eod_reversion or eod_reversion:AAPL or spread_diff:SPY-QQQ")
    colon_used = any(":" in s for s in args.strategy) if args.strategy else None
    if colon_used and (args.symbol or args.pair):
        raise ValueError("Cannot mix colon syntax with --symbol or --pair arguments")
    if not colon_used and not args.symbol and not args.pair:
        raise ValueError("Either use colon syntax in --strategy or provide --symbol / --pair")
    if args.symbol == "EVERYTHING":
        args.symbol = SYMBOLS

    strategy_dict = {}
    symbols = []
    if colon_used:
        for item in args.strategy:
            name, sym_str = item.split(":", 1)
            symbols_or_pairs = sym_str.split(",") if sym_str else []
            cls = strategy_map[name]
            strategy_dict[cls] = symbols_or_pairs
            for entry in symbols_or_pairs:
                if "-" in entry:  
                    a, b = entry.split("-")
                    symbols.extend([a, b])
                else:
                    symbols.append(entry)
        args.strategy = list(strategy_dict)[0] 
        args.symbol = strategy_dict[args.strategy][0]
        args.pair = strategy_dict[args.strategy][0]
    elif args.strategy:
        args.strategy = strategy_map[args.strategy[0]]
        symbols = args.symbol or args.pair

    dh = DataHandler()
    timezone = ZoneInfo("America/New_York")

    if args.live:
        now = datetime.now(timezone)
        data_filled = (now + timedelta(days=1)).replace(hour=1, minute=0, second=0, microsecond=0)
        if now < data_filled:
            wait_seconds = int((data_filled - now).total_seconds())
            hours, rem = divmod(wait_seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            print(f"[WAIT] Data not ready. Time remaining: {hours}h {minutes}m {seconds}s")
            time.sleep(wait_seconds)
        dh.historical_data(symbols)

        if strategy_dict:
            dfc = DataFeedController(strategy_dict, margin=args.margin)
            dfc.run()
        elif args.symbol:
            eq = Equities(args.symbol, args.strategy, margin=args.margin) # single strategy
            eq.run()
        elif args.pair:
            ep = EquityPairs(args.pair, args.strategy, margin=args.margin) # single strategy
            ep.run()
    elif args.backtest:
        bt = Backtest(args.symbol, args.strategy, cash=args.cash, margin=args.margin, commission=args.commission, slippage=args.slippage) # single strategy
        bt.run(end_date=str(date.today()), train=args.train, grid=args.grid)
    elif args.fetch:
        if args.schwab:
            dh.schwab_data(args.symbol)
        else:
            dh.historical_data(args.symbol)
    elif args.stream:
        dh.stream_data(args.symbol)
    elif args.quote:
        dh.get_quote(args.symbol)
    else:
        raise ValueError(
            "You must provide one of the following arguments: --live, --backtest, --fetch, --stream"
        )
    
if __name__ == "__main__":
    main()