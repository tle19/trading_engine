import pandas as pd
from xgboost import XGBClassifier

from models import BaseModel

class XGBModel(BaseModel):
    def __init__(self, strategy):
        super().__init__(strategy)
        
    def initialize(self):
        self.open_trade_hist()
        self.model = XGBClassifier(
            n_estimators=100, 
            max_depth=3, 
            use_label_encoder=False, 
            eval_metric='logloss'
        )
        self.prepare_features()
    
    def prepare_features(self):
        df = self.df

        if "pnl" in self.df.columns:
            df["target"] = (df["pnl"] > 0).astype(int)

        for col in ["strategy", "symbol", "direction", "position_size", "shares",
                    "entry_fill", "exit_time", "exit_price", "exit_fill", "pnl", "pnl_pct"]:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)

        self.df = df
        
    def train(self, X, y):
        self.model.fit(X, y)

    def test(self, X, y):
        self.model.predict(X)
     
    def run(self):
        return NotImplementedError