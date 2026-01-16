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
    parser.add_argument("--symbol", nargs="+", type=str, default=None, help="AAPL MSFT TSLA")
    parser.add_argument("--margin", type=float, default=1.0)
    args = parser.parse_args()

    strategy_class = strategy_map.get(args.strategy)
    if strategy_class is None:
        raise ValueError(f"Unknown Strategy: {args.strategy}")

    if args.live:
        eq = Equities(args.symbol, strategy_class, margin=args.margin)
        eq.run()
    elif args.backtest:
        bt = Backtest(args.symbol, strategy_class, margin=args.margin)
        bt.run()
    elif args.fetch:
        dh = DataHandler()
        dh.historical_data(args.symbol[0], from_date='2024-01-01', to_date='2026-01-01')
        if args.schwab:
            current_date = datetime.now().date()
            dh.schwab_data(args.symbol[0], end_date=(datetime.fromisoformat(current_date) - timedelta(days=1)).date().isoformat())
    elif args.stream:
        dh = DataHandler()
        dh.stream_data(args.symbol[0])
    
if __name__ == "__main__":
    main()