import pandas as pd
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler

from models import BaseModel

class KNNModel(BaseModel):
    def __init__(self, symbol=None, strategy=None, live=False):
        super().__init__(symbol, strategy, live)
        
    def initialize(self):
        if not self.live:
            self.model = KNeighborsClassifier(
                n_neighbors=5,
                weights='uniform',
                metric='minkowski',
                p=2
            )
            self.open_trade_hist()
            if hasattr(self, "df") and not self.df.empty:
                self.prepare_features(self.df)
            return True
        else:
            return self.load_model(file=f"{self.symbol}_rf_model.pkl")
    
    def prepare_features(self, df):
        df = df.copy()
        feature_cols = []

        # classification target
        if not self.live and "pnl_pct" in self.df.columns:
            df["target"] = (df["pnl_pct"] > -0.001).astype(int)

        # session-relative prices
        for col in ["session_open", "session_low", "session_high"]:
            df[f"{col}_pct_from_entry"] = df["direction"] * (df[col] - df["entry_price"]) / df["entry_price"]
            feature_cols.append(f"{col}_pct_from_entry")
        
        # overnight gap
        df[f"overnight_gap"] = df["session_open"] - df["prev_day_close"]
        feature_cols.append("overnight_gap")

        # # time from market open
        # market_open = df["entry_time"].dt.normalize() + pd.Timedelta(hours=9, minutes=30)
        # df["minutes_from_open"] = (df["entry_time"] - market_open).dt.total_seconds() / 60
        # feature_cols.append("minutes_from_open")

        # other features
        feature_cols.extend(["adx", "adx_ma_3"])
        # feature_cols.extend(["atr", "atr_ma_3"])
        feature_cols.append("open_volume")

        # scale features
        X = df[feature_cols].copy()
        X_scaled = StandardScaler().fit_transform(X)
        self.df = pd.DataFrame(X_scaled, columns=feature_cols, index=df.index)
        self.df["entry_time"] = df["entry_time"]
        self.df["target"] = df["target"]

        # print(f"Features: {feature_cols}")

    def save_model(self, file):
        super().save_model(file=f"{self.symbol}_knn_model.pkl")