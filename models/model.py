import os
import json
import numpy as np
import pandas as pd
import pickle
from itertools import product
from zoneinfo import ZoneInfo

from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score, f1_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

timezone = ZoneInfo("America/New_York")

class BaseModel:
    def __init__(self, symbol=None, strategy=None, live=False):
        self.symbol = symbol
        self.strategy = strategy
        self.live = live
        self.model = None
        self.df = pd.DataFrame()
       
    def initialize(self):
        if self.live:
            self.load_model(file=f"{self.symbol}_{self.strategy}_xgb_model.pkl")
        else:
            self.build_model()
            self.open_trade_hist()
            self.prepare_features(self.df)
   
    def build_model(self):
        raise NotImplementedError
       
    def save_model(self, file="ml_model.pkl"):
        with open(file, "wb") as f:
            pickle.dump(self.model, f)
        print(f"Saved model to {file}")
                
    def load_model(self, file="ml_model.pkl"):
        try:
            with open(file, "rb") as f:
                self.model = pickle.load(f)
            print(f"Loaded model from {file}")
            return True
        except (FileNotFoundError):
            return False

    def open_trade_hist(self, file="trade_logs.json"):
        try:
            with open(file, "r") as f:
                data = json.load(f)
        except (FileNotFoundError):
            raise FileNotFoundError(f"Trade Logs file not found: {file}")

        rows = []
        for trade in data.get("trade_history", []):
            if self.strategy and trade.get("strategy") != self.strategy:
                continue
            
            features = trade.get("features", {})
            features["pnl_pct"] = trade["pnl_pct"]

            if "entry_time" in features and features["entry_time"] is not None:
                features["entry_time"] = (
                    pd.to_datetime(features["entry_time"], utc=True).tz_convert(timezone)
                )

            rows.append(features)

        if not rows:
            print(f"No trades found for strategy: {self.strategy}")

        self.df = pd.DataFrame(rows)
           
    def prepare_features(self, df):
        df = df.copy()
        feature_cols = []
        df['entry_time'] = pd.to_datetime(df['entry_time'], utc=True)
        df = df.sort_values('entry_time')
        df['date'] = df['entry_time'].dt.date
        
        # classification target
        if not self.live and "pnl" in self.df.columns:
            # filter out chop
            df = df[df["pnl_pct"].abs() > 0.001]
            
            # original output labels
            mask = df["direction"] != df["original_dir"]
            df.loc[mask, "direction"] = df.loc[mask, "original_dir"]
            df.loc[mask, "pnl_pct"] = -df.loc[mask, "pnl_pct"]

            df["target"] = (df["pnl_pct"] > 0).astype(int)

        # regression target
        if not self.live and "pnl" in self.df.columns:
            df["target"] = df["pnl"] / (df["direction"] * (df["entry_price"] - df["stop_price"]))

        # session-relative prices
        for col in ["session_open", "session_low", "session_high"]:
            df[f"{col}_pct_from_entry"] = df["direction"] * (df[col] - df["entry_price"]) / df["entry_price"]
            feature_cols.append(f"{col}_pct_from_entry")
            
        # overnight gap
        df[f"overnight_gap"] = abs(1 - (df["session_open"] / df["prev_day_close"]))
        feature_cols.append("overnight_gap")

        # time from market open
        market_open = df["entry_time"].dt.normalize() + pd.Timedelta(hours=9, minutes=30)
        df["minutes_from_open"] = (df["entry_time"] - market_open).dt.total_seconds() / 60
        feature_cols.append("minutes_from_open")

        # market open volume
        feature_cols.append("open_volume")

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
                
    def train(self, X, y):
        self.model.fit(X, y)
    
    def grid_search(self, X_train, X_val, y_train, y_val):
        best_score = -float("inf")
        best_params = None

        for params in self.param_grid():
            self.build_model(**params)
            self.train(X_train, y_train)

            preds = self.model.predict(X_val)
            score = self.metric(y_val, preds)

            if score > best_score:
                best_score = score
                best_params = params

        X_full = pd.concat([X_train, X_val])
        y_full = pd.concat([y_train, y_val])
    
        self.build_model(**best_params)
        self.train(X_train, y_train) # X_full, y_full
    
    def param_grid(self):
        raise NotImplementedError
    
    def metric(self, y_true, y_pred, min_tn_fraction=0.05, max_tn_fraction=0.2):
        y_true = np.array(y_true)
        y_pred = np.array(y_pred)

        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        total_preds = tn + fp + fn + tp
        tn_fraction = tn / total_preds
        
        if tn_fraction > max_tn_fraction or tn_fraction < min_tn_fraction:
            return -1.0
        
        if tn + fn == 0:
            return 0.0
        
        npv = tn / (tn + fn)
        return npv
    
    def evaluate_classification(self, X_train, X_test, y_train, y_test, threshold=0.4):
        y_train_proba = self.model.predict_proba(X_train)[:, 1]
        y_test_proba = self.model.predict_proba(X_test)[:, 1]
        y_train_pred = (y_train_proba >= threshold).astype(int)
        y_test_pred = (y_test_proba >= threshold).astype(int)

        train_acc = accuracy_score(y_train, y_train_pred)
        test_acc = accuracy_score(y_test, y_test_pred)

        tn, fp, fn, tp = confusion_matrix(y_test, y_test_pred).ravel()
        total = tp + fp + tn + fn
        precision = precision_score(y_test, y_test_pred)
        recall = recall_score(y_test, y_test_pred)
        f1 = f1_score(y_test, y_test_pred)
        npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0

        print("=== Classification Metrics ===")
        print(f"Train Accuracy: {train_acc:.4f}")
        print(f"Test Accuracy: {test_acc:.4f}")
        print(f"TP: {tp/total:.4f}, FP: {fp/total:.4f}, TN: {tn/total:.4f}, FN: {fn/total:.4f}")
        print(f"Test Precision: {precision:.4f}")
        print(f"Test Recall:    {recall:.4f}")
        print(f"Test NPV:       {npv:.4f}")
        print(f"Test F1 Score:  {f1:.4f}")

    def evaluate_regression(self, X_train, X_test, y_train, y_test):
        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)

        train_mse = mean_squared_error(y_train, y_train_pred)
        train_mae = mean_absolute_error(y_train, y_train_pred)
        train_r2  = r2_score(y_train, y_train_pred)

        test_mse = mean_squared_error(y_test, y_test_pred)
        test_mae = mean_absolute_error(y_test, y_test_pred)
        test_r2  = r2_score(y_test, y_test_pred)

        print("=== Regression Metrics ===")
        print(f"Train MSE: {train_mse:.6f}, MAE: {train_mae:.6f}, R²: {train_r2:.4f}")
        print(f"Test  MSE: {test_mse:.6f}, MAE: {test_mae:.6f}, R²: {test_r2:.4f}")

    def get_proba(self):
        X_input = self.df[self.model.feature_names_in_]
        proba = self.model.predict_proba(X_input)[0, 1]
        return proba