from .strategy import Strategy, RiskManager
from .stochastic import StochasticIndicator
from .sma_crossover import SMACrossoverIndicator
from .orb import ORBIndicator
from .macd import MACDIndicator

__all__ = [
    "StochasticIndicator",
    "ORBIndicator",
    "MACDIndicator",
    "SMACrossoverIndicator",
    "strategy_map",
]

strategy_map = {
    "stochastic": StochasticIndicator,
    "orb": ORBIndicator,
    "macd": MACDIndicator,
    "sma": SMACrossoverIndicator
}

