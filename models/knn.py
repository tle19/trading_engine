import numpy as np
import pandas as pd
from itertools import product
from sklearn.neighbors import KNeighborsClassifier

from models import BaseModel

class KNNModel(BaseModel):
    def __init__(self, symbol=None, strategy=None, live=False):
        super().__init__(symbol, strategy, live)
        
    def initialize(self):
        if self.live:
            return self.load_model(file=f"{self.symbol}_{self.strategy}_knn_model.pkl")
        else:
            self.build_model()
            self.open_trade_hist()
            self.prepare_features(self.df)
            return True

    def build_model(self, **params):
        self.model = KNeighborsClassifier(
            n_neighbors=params.get("n_neighbors", 5),
            weights=params.get("weights", "uniform"),
            algorithm=params.get("algorithm", "auto"),
            leaf_size=params.get("leaf_size", 30),
            p=params.get("p", 2),
            metric=params.get("metric", "minkowski"),
            metric_params=params.get("metric_params", None),
            n_jobs=params.get("n_jobs", -1)
        )
    
    def prepare_features(self, df):
        feature_cols = []
        df = df.copy()
        df['entry_time'] = pd.to_datetime(df['entry_time'], utc=True)
        df = df.sort_values('entry_time')
        df['date'] = df['entry_time'].dt.date
        
        # classification target
        if not self.live and "pnl_pct" in self.df.columns:
            df["target"] = (df["pnl_pct"] > 0.000).astype(int)
            feature_cols.append("entry_time")
            feature_cols.append("target")

        # session-relative prices
        for col in ["session_open", "session_low", "session_high"]:
            df[f"{col}_pct_from_entry"] = df["direction"] * (df[col] - df["entry_price"]) / df["entry_price"]
            feature_cols.append(f"{col}_pct_from_entry")

        # overnight gap
        df[f"overnight_gap"] = abs(1 - (df["session_open"] / df["prev_day_close"]))
        feature_cols.append("overnight_gap")

        # adx relationship
        daily_adx = df.groupby("date")["adx"].first().sort_index()
        daily_adx_ma = daily_adx.rolling(window=3, min_periods=1).mean()
        df["adx_ma"] = df["date"].map(daily_adx_ma)
        df["adx_trend"] = df["adx"] - df["adx_ma"]
        feature_cols.extend(["adx", "adx_ma", "adx_trend"])

        # atr relationship
        daily_atr = df.groupby("date")["atr"].first().sort_index()
        daily_atr_ma = daily_atr.rolling(window=3, min_periods=1).mean()
        df["atr_ma"] = df["date"].map(daily_atr_ma)
        df["atr_trend"] = df["atr"] - df["atr_ma"]
        feature_cols.extend(["atr", "atr_ma", "atr_trend"])

        # print(f"Features: {feature_cols}")
        self.df = df[feature_cols]

    def param_grid(self):
        grid = {
            "n_neighbors": [3, 5, 7, 9],
            "weights": ["uniform", "distance"],
            "algorithm": ["auto", "ball_tree", "kd_tree", "brute"],
            "leaf_size": [20, 30, 40],
            "p": [1, 2],  # 1 = Manhattan, 2 = Euclidean
            "metric": ["minkowski", "manhattan", "euclidean"]
        }

        for combo in product(*grid.values()):
            yield dict(zip(grid, combo))
    
    def save_model(self):
        super().save_model(file=f"{self.symbol}_{self.strategy}_knn_model.pkl")