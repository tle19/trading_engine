import argparse
from get_data import DataHandler
from backtest import run_backtest, grid_search_trend, grid_search_scalp
from strategy.mean_reversal import MeanReversionIndicator
from strategy.scalp import Scalp
from strategy.trend import IntradayTrend
from run_program import Program

def main():

    strategy_map = {
        "trend": IntradayTrend,
        "scalp": Scalp,
        "mean_reversion": MeanReversionIndicator
    }

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--strategy", type=str, default="trend")
    parser.add_argument("--symbol", type=str, default="TSLA")
    parser.add_argument("--duration", type=int, default=300)
    args = parser.parse_args()

    strategy_class = strategy_map.get(args.strategy)
    if strategy_class is None:
        raise ValueError(f"Unknown strategy: {args.strategy}")
    
    dh = DataHandler()
    
    if args.start:
        pr = Program(args.symbol, strategy_class)
        pr.start_equity()
        # pr.start_forex()
        return
    if args.fetch:
        dh.polygon_historical_data(args.symbol)
        # dh.historical_data(args.symbol)
        return
    if args.stream:
        dh.stream_data(args.symbol, duration=args.duration)
        return
    if args.backtest:
        run_backtest(strategy_class, args.symbol, dh)
        # grid_search_trend(strategy_class, args.symbol, dh)
        # grid_search_scalp(strategy_class, args.symbol, dh)
        return

if __name__ == "__main__":
    main()
