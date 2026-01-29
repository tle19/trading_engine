import argparse
from datetime import date

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

    parser.add_argument("--strategy", type=str, default="eod_reversion")
    parser.add_argument("--symbol", nargs="+", type=str, default=None, help="QQQ AAPL MSFT")
    parser.add_argument("--pair", nargs="+", type=str, default=None, help="SPY-QQQ GOOG-GOOGL")
    
    parser.add_argument("--cash", type=int, default=25000)
    parser.add_argument("--margin", type=float, default=1.0)
    parser.add_argument("--commission", type=float, default=0.0)
    parser.add_argument("--slippage", type=float, default=0.1)
    args = parser.parse_args()
    
    strategy_class = strategy_map.get(args.strategy)
    if strategy_class is None:
        raise ValueError(f"Unknown Strategy: {args.strategy}")
    if args.symbol is None and args.pair is None:
        raise ValueError(f"You must provide a symbol/pair, e.g., --symbol SPY and/or --pair SPY-QQQ")
    if args.symbol == "EVERYTHING":
        args.symbol = SYMBOLS
    
    if args.live:
        # dh = DataHandler()
        # dh.historical_data(symbols)
        if args.pair:
            ep = EquityPairs(args.pair, strategy_class, margin=args.margin)
            ep.run()
        else:
            eq = Equities(args.symbol, strategy_class, margin=args.margin)
            eq.run()
    elif args.backtest:
        bt = Backtest(args.symbol, strategy_class, cash=args.cash, margin=args.margin, commission=args.commission, slippage=args.slippage)
        bt.run(end_date=str(date.today()), train=args.train, grid=args.grid)
    elif args.fetch:
        dh = DataHandler()
        if args.schwab:
            dh.schwab_data(args.symbol)
        else:
            dh.historical_data(args.symbol)
    elif args.stream:
        dh = DataHandler()
        dh.stream_data(args.symbol)
    elif args.quote:
        dh = DataHandler()
        dh.get_quote(args.symbol)
    else:
        raise ValueError(
            "You must provide one of the following arguments: --live, --backtest, --fetch, --stream"
        )
    
if __name__ == "__main__":
    main()