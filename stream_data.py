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

timezone = ZoneInfo("America/New_York")
df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume' ,'datetime'])

def response_handler(response):
    data = json.loads(response)
    data = data.get("data", [])

    global df

    if not data:
        return 
    for item in data:
        content = item["content"][0]
        row = {
            "open": content.get("17"),
            "high": content.get("10"),
            "low": content.get("11"),
            "close": content.get("12"),
            "volume": content.get("8"),
            "datetime": pd.to_datetime(item["timestamp"], unit='ms').tz_localize('UTC').tz_convert(timezone)
        }
        df.loc[len(df)] = row
    
    curr = df.iloc[-1]
    print(f"Datetime: {curr['datetime']}, "
          f"Open: {curr['open']}, "
          f"High: {curr['high']}, "
          f"Low: {curr['low']}, "
          f"Close: {curr['close']}, "
          f"Volume: {curr['volume']}")

streamer.start(response_handler)

streamer.send(streamer.level_one_equities(symbol, "0,8,10,11,12,17", command="ADD"))
time.sleep(100) # stream duration

streamer.stop()

df.to_csv(f"data/{symbol}_streamed_data.csv", index=False)