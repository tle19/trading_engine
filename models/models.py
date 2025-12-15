import pandas as pd
import json
import os
# import joblib
# from xgboost import XGBClassifier
# from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


class TradeModel:
    def __init__(self):
        self.model = None
        self.feature_columns = None

    def trade_history_df(self, strategy_name="StochasticIndicator", 
                             log_file="trade_logs.json"):
        with open(log_file, "r") as f:
            data = json.load(f)

        trade_history = []
        for trade in data.get("trade_history", []):
            if strategy_name and trade.get("strategy") != strategy_name:
                continue

            trade_copy = trade.copy()
            for key in ["entry_time", "exit_time"]:
                if key in trade_copy and trade_copy[key] is not None:
                    trade_copy[key] = pd.Timestamp(trade_copy[key])

            features = trade_copy.pop("features", {})
            for feat_name, feat_val in features.items():
                if isinstance(feat_val, list):
                    for i, v in enumerate(feat_val, start=1):
                        trade_copy[f"{feat_name}_{i}"] = v
                else:
                    trade_copy[feat_name] = feat_val

            trade_history.append(trade_copy)

        if not trade_history:
            print(f"No trades found for strategy: {strategy_name}")
            return pd.DataFrame()

        df = pd.DataFrame(trade_history)
        return df

    def train(self):
        # xg boost / rf / nn
        return NotImplementedError

    def test(self):
        return NotImplementedError