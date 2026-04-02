from .strategy import Strategy
from .strategy_pair import StrategyPair
from .strategy_book import StrategyBook
from .risk import RiskManager
from .record_quote import RecordQuote
from .record_book import RecordBook
from .example import SMACrossover
from .stochastic import StochasticIndicator
from .orb import ORBIndicator
from .eod_reversion import EODReversion
from .eod_reversion2 import EODReversion2
from .rsi_swing import RSISwing
from .naive import Naive
from .ols import OLS
from .ols_trend import OLSTrend
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
    "EODReversion",
    "EODReversion2",
    "RSISwing",
    "Naive",
    "OLS",
    "OLSTrend",
    "KalmanFilter",
    "strategy_map"
]

strategy_map = {
    "record_quote": RecordQuote,
    "record_book": RecordBook,
    "sma": SMACrossover,
    "stochastic": StochasticIndicator,
    "orb": ORBIndicator,
    "eod_reversion": EODReversion,
    "eod_reversion2": EODReversion2,
    "rsi_swing": RSISwing,
    "naive": Naive,
    "ols": OLS,
    "ols_trend": OLSTrend,
    "kalman": KalmanFilter,
}

