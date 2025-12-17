import os
import json
import pandas as pd
import pickle
from zoneinfo import ZoneInfo

from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score, f1_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

timezone = ZoneInfo("America/New_York")

class BaseModel:
    def __init__(self, strategy=None, live=False):
        self.strategy = strategy
        self.live = live
        self.model = None
        self.df = pd.DataFrame()
       
    def initialize(self):
        self.model = None

        if not self.live:
            self.open_trade_hist()
            if hasattr(self, "df") and not self.df.empty:
                self.prepare_features(self.df)    
    
    def save_model(self, file="ml_model.pkl"):
        with open(file, "wb") as f:
            pickle.dump(self.model, f)
        print(f"Saved model to {file}")
                
    def load_model(self, file="ml_model.pkl"):
        with open(file, "rb") as f:
            self.model = pickle.load(f)
        print(f"Loaded model from {file}")

    def open_trade_hist(self, log_file="trade_logs.json"):
        with open(log_file, "r") as f:
            data = json.load(f)

        trade_history = []
        for trade in data.get("trade_history", []):
            if self.strategy and trade.get("strategy") != self.strategy:
                continue

            trade_copy = trade.copy()
            for key in ["entry_time", "exit_time"]:
                if key in trade_copy and trade_copy[key] is not None:
                    trade_copy[key] = pd.to_datetime(trade_copy[key], utc=True).tz_convert(timezone)

            features = trade_copy.pop("features", {})
            for feat_name, feat_val in features.items():
                if isinstance(feat_val, list):
                    for i, v in enumerate(feat_val, start=0):
                        trade_copy[f"{feat_name}_{i}"] = v
                else:
                    trade_copy[feat_name] = feat_val

            trade_history.append(trade_copy)

        if not trade_history:
            print(f"No trades found for strategy: {self.strategy}")
            return

        self.df = pd.DataFrame(trade_history)
     
    def prepare_features(self, df):
        df = df.copy()
        feature_cols = []

        # classification target
        if not self.live and "pnl" in self.df.columns:
            df["target"] = (df["pnl_pct"] > 0).astype(int)

        # regression target
        if not self.live and "pnl" in self.df.columns:
            df["target"] = df["pnl"] / (df["direction"] * (df["entry_price"] - df["stop_price"]))

        # ohlcv normalization
        for base in ["opens", "closes", "lows", "highs", "volumes"]:
            cols = [f"{base}_{i}" for i in range(0, 10)]
            df[cols] = df[cols].apply(
                lambda x: (x - x.min()) / (x.max() - x.min())
                if (x.max() - x.min()) != 0 else 0,
                axis=1
            )
            feature_cols.extend(cols)

        # body = close - open
        # range_ = high - low
        # upper_wick = high - max(open, close)
        # lower_wick = min(open, close) - low
        # body_pct = body / range_
        
    def train(self, X, y):
        self.model.fit(X, y)
    
    def evaluate_classification(self, X_train, y_train, X_test, y_test):
        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)

        train_acc = accuracy_score(y_train, y_train_pred)
        test_acc = accuracy_score(y_test, y_test_pred)

        tn, fp, fn, tp = confusion_matrix(y_test, y_test_pred).ravel()
        total = tp + fp + tn + fn

        precision = precision_score(y_test, y_test_pred)
        recall = recall_score(y_test, y_test_pred)
        f1 = f1_score(y_test, y_test_pred)

        print("=== Classification Metrics ===")
        print(f"Train Accuracy: {train_acc:.4f}")
        print(f"Test Accuracy: {test_acc:.4f}")
        print(f"TP: {tp/total:.4f}, FP: {fp/total:.4f}, TN: {tn/total:.4f}, FN: {fn/total:.4f}")
        print(f"Test Precision: {precision:.4f}")
        print(f"Test Recall:    {recall:.4f}")
        print(f"Test F1 Score:  {f1:.4f}")

    def evaluate_regression(self, X_train, y_train, X_test, y_test):
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

    def get_proba(self, feature_row):
        X_input = feature_row.values.reshape(1, -1) if isinstance(feature_row, pd.Series) else feature_row.values
        prob = self.model.predict_proba(X_input)[0, 1]
        return prob