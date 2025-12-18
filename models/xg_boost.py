import pandas as pd
from xgboost import XGBClassifier, XGBRegressor

from models import BaseModel

class XGBModel(BaseModel):
    def __init__(self, strategy=None, live=False):
        super().__init__(strategy, live)
        
    def initialize(self):
        if not self.live:
            self.model = XGBClassifier(
                n_estimators=50,
                max_depth=2,
                learning_rate=0.2,
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
        else:
            self.load_model(file="xgb_model.pkl")
    
    def prepare_features(self, df):
        df = df.copy()
        feature_cols = []

        # classification target
        if not self.live and "pnl_pct" in self.df.columns:
            df["target"] = (df["pnl_pct"] > -0.001).astype(int)
            feature_cols.append("entry_time")
            feature_cols.append("target")

        # session-relative prices
        for col in ["session_open", "session_low", "session_high"]:
            if col in df.columns:
                df[f"{col}_pct_from_entry"] = df["direction"] * (df["entry_price"] - df[col]) / df["entry_price"]
                feature_cols.append(f"{col}_pct_from_entry")

        # # time from market open
        # market_open = df["entry_time"].dt.normalize() + pd.Timedelta(hours=9, minutes=30)
        # df["minutes_from_open"] = (df["entry_time"] - market_open).dt.total_seconds() / 60
        # feature_cols.append("minutes_from_open")

        self.df = df[feature_cols]
        # print(f"Features: {feature_cols}")
        
    def train(self, X, y):
        self.model.fit(X, y)