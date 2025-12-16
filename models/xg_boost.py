import pandas as pd
from xgboost import XGBClassifier

from models import BaseModel

class XGBModel(BaseModel):
    def __init__(self, strategy, live):
        super().__init__(strategy, live)
        
    def initialize(self):
        self.model = XGBClassifier(
            n_estimators=50, 
            max_depth=3, 
            learning_rate=0.2,
            eval_metric='logloss',
            random_state=42
        )

        if not self.live:
            self.open_trade_hist()
            if hasattr(self, "df") and not self.df.empty:
                self.prepare_features(self.df)        
    
    def prepare_features(self, df):
        df = df.copy()
        feature_cols = []

        # target
        if not self.live and "pnl" in self.df.columns:
            df["target"] = (df["pnl"] > 0).astype(int)
        
        # session-relative prices
        for col in ["session_open", "session_low", "session_high"]:
            if col in df.columns:
                df[f"{col}_pct_from_entry"] = (df[col] - df["entry_price"]) / df["entry_price"]
                feature_cols.append(f"{col}_pct_from_entry")

        # time from market open
        market_open = df["entry_time"].dt.normalize() + pd.Timedelta(hours=9, minutes=30)
        df["minutes_from_open"] = (df["entry_time"] - market_open).dt.total_seconds() / 60
        feature_cols.append("minutes_from_open")

        if not self.live:
            self.df = df[feature_cols + ["target"]]
        else:
            self.df = df[feature_cols]
        # print(f"Features: {feature_cols}")
        
    def train(self, X, y):
        self.model.fit(X, y)