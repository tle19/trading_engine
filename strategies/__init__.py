from .strategy import Strategy, RiskManager
from .macd import MACDIndicator
from .sma_crossover import SMACrossoverIndicator

__all__ = [
    "MACDIndicator",
    "SMACrossoverIndicator",
    "strategy_map",
]

strategy_map = {
    "macd": MACDIndicator,
    "sma": SMACrossoverIndicator
}

