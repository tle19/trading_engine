import os
import json
import pandas as pd

class BaseModel:
    def __init__(self, strategy):
        self.strategy = strategy
        self.model = None
        self.df = pd.DataFrame()
       
    def initialize(self):
        self.open_trade_hist()
        self.model = None
        self.prepare_features()
    
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
            print(f"No trades found for strategy: {self.strategy}")
            return

        self.df = pd.DataFrame(trade_history)
     
    def prepare_features(self):
        raise NotImplementedError
    
    def train(self):
        raise NotImplementedError

    def test(self):
        raise NotImplementedError
    
    def run(self):
        raise NotImplementedError