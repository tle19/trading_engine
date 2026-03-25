from .strategy import Strategy
from .strategy_pair import StrategyPair
from .strategy_book import StrategyBook
from .risk import RiskManager
from .record_quote import RecordQuote
from .record_book import RecordBook
from .example import SMACrossover
from .stochastic import StochasticIndicator
from .orb import ORBIndicator
from .rsi_swing import RSISwing
from .eod_reversion import EODReversion
from .eod_reversion2 import EODReversion2
from .ratio_ema import RatioEMA
from .ratio_ema2 import RatioEMA2
from .ols import OLS
from .kalman import KalmanFilter

__all__ = [
    "Strategy",
    "StrategyPair",
    "StrategyBook",
    "RiskManager",
    "RecordQuote",
    "RecordBook",
    "SMACrossover",
    "StochasticIndicator",
    "ORBIndicator",
    "RSISwing",
    "EODReversion",
    "EODReversion2",
    "RatioEMA",
    "RatioEMA2",
    "OLS",
    "KalmanFilter",
    "strategy_map"
]

strategy_map = {
    "record_quote": RecordQuote,
    "record_book": RecordBook,
    "sma": SMACrossover,
    "stochastic": StochasticIndicator,
    "orb": ORBIndicator,
    "rsi_swing": RSISwing,
    "eod_reversion": EODReversion,
    "eod_reversion2": EODReversion2,
    "ratio_ema": RatioEMA,
    "ratio_ema2": RatioEMA2,
    "ols": OLS,
    "kalman": KalmanFilter,
}

