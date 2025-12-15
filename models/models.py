import pandas as pd
import json
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
    
def train(self):
    # xg boost / rf / nn
    return NotImplementedError

def test(self):
    return NotImplementedError