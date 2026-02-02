from .strategy import Strategy
from .strategy_pair import StrategyPair
from .risk import RiskManager
from .example import SMACrossover
from .stochastic import StochasticIndicator
from .macd import MACDIndicator
from .orb import ORBIndicator
from .volume_decay import VolumeDecay
from .rsi_scalp import RSIScalp
from .spread_diff import SpreadDiff
from .ema_swing import EMASwing
from .rsi_swing import RSISwing
from .eod_reversion import EODReversion
from .eod_reversion2 import EODReversion2

__all__ = [
    "Strategy",
    "StrategyPair",
    "RiskManager",
    "SMACrossover",
    "StochasticIndicator",
    "MACDIndicator",
    "ORBIndicator",
    "VolumeDecay",
    "RSIScalp",
    "SpreadDiff",
    "EMASwing",
    "RSISwing",
    "EODReversion",
    "EODReversion2",
    "strategy_map"
]

strategy_map = {
    "sma": SMACrossover,
    "stochastic": StochasticIndicator,
    "macd": MACDIndicator,
    "orb": ORBIndicator,
    "volume": VolumeDecay,
    "rsi": RSIScalp,
    "spread_diff": SpreadDiff,
    "ema_swing": EMASwing,
    "rsi_swing": RSISwing,
    "eod_reversion": EODReversion,
    "eod_reversion2": EODReversion2
}

