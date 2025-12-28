import argparse
from datetime import datetime, timedelta
from core import *
from utils import *
from strategies import strategy_map

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--schwab", action="store_true")
    parser.add_argument("--strategy", type=str, default="stochastic")
    parser.add_argument("--symbol", type=str, default=None, help="AAPL")
    parser.add_argument("--symbols", nargs="+", type=str, default=None, help="AAPL MSFT TSLA")
    parser.add_argument("--margin", type=float, default=1.0)
    args = parser.parse_args()

    strategy_class = strategy_map.get(args.strategy)
    if strategy_class is None:
        raise ValueError(f"Unknown Strategy: {args.strategy}")
    if args.symbol:
        args.symbols = [args.symbol]

    if args.live:
        eq = Equities(args.symbols, strategy_class, margin=args.margin)
        eq.run()
    elif args.backtest:
        strat = strategy_class(args.symbol)
        bt = Backtest(args.symbol, strat, margin=args.margin)
        bt.run(plot=True, save_plot=False)
    elif args.fetch:
        dh = DataHandler()
        dh.historical_data(args.symbol, from_date='2023-12-01', to_date='2025-12-01')
        if args.schwab:
            current_date = datetime.now().date()
            dh.schwab_data(args.symbol, end_date=(datetime.fromisoformat(current_date) - timedelta(days=1)).date().isoformat())
    elif args.stream:
        dh = DataHandler()
        dh.stream_data(args.symbol)
    
if __name__ == "__main__":
    main()