import argparse
from get_data import DataHandler
from backtest import *
from strategy.mean_reversal import MeanReversionIndicator
from strategy.trend import IntradayTrend
from strategy.scalp import Scalp
from run_program import Equities

def main():

    strategy_map = {
        "mean": MeanReversionIndicator,
        "trend": IntradayTrend,
        "scalp": Scalp
    }

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--strategy", type=str, default="mean")
    parser.add_argument("--symbol", type=str, default="GOOG")
    parser.add_argument("--duration", type=int, default=300)
    args = parser.parse_args()

    strategy_class = strategy_map.get(args.strategy)
    if strategy_class is None:
        raise ValueError(f"Unknown strategy: {args.strategy}")
    
    dh = DataHandler()
    
    if args.start:
        pr = Equities(args.symbol, strategy_class)
        pr.start()
    elif args.fetch:
        dh.historical_data(args.symbol)
        # dh.schwab_historical_data(args.symbol)
    elif args.stream:
        dh.stream_data(args.symbol, duration=args.duration)
    elif args.backtest:
        run_backtest(strategy_class, args.symbol, dh)
        # grid_search_trend(strategy_class, args.symbol, dh)
        # grid_search_scalp(strategy_class, args.symbol, DataHandler)
        # grid_search_mean_reversion(strategy_class, args.symbol, DataHandler)

if __name__ == "__main__":
    main()
