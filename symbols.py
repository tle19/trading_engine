SP500 = [
    # ===== Information Technology =====
    "AAPL", "MSFT", "NVDA", "ADBE", "CRM", "ORCL", "CSCO", "ACN", "IBM",
    "TXN", "AVGO", "QCOM", "AMD", "NOW", "ADSK", "ANSS", "CTSH", "CDNS",
    "INTU", "PAYX", "VRSN", "PYPL", "ANET", "SNOW", "FTNT", "V", "MA", "FIS",
    "FISV", "INTC", "BLK", "SCHW",

    # ===== Financials =====
    "JPM", "BAC", "BRK.B", "C", "MS", "GS", "AXP", "PNC", "WFC", "USB",
    "COF", "TFC", "BK", "AIG", "MMC", "ICE", "CME", "MSCI", "SPGI", "SCHW",
    "BLK", "ICE", "CME",

    # ===== Health Care =====
    "UNH", "JNJ", "PFE", "MRK", "LLY", "ABT", "AMGN", "MDT", "DHR", "BMY",
    "ISRG", "CI", "HCA", "ZTS", "SYK", "BDX", "EW", "DGX", "ABC", "PKI",

    # ===== Consumer Discretionary =====
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "BKNG", "TJX",
    "ROST", "LVS", "CCL", "DAL", "MAR", "SYY", "LEG", "DG", "CMG", "DHI",

    # ===== Communication Services =====
    "GOOGL", "GOOG", "META", "NFLX", "VZ", "T", "DIS", "CMCSA", "ATVI",
    "EA", "TGT", "FTNT",

    # ===== Industrials =====
    "BA", "CAT", "DE", "UPS", "EMR", "HON", "GD", "LMT", "RTX", "PCAR",
    "CSX", "NSC", "EXPD", "FDX", "ROK", "ITW", "NOC", "WM", "PNR", "ETN",
    "MLM", "AAL",

    # ===== Consumer Staples =====
    "PG", "KO", "PEP", "WMT", "COST", "MO", "EL", "CL", "KMB", "SJM",

    # ===== Energy =====
    "XOM", "CVX", "COP", "SLB", "OXY", "MPC", "PSX", "VLO", "EOG", "DVN",

    # ===== Utilities =====
    "NEE", "DUK", "SO", "EXC", "DTE", "AEP", "PNW", "PPL", "SRE", "ES",

    # ===== Materials =====
    "LIN", "DD", "ECL", "PPG", "LYB", "NEM", "APD", "CF", "SEE", "WRK",

    # ===== Real Estate =====
    "AMT", "PLD", "SPG", "EQIX", "PSA", "O", "DRE", "WELL", "DLR", "CBRE",
]

PAIRS = [
    # Broad Market Index ETFs
    ["SPY", "QQQ"],   # S&P 500 ETF vs Nasdaq-100 ETF (Large-Cap / Tech-Heavy)
    ["VOO", "SCHX"],  # S&P 500 ETF vs Schwab 750 ETF (Large-Cap)
    ["IVV", "IWM"],   # S&P 500 ETF vs Russell 2000 ETF (Small-Cap)

    # Sector / Thematic ETFs
    ["XLV", "XBI"],   # Healthcare ETF vs Biotech ETF

    # Precious Metals
    ["GLD", "SLV"],   # Gold ETF vs Silver ETF
]

CRYPTO = [
    "IBIT",   # Bitcoin-based ETF
    "ETHA",   # Ethereum-based ETF
    "FBTC",   # Fidelity Bitcoin ETF
    "FETH"    # Fidelity Ethereum ETF
]

EXTRA = [
    "DIA",    # Dow Jones Industrial Average ETF
    "QQQM",   # Nasdaq-100 ETF (smaller version, lower AUM)
    "XLK",    # Technology Sector ETF
    "XLI",    # Industrials Sector ETF
    "XLE"     # Energy Sector ETF
]