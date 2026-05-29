from .strategy import Strategy
from .strategy_pair import StrategyPair
from .risk import RiskManager
from .record_quote import RecordQuote
from .example import SMACrossover
from .stochastic import StochasticIndicator
from .orb import ORBIndicator
from .eod_reversion import EODReversion
from .rsi_swing import RSISwing
from .ols import OLS

__all__ = [
    "Strategy",
    "StrategyPair",
    "StrategyBook",
    "RiskManager",
    "RecordQuote",
    "SMACrossover",
    "StochasticIndicator",
    "ORBIndicator",
    "EODReversion",
    "RSISwing",
    "OLS",
    "strategy_map"
]

strategy_map = {
    "record_quote": RecordQuote,
    "sma": SMACrossover,
    "stochastic": StochasticIndicator,
    "orb": ORBIndicator,
    "eod_reversion": EODReversion,
    "rsi_swing": RSISwing,
    "ols": OLS
}

