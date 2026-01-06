import pandas as pd
import numpy as np
from xgboost import XGBClassifier

from models import BaseModel

class XGBModel(BaseModel):
    def __init__(self, symbol=None, strategy=None, live=False):
        super().__init__(symbol, strategy, live)
        
    def initialize(self):
        if not self.live:
            self.model = XGBClassifier(
                n_estimators=50,
                max_depth=2,
                learning_rate=0.15,
                subsample=0.5,
                colsample_bytree=1.0,
                reg_alpha=1.0,
                reg_lambda=1.0,
                eval_metric='logloss',
                random_state=42
            )
            self.open_trade_hist()
            if hasattr(self, "df") and not self.df.empty:
                self.prepare_features(self.df)
            return True
        else:
            return self.load_model(file=f"{self.symbol}_xgb_model.pkl")
    
    def prepare_features(self, df):
        df = df.copy()
        feature_cols = []
        
        # df["entry_time"] = pd.to_datetime(df["entry_time"])
        # df = df.sort_values("entry_time")
        # cutoff = df["entry_time"].max() - pd.DateOffset(months=1)
        # df = df[df["entry_time"] >= cutoff]

        # inverted copy
        # inv = df.copy()
        # inv["direction"] = -inv["direction"]
        # inv["pnl_pct"] = -inv["pnl_pct"]
        # df = pd.concat([df, inv], ignore_index=True)
        
        # df = df[df["pnl_pct"].abs() > 0.00025]
        
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
        df[f"overnight_gap"] = df["session_open"] - df["prev_day_close"]
        feature_cols.append("overnight_gap")

        # # time from market open
        # market_open = df["entry_time"].dt.normalize() + pd.Timedelta(hours=9, minutes=30)
        # df["minutes_from_open"] = (df["entry_time"] - market_open).dt.total_seconds() / 60
        # feature_cols.append("minutes_from_open")

        # other features
        feature_cols.extend(["adx", "adx_ma_3"])
        feature_cols.extend(["atr", "atr_ma_3"])
        feature_cols.append("open_volume")
        
        self.df = df[feature_cols]
        # print(f"Features: {feature_cols}")

    # def train(self, X, y, decay=0.001):
    #     n = len(X)
    #     sample_weight = np.exp(decay * np.arange(n))
    #     sample_weight /= sample_weight.mean()

    #     self.model.fit(X, y, sample_weight=sample_weight)

    def save_model(self):
        super().save_model(file=f"{self.symbol}_xgb_model.pkl")