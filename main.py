import argparse
from get_data import DataHandler

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--symbol", type=str, default="TSLA")
    parser.add_argument("--duration", type=int, default=100)
    args = parser.parse_args()

    dh = DataHandler()

    if args.fetch:
        df_hist = dh.historical_data(args.symbol)
    if args.stream:
        df_stream = dh.stream_data(args.symbol, duration=args.duration)
    # if args.backtest:
    #     dh.run_backtest(args.symbol)

if __name__ == "__main__":
    main()
