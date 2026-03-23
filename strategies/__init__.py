from .strategy import Strategy
from .strategy_pair import StrategyPair
from .strategy_book import StrategyBook
from .risk import RiskManager
from .example import SMACrossover
from .stochastic import StochasticIndicator
from .orb import ORBIndicator
from .rsi_scalp import RSIScalp
from .record_book import RecordBook
from .record_quote import RecordQuote
from .rsi_swing import RSISwing
from .eod_reversion import EODReversion
from .eod_reversion2 import EODReversion2
from .ratio_ema import RatioEMA

__all__ = [
    "Strategy",
    "StrategyPair",
    "StrategyBook",
    "RiskManager",
    "SMACrossover",
    "StochasticIndicator",
    "ORBIndicator",
    "RSIScalp",
    "RSISwing",
    "EODReversion",
    "EODReversion2",
    "RatioEMA",
    "RecordBook",
    "RecordQuote",
    "strategy_map"
]

strategy_map = {
    "sma": SMACrossover,
    "stochastic": StochasticIndicator,
    "orb": ORBIndicator,
    "rsi": RSIScalp,
    "rsi_swing": RSISwing,
    "eod_reversion": EODReversion,
    "eod_reversion2": EODReversion2,
    "ratio_ema": RatioEMA,
    "record_book": RecordBook,
    "record_quote": RecordQuote
}

