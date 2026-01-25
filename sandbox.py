import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from core import *
from metrics import *
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
symbols = ["QQQ", "AAPL", "MSFT", "META", "CRM", "ABBV", "CVX", "MRK", "UPS", "AXP", "CAT"]

def test_order(symbol="AAPL"):
    eq = Equities(symbol, StochasticIndicator)
    symbol = symbol[0]

    entry_id, _ = eq.buy_market(symbol, 1, "BUY")
    exit_id = eq.long_bracket(symbol, 1, 333.0, 333.5)
    time.sleep(20)
    fill_price = eq.get_fill_price(exit_id, timeout=0.1)
    print(fill_price)

def train_model(symbol="META", train_period=100, test_period=50, grid=False):
    trade_manager = TradeManager(live=True)
    trade_history = trade_manager.trade_history

    curr_date = pd.Timestamp.utcnow().normalize()
    start_date = curr_date - pd.DateOffset(days=train_period + test_period)
    trade_manager.trade_history = [
            trade for trade in trade_history
            if start_date < pd.to_datetime(trade["entry_time"], utc=True).normalize() < curr_date
       ]
    trade_manager.save_logs()

    mdl = XGBModel(symbol=symbol, strategy="EODReversion", live=False)
    # mdl = RFModel(symbol=symbol, strategy="StochasticIndicator", live=False)
    # mdl = KNNModel(symbol=symbol, strategy="StochasticIndicator", live=False)
    mdl.initialize()
    X_train, X_test, y_train, y_test = train_test_split(mdl.df, n_days=train_period)
    if grid:
        mdl.grid_search(X_train, X_test, y_train, y_test)
    else:
        mdl.train(X_train, y_train)
    mdl.evaluate_classification(X_train, X_test, y_train, y_test)
    # mdl.save_model()

    trade_manager.trade_history = trade_history
    trade_manager.save_logs()

def plot_diist(df, col):
    x = df[col].dropna()
    lo, hi = x.quantile([0.001, 0.999])
    x_clip = x.clip(lo, hi)
    mu = x.mean()
    sigma = x.std()
    print(f"±1σ: {round(mu + sigma, 5)}")
    print(f"±2σ: {round(mu + 2*sigma, 5)}")
    print(f"±3σ: {round(mu + 3*sigma, 5)}")
    plt.figure(figsize=(10, 6))
    plt.hist(x_clip, bins=100, color="lightgray", edgecolor="black")
    plt.axvspan(mu - sigma,   mu + sigma,   color="green",  alpha=0.15, label="68% (±1σ)")
    plt.axvspan(mu - 2*sigma, mu + 2*sigma, color="yellow", alpha=0.15, label="95% (±2σ)")
    plt.axvspan(mu - 3*sigma, mu + 3*sigma, color="red",    alpha=0.15, label="99.7% (±3σ)")
    plt.axvline(mu, color="blue", linestyle="--", linewidth=2, label="Mean")
    plt.title(f"{col} (0.1-99.9% clipped)")
    plt.xlabel(col)
    plt.ylabel("Frequency")
    plt.legend()
    plt.show()

def find_proba(df):
    wins = 0
    losses = 0

    target = 0
    stop = 0
    for i, entry_cond in enumerate(df["entry_cond"]):
        if not entry_cond:
            continue
        if df["straddle_up"]:
            direction = 1
        elif df["straddle_down"]:
            direction = -1
        # find timestamp
        # set target to ema +/- abs(ema_straddle_target)
        # set stop to ema +/- abs(target - ema) / 2
        for j in range(i + 1, len(df)):
            high = df.loc[j, "high"]
            low = df.loc[j, "low"]

            if high >= target:
                wins += 1
                break
            elif low <= stop:
                losses += 1
                break

            if df.loc["timestamp"] == 15.59:
                break

# ema_window = 50
# lookback = 15
# df = open_data("GOOG", start_date="2024-01-01", end_date="2026-01-01", start_time="10:00", end_time="15:59")
# df["ema"] = df["close"].ewm(span=ema_window, adjust=False).mean()
# df["straddle_up"] = (df["close"] > df["ema"]) & (df["open"] < df["ema"])
# df["straddle_down"] = (df["close"] < df["ema"]) & (df["open"] > df["ema"])
# df["ema_max_last5_pct"] = (df["high"].rolling(lookback, min_periods=1).max() - df["ema"]) / df["ema"]
# df["ema_min_last5_pct"] = (df["low"].rolling(lookback, min_periods=1).min() - df["ema"]) / df["ema"]
# df["ema_straddle_target"] = np.where(df["straddle_up"], df["ema_min_last5_pct"],
#     np.where(df["straddle_down"], df["ema_max_last5_pct"], np.nan)
# )

# col = "ema_straddle_target"
# x = df[col].dropna()
# mu = x.mean()
# sigma = x.std()
# df["entry_cond"] = (df[col] >= mu - 2*sigma) | (df[col] <= mu + 2*sigma)

# plot_dist(df, "ema_straddle_target")

train_model(symbol="AAPL", train_period=450, test_period=300, grid=True)