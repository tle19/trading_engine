from .strategy import Strategy, RiskManager
from .stochastic import StochasticIndicator
from .orb import ORBIndicator
from .macd import MACDIndicator
from .sma_crossover import SMACrossoverIndicator
from .ema_crossover import EMACrossoverIndicator

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
    "sma": SMACrossoverIndicator,
    "ema": EMACrossoverIndicator
}

