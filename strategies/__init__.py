from .strategy import Strategy
from .strategy_pair import StrategyPair
from .strategy_book import StrategyBook
from .risk import RiskManager
from .example import SMACrossover
from .stochastic import StochasticIndicator
from .orb import ORBIndicator
from .volume_decay import VolumeDecay
from .rsi_scalp import RSIScalp
from .record_book import RecordBook
from .div_arb import DivArb
from .rsi_swing import RSISwing
from .eod_reversion import EODReversion
from .eod_reversion2 import EODReversion2
from .stat_arb import StatArb

__all__ = [
    "Strategy",
    "StrategyPair",
    "StrategyBook",
    "RiskManager",
    "SMACrossover",
    "StochasticIndicator",
    "ORBIndicator",
    "VolumeDecay",
    "RSIScalp",
    "RecordBook",
    "RSISwing",
    "EODReversion",
    "EODReversion2",
    "DivArb",
    "StatArb",
    "strategy_map"
]

strategy_map = {
    "sma": SMACrossover,
    "stochastic": StochasticIndicator,
    "orb": ORBIndicator,
    "volume": VolumeDecay,
    "rsi": RSIScalp,
    "div_arb": DivArb,
    "record_book": RecordBook,
    "rsi_swing": RSISwing,
    "eod_reversion": EODReversion,
    "eod_reversion2": EODReversion2,
    "stat-arb": StatArb
}

