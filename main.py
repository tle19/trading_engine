import argparse
from get_data import DataHandler
from backtest import run_backtest
from strategy.mean_reversal import MeanReversionIndicator
from strategy.momentum import Momentum


def main():

    strategy_map = {
        "trend_follow": Momentum,
        "mean_reversal": MeanReversionIndicator
    }

    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--strategy", type=str, default="Momentum")
    parser.add_argument("--symbol", type=str, default="TSLA")
    parser.add_argument("--duration", type=int, default=300)
    args = parser.parse_args()

    dh = DataHandler()

    if args.fetch:
        dh.polygon_historical_data(args.symbol)
        # dh.historical_data(args.symbol)
        return
    if args.stream:
        dh.stream_data(args.symbol, duration=args.duration)
        return
    if args.backtest:
        strategy_class = strategy_map.get(args.strategy)
        if strategy_class is None:
            raise ValueError(f"Unknown strategy: {args.strategy}")
        run_backtest(strategy_class, args.symbol, dh)
        return

if __name__ == "__main__":
    main()
