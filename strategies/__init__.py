from .strategy import Strategy, PositionLeg, PositionManager, RiskManager
from .example import SMACrossover
from .stochastic import StochasticIndicator
from .macd import MACDIndicator
from .orb import ORBIndicator
from .volume_decay import VolumeDecay
from .rsi_scalp import RSIScalp
from .box import BoxIndicator
from .ema_swing import EMASwing
from .rsi_swing import RSISwing
from .eod_buyback import EODBuyBack

__all__ = [
    "SMACrossover",
    "StochasticIndicator",
    "MACDIndicator",
    "ORBIndicator",
    "VolumeDecay",
    "RSIScalp",
    "BoxIndicator",
    "EMASwing",
    "RSISwing",
    "EODBuyBack",
    "strategy_map"
]

strategy_map = {
    "sma": SMACrossover,
    "stochastic": StochasticIndicator,
    "macd": MACDIndicator,
    "orb": ORBIndicator,
    "volume": VolumeDecay,
    "rsi": RSIScalp,
    "box": BoxIndicator,
    "ema_swing": EMASwing,
    "rsi_swing": RSISwing,
    "eod_buyback": EODBuyBack
}

