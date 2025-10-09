from .strategy import Strategy
from .mean_reversion import MeanReversionIndicator
from .momentum import MomentumSMAIndicator
from .sma_crossover import SMACrossoverIndicator

strategy_map = {
    "mean": MeanReversionIndicator,
    "momentum": MomentumSMAIndicator,
    "sma": SMACrossoverIndicator
}