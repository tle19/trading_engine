from .strategy import Strategy
from .mean_reversion import MeanReversionIndicator
from .momentum import MomentumSMAIndicator
from .sma import SMAIndicator

strategy_map = {
    "mean": MeanReversionIndicator,
    "momentum": MomentumSMAIndicator,
    "sma": SMAIndicator
}