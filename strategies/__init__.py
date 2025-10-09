from .strategy import Strategy
from .mean_reversion import MeanReversionIndicator
from .momentum import MomentumSMAIndicator
from .sma_crossover import SMACrossoverIndicator

__all__ = [
    "MeanReversionIndicator",
    "MomentumSMAIndicator",
    "SMACrossoverIndicator",
    "strategy_map",
]

strategy_map = {
    "mean": MeanReversionIndicator,
    "momentum": MomentumSMAIndicator,
    "sma": SMACrossoverIndicator
}

