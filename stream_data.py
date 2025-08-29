import schwabdev
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import json

est = ZoneInfo("America/New_York")

client = schwabdev.Client("REMOVED", 
                          "REMOVED")

streamer = client.stream

def response_handler(response):
    o = response.get("open")
    h = response.get("high")
    l = response.get("low")
    c = response.get("close")
    v = response.get("volume")
    ts = response.get("datetime")

    ts = datetime.fromtimestamp(ts / 1000)
    
    print(f"Open: {o}, High: {h}, Low: {l}, Close: {c}, Volume: {v}, Time: {ts}")

streamer.start(response_handler)

streamer.send(streamer.level_one_equities("AMD, INTC", "0,1,2,3"))

time.sleep(100) #duration of stream