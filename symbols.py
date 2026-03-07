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
    # Broad Market vs Tech
    ["SPY", "QQQ"],   # S&P 500 ETF vs Nasdaq-100 ETF

    # Precious Metals
    ["GLD", "SLV"],   # Gold ETF vs Silver ETF

    # Energy Sector
    ["XLE", "VDE"],   # Energy Select Sector SPDR vs Vanguard Energy ETF

    # Crypto ETPs
    ["IBIT", "ETHA"], # Bitcoin ETP vs Ethereum ETP
]