import os

import matplotlib.pyplot as plt
import pandas as pd

from utils import *
from strategy.mean_reversal import *


symbol = "TSLA"
date = "2025-08-22"
df = open_data(symbol, date)

df = strategy1(df)