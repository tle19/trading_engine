import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

from core import *
from strategies import *
from models import *
from utils import *

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
    "COF",   # Capital One

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

def fetch_multiple_symbols(symbols):
    dh = DataHandler()
    for symbol in symbols:
        start_time = time.perf_counter()

        dh.historical_data(symbol=symbol, from_date='2024-01-01', to_date='2026-01-05')

        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        print(f"Elapsed Data Fetch Time: {elapsed_time:.6f} seconds")

def test_order(symbol="[AAPL]"):
    eq = Equities(symbol, StochasticIndicator)
    symbol = symbol[0]

    entry_id, _ = eq.buy_market(symbol, 1, "BUY")
    exit_id = eq.long_bracket(symbol, 1, 333.0, 333.5)
    time.sleep(20)
    fill_price = eq.get_fill_price(exit_id, timeout=0.1)
    print(fill_price)


# symbol = "META"
# mdl = XGBModel(symbol=symbol, strategy="StochasticIndicator", live=False)
# # mdl = RFModel(symbol=symbol, strategy="StochasticIndicator", live=False)
# # mdl = KNNModel(symbol=symbol, strategy="StochasticIndicator", live=False)
# mdl.initialize()
# X_train, X_test, y_train, y_test = train_test_split(mdl.df, n_months=18)
# mdl.train(X_train, y_train)
# mdl.evaluate_classification(X_train, y_train, X_test, y_test)
# # mdl.save_model()


# window = 50
# df = open_data(
#     "TSLA", start_date="2025-11-18", end_date="2025-11-18", start_time="10:30", end_time="16:00")
# df["ema"] = df["close"].ewm(span=window, adjust=False).mean()
# df["close_minus_ema_pct"] = (df["close"] - df["ema"]) / df["ema"]
# print(df)

# x = df["close_minus_ema_pct"].dropna()
# lo, hi = x.quantile([0.001, 0.999])
# x_clip = x.clip(lo, hi)
# mu = x.mean()
# sigma = x.std()
# plt.figure(figsize=(10, 6))
# plt.hist(x_clip, bins=100, color="lightgray", edgecolor="black")
# plt.axvspan(mu - sigma,   mu + sigma,   color="green",  alpha=0.25, label="68% (±1σ)")
# plt.axvspan(mu - 2*sigma, mu + 2*sigma, color="yellow", alpha=0.20, label="95% (±2σ)")
# plt.axvspan(mu - 3*sigma, mu + 3*sigma, color="red",    alpha=0.15, label="99.7% (±3σ)")
# plt.axvline(mu, color="black", linewidth=2, label="Mean")
# plt.axvline(0, color="blue", linestyle="--", label="Zero")
# plt.title("Close Relative to EMA (1–99% clipped)")
# plt.xlabel("(Close - EMA) / EMA")
# plt.ylabel("Frequency")
# plt.legend()
# plt.show()

# P (price will pull back towards mean | slope is steady)
# P (price will pull back towards mean | slope is trending)