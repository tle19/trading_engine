from .strategy import Strategy
from .strategy_pair import StrategyPair
from .risk import RiskManager
from .example import SMACrossover
from .stochastic import StochasticIndicator
from .orb import ORBIndicator
from .volume_decay import VolumeDecay
from .rsi_scalp import RSIScalp
from .spread_scalp import SpreadScalp
from .rsi_swing import RSISwing
from .eod_reversion import EODReversion
from .eod_reversion2 import EODReversion2

__all__ = [
    "Strategy",
    "StrategyPair",
    "RiskManager",
    "SMACrossover",
    "StochasticIndicator",
    "ORBIndicator",
    "VolumeDecay",
    "RSIScalp",
    "SpreadScalp",
    "RSISwing",
    "EODReversion",
    "EODReversion2",
    "strategy_map"
]

strategy_map = {
    "sma": SMACrossover,
    "stochastic": StochasticIndicator,
    "orb": ORBIndicator,
    "volume": VolumeDecay,
    "rsi": RSIScalp,
    "spread_scalp": SpreadScalp,
    "rsi_swing": RSISwing,
    "eod_reversion": EODReversion,
    "eod_reversion2": EODReversion2
}

