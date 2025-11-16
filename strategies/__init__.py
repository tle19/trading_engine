from .strategy import Strategy, RiskManager
from .volume_decay import VolumeDecayIndicator
from .stochastic import StochasticIndicator
from .orb import ORBIndicator
from .macd import MACDIndicator
from .sma_crossover import SMACrossoverIndicator
from .ema_crossover import EMACrossoverIndicator

__all__ = [
    "VolumeDecayIndicator",
    "StochasticIndicator",
    "ORBIndicator",
    "MACDIndicator",
    "SMACrossoverIndicator",
    "strategy_map",
]

strategy_map = {
    "volume": VolumeDecayIndicator,
    "stochastic": StochasticIndicator,
    "orb": ORBIndicator,
    "macd": MACDIndicator,
    "sma": SMACrossoverIndicator,
    "ema": EMACrossoverIndicator
}

