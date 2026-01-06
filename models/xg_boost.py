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
                n_estimators=100,
                max_depth=3,
                learning_rate=0.1,
                subsample=1.0,
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
        feature_cols = []
        df = df.copy()
        df = df.sort_values('entry_time')

        # extract date
        df['date'] = df['entry_time'].dt.date
        
        # # filter out chop
        # df = df[df["pnl_pct"].abs() > 0.0001]
        
        # classification target
        if not self.live and "pnl_pct" in self.df.columns:
            df["target"] = (df["pnl_pct"] > 0.000).astype(int)
            feature_cols.append("entry_time")
            feature_cols.append("target")

        # overnight gap
        df[f"overnight_gap"] = abs(1 - (df["session_open"] / df["prev_day_close"]))
        feature_cols.append("overnight_gap")

        # adx relationship
        daily_adx = df.groupby("date")["adx"].first().sort_index()
        daily_adx_ma = daily_adx.rolling(window=3, min_periods=1).mean()
        df["adx_ma"] = df["date"].map(daily_adx_ma)
        df["adx_trend"] = df["adx"] - df["adx_ma"]
        feature_cols.extend(["adx", "adx_ma", "adx_trend"])

        # atr
        daily_atr = df.groupby("date")["atr"].first().sort_index()
        daily_atr_ma = daily_atr.rolling(window=3, min_periods=1).mean()
        df["atr_ma"] = df["date"].map(daily_atr_ma)
        df["atr_trend"] = df["atr"] - df["atr_ma"]
        feature_cols.extend(["atr", "atr_ma", "atr_trend"])

        # pnl performance
        daily_pnl = df.groupby('date')['yday_pnl'].sum().sort_index()
        daily_pnl_rolling_mean = daily_pnl.rolling(window=10, min_periods=1).mean()
        daily_pnl_rolling_sum = daily_pnl.rolling(window=10, min_periods=1).sum()
        df['pnl_rolling_mean'] = df['date'].map(daily_pnl_rolling_mean)
        df['pnl_rolling_sum'] = df['date'].map(daily_pnl_rolling_sum)
        feature_cols.extend(["pnl_rolling_mean", "pnl_rolling_sum"])

        # drawdown performance
        daily_equity = (1 + daily_pnl).cumprod()
        rolling_max_1 = daily_equity.rolling(5, min_periods=1).max()
        rolling_max_2 = daily_equity.rolling(20, min_periods=1).max()
        drawdown_1 = (rolling_max_1 - daily_equity) / rolling_max_1
        drawdown_2 = (rolling_max_2 - daily_equity) / rolling_max_2
        df['drawdown_1'] = df['date'].map(drawdown_1)
        df['drawdown_2'] = df['date'].map(drawdown_2)
        feature_cols.extend(['drawdown_1', 'drawdown_2'])
        
        # print(f"Features: {feature_cols}")
        self.df = df[feature_cols]

    # def train(self, X, y, decay=0.001):
    #     n = len(X)
    #     sample_weight = np.exp(decay * np.arange(n))
    #     sample_weight /= sample_weight.mean()

    #     self.model.fit(X, y, sample_weight=sample_weight)

    def save_model(self):
        super().save_model(file=f"{self.symbol}_xgb_model.pkl")