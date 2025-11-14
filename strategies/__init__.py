from .strategy import Strategy, RiskManager
from .volume_accel import VolumeAccelIndicator
from .stochastic import StochasticIndicator
from .orb import ORBIndicator
from .macd import MACDIndicator
from .sma_crossover import SMACrossoverIndicator
from .ema_crossover import EMACrossoverIndicator

__all__ = [
    "VolumeAccelIndicator",
    "StochasticIndicator",
    "ORBIndicator",
    "MACDIndicator",
    "SMACrossoverIndicator",
    "strategy_map",
]

strategy_map = {
    "volume": VolumeAccelIndicator,
    "stochastic": StochasticIndicator,
    "orb": ORBIndicator,
    "macd": MACDIndicator,
    "sma": SMACrossoverIndicator,
    "ema": EMACrossoverIndicator
}

