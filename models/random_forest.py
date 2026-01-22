import numpy as np
import pandas as pd
from itertools import product
from sklearn.ensemble import RandomForestClassifier

from models import BaseModel

class RFModel(BaseModel):
    def __init__(self, symbol=None, strategy=None, live=False):
        super().__init__(symbol, strategy, live)
        
    def initialize(self):
        if self.live:
            return self.load_model(file=f"{self.symbol}_{self.strategy}_rf_model.pkl")
        else:
            self.build_model()
            self.open_trade_hist()
            self.prepare_features(self.df)
            return True
        
    def build_model(self, **params):
        self.model = RandomForestClassifier(
            n_estimators=params.get("n_estimators", 150),
            max_depth=params.get("max_depth", 10),
            max_features=params.get("max_features", "sqrt"),
            min_samples_split=params.get("min_samples_split", 3),
            min_samples_leaf=params.get("min_samples_leaf", 3),
            class_weight=params.get("class_weight", {0: 1.0, 1: 1.0}),
            bootstrap=params.get("bootstrap", True),
            n_jobs=params.get("n_jobs", -1),
            random_state=params.get("random_state", 42)
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

    def train(self, X, y, decay=0.005):
        n = len(X)
        sample_weight = np.exp(decay * np.arange(n))
        sample_weight /= sample_weight.mean()

        self.model.fit(X, y, sample_weight=sample_weight)

    def param_grid(self):
        grid = {
            "n_estimators": [50, 100, 150],
            "max_depth": [7, 12, None],
            "max_features": ["sqrt", "log2"],
            "min_samples_split": [2, 3, 5],
            "min_samples_leaf": [1, 2, 3],
            "class_weight": [
                {0: 1.0, 1: 1.0}
            ],
            "random_state": [42]
        }

        for combo in product(*grid.values()):
            yield dict(zip(grid, combo))

    def save_model(self):
        super().save_model(file=f"{self.symbol}_{self.strategy}_rf_model.pkl")