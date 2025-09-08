import os

import json
import matplotlib.pyplot as plt
import pandas as pd


def summary(df, initial_cash):
    strategy_final = df['equity'].iloc[-1]
    print("Strategy final value:", strategy_final)
    print("Strategy Profit %:", (strategy_final - initial_cash) / initial_cash * 100, "%")

def profits(df, symbol="", date=""):
    plt.figure(figsize=(12,6))
    plt.plot(df.index, df['equity'], label='Strategy', color='blue')
    plt.xlabel("Time")
    plt.ylabel("Portfolio Value")
    plt.title(f"{symbol} Strategy Profits ({date})")
    plt.legend()
    plt.grid(True)
    plt.show()

def HOD_probability(df, opening_minutes=30, filename="hod_results.json"):
    df = df.copy()

    results = []

    for date, group in df.groupby(df.index.date):
        group = group.sort_index()
        end_time = (pd.Timestamp(date, tz="America/New_York") + pd.Timedelta(minutes=9*60 + opening_minutes)).time()
        opening_window = group.between_time("09:30", end_time)

        if opening_window.empty:
            continue

        opening_high = opening_window["high"].max()
        opening_low = opening_window["low"].min()

        later_group = group[group.index > opening_window.index[-1]]
        later_hod = later_group["high"].max() if not later_group.empty else None
        later_lod = later_group["low"].min() if not later_group.empty else None

        hod_after_trend = later_hod is not None and later_hod > opening_high
        lod_below_trend = later_lod is not None and later_lod < opening_low

        hod_return_pct = (later_hod - opening_high) / opening_high * 100 if later_hod is not None else None
        lod_return_pct = (later_lod - opening_low) / opening_low * 100 if later_lod is not None else None

        results.append({
            "date": date.isoformat(),
            "opening_trend_high": opening_high,
            "opening_trend_low": opening_low,
            "later_hod": later_hod,
            "later_lod": later_lod,
            "hod_after_trend": hod_after_trend,
            "lod_below_trend": lod_below_trend,
            "hod_return_pct": hod_return_pct,
            "lod_return_pct": lod_return_pct
        })

    daily_df = pd.DataFrame(results)
    avg_hod_prob = daily_df["hod_after_trend"].mean()
    avg_lod_prob = daily_df["lod_below_trend"].mean()
    avg_hod_return = daily_df["hod_return_pct"].mean()
    avg_lod_return = daily_df["lod_return_pct"].mean()

    output = {
        "average_hod_prob": avg_hod_prob,
        "average_lod_prob": avg_lod_prob,
        "average_hod_return_pct": avg_hod_return,
        "average_lod_return_pct": avg_lod_return,
        "daily_results": daily_df.to_dict(orient="records")
    }

    with open(filename, "w") as f:
        json.dump(output, f, indent=4)

    print(f"HOD/LOD results with percent returns saved to {filename}")
        
def bearish_overnight_return(df, opening_minutes=30, filename="overnight_results.json"):
    df = df.copy()
    results = []
    grouped = df.groupby(df.index.date)
    dates = sorted(grouped.groups.keys())

    for i in range(len(dates) - 1):
        today = dates[i]
        next_day = dates[i + 1]

        group_today = grouped.get_group(today).sort_index()
        open_price = group_today.iloc[0]["open"]
        close_price = group_today.iloc[0]["close"]

        if close_price >= open_price:
            continue

        end_time = (pd.Timestamp(today, tz="America/New_York") + pd.Timedelta(minutes=9*60 + opening_minutes)).time()
        opening_window = group_today.between_time("09:30", end_time)

        if opening_window.empty:
            continue

        entry_price = opening_window.iloc[-1]["close"]
        next_open_price = grouped.get_group(next_day).iloc[0]["open"]
        pct_return = (next_open_price - entry_price) / entry_price * 100

        results.append({
            "entry_date": today.isoformat(),
            "entry_price": entry_price,
            "exit_date": next_day.isoformat(),
            "exit_price": next_open_price,
            "pct_return": pct_return
        })

    overnight_df = pd.DataFrame(results)
    avg_return = overnight_df["pct_return"].mean() if not overnight_df.empty else None

    output = {
        "average_pct_return": avg_return,
        "daily_results": overnight_df.to_dict(orient="records")
    }

    with open(filename, "w") as f:
        json.dump(output, f, indent=4)

    print(f"Overnight bearish returns saved to {filename}")

def deviations(df):
    df["dev_high_norm"] = (df["high"] - df["open"]) / df["open"]
    df["dev_low_norm"]  = (df["open"] - df["low"]) / df["open"]

    avg_dev_high_norm = df["dev_high_norm"].mean()
    avg_dev_low_norm  = df["dev_low_norm"].mean()

    print("Average normalized deviation to high:", avg_dev_high_norm)
    print("Average normalized deviation to low:", avg_dev_low_norm)

def average_lowest_low_times(df, n_lows=5):
    df = df.copy()
    df["date"] = df.index.date
    df["time"] = df.index.time

    lowest_lows = []
    for day, group in df.groupby("date"):
        lows = group.nsmallest(n_lows, "low")
        for rank, row in enumerate(lows.itertuples(), 1):
            lowest_lows.append({
                "date": day,
                "time": row.Index.time(),
                "low": row.low,
                "rank": rank
            })

    lows_df = pd.DataFrame(lowest_lows)
    def minutes_since_open(t):
        return (t.hour - 9) * 60 + (t.minute - 30)

    lows_df["minutes_since_open"] = lows_df["time"].apply(minutes_since_open)

    avg_minutes = lows_df.groupby("rank")["minutes_since_open"].mean()
    avg_times = avg_minutes.apply(lambda m: f"{int((9*60 + 30 + m)//60):02d}:{int((9*60 + 30 + m)%60):02d}")
    print(pd.DataFrame({"avg_minutes_since_open": avg_minutes, "avg_time_of_day": avg_times}))

def average_highest_high_times(df, n_highs=5):
    df = df.copy()
    df["date"] = df.index.date
    df["time"] = df.index.time

    highest_highs = []
    for day, group in df.groupby("date"):
        highs = group.nlargest(n_highs, "high")
        for rank, row in enumerate(highs.itertuples(), 1):
            highest_highs.append({
                "date": day,
                "time": row.Index.time(),
                "high": row.high,
                "rank": rank
            })

    highs_df = pd.DataFrame(highest_highs)

    def minutes_since_open(t):
        return (t.hour - 9) * 60 + (t.minute - 30)

    highs_df["minutes_since_open"] = highs_df["time"].apply(minutes_since_open)

    avg_minutes = highs_df.groupby("rank")["minutes_since_open"].mean()
    avg_times = avg_minutes.apply(lambda m: f"{int((9*60 + 30 + m)//60):02d}:{int((9*60 + 30 + m)%60):02d}")
    print(pd.DataFrame({"avg_minutes_since_open": avg_minutes, "avg_time_of_day": avg_times}))

# for running data quick
from zoneinfo import ZoneInfo
def open_data(symbol, date="", start_time="9:30", end_time="16:00"):
        file_path = os.path.join("data", f"{symbol}_historical_data.csv")
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, utc=True)
        df.index = df.index.tz_convert(ZoneInfo("America/New_York"))

        if date != "":
            df = df[df.index.date == pd.to_datetime(date).date()]
        df = df.between_time(start_time, end_time)

        return df

df = open_data("TSLA")
average_highest_high_times(df, n_highs=5)
average_lowest_low_times(df, n_lows=5)
# HOD_probability(df, opening_minutes=120)
