# multiple symbol fetch
from core import DataHandler
symbols = ["SPY", "QQQ", "TSLA", "NVDA", "AMD", "AMZN", "AAPL", 
           "GOOG", "MSFT", "META", "TSM", "CSCO", "INTC", "ADBE"]
dh = DataHandler()
for symbol in symbols:
    dh.historical_data(symbol)

# direct script for running multiple data/backtest/strategies
# walk forward optimization / OOS