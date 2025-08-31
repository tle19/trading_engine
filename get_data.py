import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import schwabdev


app_key = "REMOVED"
app_secret = "REMOVED"

client = schwabdev.Client(app_key, app_secret)
streamer = client.stream
symbol = "TSLA"

historical_data = client.price_history(
    symbol=symbol, 
    periodType="day", 
    period=10, 
    frequencyType="minute", 
    frequency=1, 
    startDate=None,
    endDate=None, 
    needExtendedHoursData=None, 
    needPreviousClose=None
)

full_str = b"".join(historical_data).decode("utf-8")
data = json.loads(full_str)
df = pd.DataFrame(data.get("candles", []))

timezone = ZoneInfo("America/New_York")
df['datetime'] = pd.to_datetime(df['datetime'], unit='ms').dt.tz_localize('UTC').dt.tz_convert(timezone)

for _, row in df.iterrows():

    print(f"Datetime: {row['datetime']}, "
          f"Open: {row['open']}, "
          f"High: {row['high']}, "
          f"Low: {row['low']}, "
          f"Close: {row['close']}, "
          f"Volume: {row['volume']}")
    
df.to_csv(f"data/{symbol}_historical_data.csv", index=False)