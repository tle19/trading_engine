import schwabdev
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import pandas as pd

client = schwabdev.Client("REMOVED", 
                          "REMOVED")

streamer = client.stream

symbol = "AMD"

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

candles = data.get("candles", [])

df = pd.DataFrame(candles)

df = pd.DataFrame(data.get("candles", []))
est = ZoneInfo("America/New_York")
df['datetime'] = pd.to_datetime(df['datetime'], unit='ms').dt.tz_localize('UTC').dt.tz_convert(est)
df.to_csv(f"{symbol}_historical_data.csv", index=False)

for _, row in df.iterrows():

    print(f"Time: {row['datetime']}, "
          f"Open: {row['open']}, "
          f"High: {row['high']}, "
          f"Low: {row['low']}, "
          f"Close: {row['close']}, "
          f"Volume: {row['volume']}")

