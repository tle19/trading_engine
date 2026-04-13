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

MACRO = [
    "SPY",    # S&P 500 ETF
    "IVV",    # S&P 500 ETF
    "VOO",    # S&P 500 ETF
    "DIA",    # Dow Jones 30 ETF
    "QQQ",    # Nasdaq 100 ETF
    "QQQM",   # Nasdaq 100 ETF
    "SCHX",   # Schwab 750 ETF
    "IWM",    # Russell 2000 ETF
    "VTI",    # Total US Market ETF
    "ITOT",   # Total US Market ETF
    "VXUS",   # Total International Market ETF
    "IXUS",   # Total International Market ETF
    "VT",     # Total World Market ETF
    "TLT"     # 20+ Year Treasury Bond ETF
]

SECTORS = [
    "XLK",    # Technology ETF
    "XLF",    # Financials ETF
    "XLI",    # Industrials ETF
    "XLE",    # Energy ETF
    "XLV",    # Healthcare ETF
    "XBI",    # Biotech ETF
    "XLY",    # Consumer Discretionary ETF
    "XLP"     # Consumer Staples ETF
]

PRECIOUS_METALS = [
    "GLD",    # Gold ETF
    "IAU",    # Gold ETF
    "SLV",    # Silver ETF
    "SIVR",   # Silver ETF
    "PALL",   # Palladium ETF
    "PLTM"    # Platinum ETF
]

ENERGY = [
    "XLE",   # Energy ETF
    "XOP",   # Oil & Gas ETF
    "USO",   # WTI Oil ETF
    "BNO",   # Brent Oil ETF
    "UNG",   # Natural Gas ETF
]

AGRICULTURE = [
    "DBA",   # Agriculture ETF
    "WEAT",  # Wheat ETF
    "CORN"   # Corn ETF
]

COMMODITIES = [
    "PDBC",   # Commodity ETF
    "DBC",    # Commodity ETF
    "GSG"     # Commodity ETF
]

CRYPTO = [
    "IBIT",   # Bitcoin ETF
    "FBTC",   # Bitcoin ETF
    "ETHA",   # Ethereum ETF
    "FETH"    # Ethereum ETF
]

SYMBOL_MAP = {
    "SP500": SP500,
    "MACRO": MACRO,
    "SECTORS": SECTORS,
    "ENERGY": ENERGY,
    "COMMODITIES": COMMODITIES,
    "PRECIOUS_METALS": PRECIOUS_METALS,
    "CRYPTO": CRYPTO
}

PAIRS = [
    ["SPY", "QQQ"],   # S&P 500 vs Nasdaq 100 (Broad vs Tech)
    ["IVV", "IWM"],   # S&P 500 vs Russell 2000 (Large vs Small)
    ["VT", "VXUS"],   # Total World vs Ex-US International (Global vs Ex-US International)
    ["GLD", "SLV"],   # Gold vs Silver (Precious Metals)
    ["IAU", "SIVR"],  # Gold vs Silver (Precious Metals)
    ["USO", "BNO"],   # WTI vs Brent (Crude Oils)
]