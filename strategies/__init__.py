from .strategy import Strategy, RiskManager
from .trend_follow import TrendFollowIndicator
from .momentum import MomentumSMAIndicator
from .sma_crossover import SMACrossoverIndicator

__all__ = [
    "TrendFollowIndicator",
    "MomentumSMAIndicator",
    "SMACrossoverIndicator",
    "strategy_map",
]

strategy_map = {
    "trend": TrendFollowIndicator,
    "momentum": MomentumSMAIndicator,
    "sma": SMACrossoverIndicator
}

