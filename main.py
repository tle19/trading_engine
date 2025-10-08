import argparse
from core import *
from strategies import *

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--strategy", type=str, default="momentum")
    parser.add_argument("--symbol", type=str, default="TSLA")
    args = parser.parse_args()

    strategy_map = {
        "mean": MeanReversionIndicator,
        "momentum": MomentumSMAIndicator,
        "scalp": ScalpIndicator,
        "swing": SwingMAIndicator
    }
    strategy_class = strategy_map.get(args.strategy)
    if strategy_class is None:
        raise ValueError(f"Unknown strategy: {args.strategy}")
    
    if args.live:
        pr = Equities(args.symbol, strategy_class)
        pr.start()
    elif args.backtest:
        bt = Backtest(args.symbol, strategy_class)
        bt.run()
    elif args.fetch:
        dh = DataHandler()
        dh.historical_data(args.symbol)
        # dh.schwab_historical_data(args.symbol)
        # dh.stream_data(args.symbol)
    
if __name__ == "__main__":
    main()