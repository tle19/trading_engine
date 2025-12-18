import time
from datetime import datetime, timedelta

from core import *
from strategies import *
from models import *
from utils import *

def fetch_multiple_symbols(symbols):
    dh = DataHandler()
    for symbol in symbols:
        start_time = time.perf_counter()

        dh.historical_data(symbol)

        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        print(f"Elapsed Data Fetch Time: {elapsed_time:.6f} seconds")

def fetch_schwab_data(symbol, current_date):
    dh = DataHandler()
    dh.schwab_data(symbol, end_date=(datetime.fromisoformat(current_date) - timedelta(days=1)).date().isoformat())

def test_order(symbol):
    eq = Equities(symbol, StochasticIndicator)
    symbol = symbol[0].split(":")[0]

    entry_id = eq.buy_market(symbol, 1, "BUY")
    exit_id = eq.long_bracket(symbol, 1, 333.0, 333.5)
    time.sleep(20)
    fill_price = eq.get_fill_price(exit_id, timeout=0.1)
    print(fill_price)

def get_average_spread(symbols, start_date="2023-10-02", end_date="2024-10-02"):
    for symbol in symbols:
        data = open_data(symbol, start_date=start_date, end_date=end_date)
        data["spread"] = data["high"] - data["low"]
        data["normalized_spread"] = data["spread"] / data["close"]
        avg_spread = data["normalized_spread"].mean()
        print(symbol, avg_spread)

symbols = [
    # ===== INDEX / MACRO =====
    "SPY",   # S&P 500 ETF
    "QQQ",   # Nasdaq-100 ETF
    "IWM",   # Russell 2000 ETF
    "TLT",   # 20+ Year Treasury Bonds ETF
    "BRK.B",  # Berkshire Hathaway

    # ===== TECH =====
    "AAPL",  # Apple
    "MSFT",  # Microsoft
    "NVDA",  # NVIDIA
    "AMD",   # AMD
    "GOOG",  # Alphabet
    "META",  # Meta Platforms
    "ADBE",  # Adobe
    "CRM",   # Salesforce
    "INTC",  # Intel
    "AVGO",  # Broadcom
    "NFLX",  # Netflix

    # ===== CONSUMER =====
    "TSLA",  # Tesla
    "AMZN",  # Amazon
    "HD",    # Home Depot
    "MCD",   # McDonald's
    "NKE",   # Nike
    "SBUX",  # Starbucks
    "COST",  # Costco
    "WMT",   # Walmart
    "PG",    # Procter & Gamble
    "KO",    # Coca-Cola
    "PEP",   # PepsiCo

    # ===== FINANCIALS =====
    "V",     # Visa
    "MA",     # Mastercard
    "JPM",   # JPMorgan Chase
    "GS",    # Goldman Sachs
    "BAC",   # Bank of America
    "MS",    # Morgan Stanley
    "C",     # Citigroup
    "AXP",   # American Express
    "SCHW",  # Charles Schwab
    "WFC",   # Wells Fargo
    "COP",   # Capital One

    # ===== INDUSTRIALS / ENERGY =====
    "XOM",   # ExxonMobil
    "CVX",   # Chevron
    "SLB",   # Schlumberger
    "CAT",   # Caterpillar
    "DE",    # Deere & Co
    "GE",    # General Electric
    "BA",    # Boeing
    "LMT",   # Lockheed Martin
    "RTX",   # RTX
    "HON",   # Honeywell
    "UPS",   # United Parcel Service

    # ===== HEALTHCARE =====
    "UNH",   # UnitedHealth Group
    "LLY",   # Eli Lilly
    "ABBV",  # AbbVie
    "JNJ",   # Johnson & Johnson
    "MRK",   # Merck
    "PFE",   # Pfizer
    "TMO",   # Thermo Fisher Scientific
    "AMGN"  # Amgen
]

# fetch_multiple_symbols(symbols)
# fetch_schwab_data("2025-10-15") 
# get_average_spread(symbols, start_date="2025-8-01", end_date="2025-11-01")
# test_order(["ADBE:1.0"])

mdl = XGBModel(strategy="StochasticIndicator", live=False)
mdl.initialize()
X_train, X_test, y_train, y_test = train_test_split(mdl.df, n_months=18)
mdl.train(X_train, y_train)
mdl.evaluate_classification(X_train, y_train, X_test, y_test)
mdl.save_model(file="xgb_model.pkl")