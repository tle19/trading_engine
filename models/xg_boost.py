import os
import json
import pandas as pd
from models import BaseModel

class XGBModel(BaseModel):
    def __init__(self):
        self.model = None
        self.feature_columns = None

    def initialize(self):
        return NotImplementedError
    
    def train(self):
        return NotImplementedError

    def test(self):
        return NotImplementedError
     
    def run(self):
        return NotImplementedError