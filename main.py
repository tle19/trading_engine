import argparse
from core import *
from utils import *
from strategies import strategy_map

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--allocate", action="store_true")
    parser.add_argument("--strategy", type=str, default="sma")
    parser.add_argument("--symbol", type=str, default="MSFT")
    parser.add_argument("--symbols", nargs="+", type=str, default=["MSFT:1.0","GOOG:0.75","META:0.5"])
    args = parser.parse_args()

    strategy_class = strategy_map.get(args.strategy)
    if strategy_class is None:
        raise ValueError(f"Unknown Strategy: {args.strategy}")
    
    if args.live:
        strat = strategy_class(args.symbol)
        eq = Equities(args.symbol, strat)
        eq.run()
    elif args.backtest:
        strat = strategy_class(args.symbol)
        bt = Backtest(args.symbol, strat)
        bt.run()
    elif args.fetch:
        dh = DataHandler()
        # dh.historical_data(args.symbol, from_date='2023-11-01', to_date='2025-11-01')
        # dh.schwab_data(args.symbol)
        dh.stream_data(args.symbol)
    elif args.allocate:
        allocate_positions(args.symbols)
    
if __name__ == "__main__":
    main()