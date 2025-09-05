import os

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

import pandas as pd

def HOD_probability(df_path):
    df = pd.read_csv(df_path, parse_dates=["timestamp"])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df.set_index('timestamp', inplace=True)
    df.index = df.index.tz_convert("America/New_York")
    df = df.between_time("09:30", "16:00")

    results = []

    for date, group in df.groupby(df.index.date):
        group = group.sort_index()
        opening_trend_window = group.between_time("09:30", "10:00")
        opening_trend_high = opening_trend_window["high"].max()
        group_after_trend = group[group.index > opening_trend_window.index[-1]]
        later_hod_val = group_after_trend["high"].max() if not group_after_trend.empty else None
        results.append({
            "date": date,
            "opening_trend_high": opening_trend_high,
            "later_hod": later_hod_val,
            "hod_after_trend": later_hod_val is not None and later_hod_val > opening_trend_high
        })

    daily_df = pd.DataFrame(results)
    p_hod_after_trend = daily_df["hod_after_trend"].mean()
    print("Probability later HOD > Opening Trend High (first 30 min):", round(p_hod_after_trend, 3))

def intraday_returns(df_path):
    df = pd.read_csv(df_path, parse_dates=["timestamp"])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df.set_index('timestamp', inplace=True)
    df.index = df.index.tz_convert("America/New_York")
    df = df.between_time("09:30", "16:00")

    results = []

    for date, group in df.groupby(df.index.date):
        group = group.sort_index()
        opening_trend_window = group.between_time("09:30", "10:00")
        price_at_10 = opening_trend_window.iloc[-1]["close"]
        group_after_trend = group[group.index > opening_trend_window.index[-1]]
        if not group_after_trend.empty:
            later_hod_val = group_after_trend["high"].max()
            later_lod_val = group_after_trend["low"].min()
            hod_return = (later_hod_val - price_at_10) / price_at_10 * 100
            lod_return = (later_lod_val - price_at_10) / price_at_10 * 100
        else:
            later_hod_val = None
            later_lod_val = None
            hod_return = None
            lod_return = None
        results.append({
            "date": date,
            "price_at_10": price_at_10,
            "later_hod": later_hod_val,
            "later_lod": later_lod_val,
            "hod_return_pct": hod_return,
            "lod_return_pct": lod_return
        })

    daily_df = pd.DataFrame(results)
    avg_hod_return = daily_df["hod_return_pct"].mean()
    avg_lod_return = daily_df["lod_return_pct"].mean()
    print("Average percent return to later HOD:", round(avg_hod_return, 2), "%")
    print("Average percent return to later LOD:", round(avg_lod_return, 2), "%")

def bearish_overnight_strategy(csv_path, open_window="09:30:00", stop_loss_pct=0.005, profit_target_pct=0.01, max_holding_days=5):
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df.set_index('timestamp', inplace=True)
    df.index = df.index.tz_convert("America/New_York")
    df = df.between_time("09:30", "16:00")

    trades = []

    # Track open trades for overnight holding
    open_trades = []

    for date, group in df.groupby(df.index.date):
        group = group.sort_index()
        open_price = group.iloc[0]["open"]

        # Check for bearish open
        if group.iloc[0]["close"] < group.iloc[0]["open"]:
            entry_price = group.iloc[0]["low"]  # buy at local minimum intraday
            trade = {
                "entry_date": date,
                "entry_price": entry_price,
                "holding_days": 0,
                "closed": False
            }

            # Intraday monitoring
            for idx, row in group.iterrows():
                if row["low"] <= entry_price * (1 - stop_loss_pct):
                    trade["exit_price"] = entry_price * (1 - stop_loss_pct)
                    trade["closed"] = True
                    break
                elif row["high"] >= entry_price * (1 + profit_target_pct):
                    trade["exit_price"] = entry_price * (1 + profit_target_pct)
                    trade["closed"] = True
                    break

            if not trade["closed"]:
                # Hold overnight
                trade["holding_days"] += 1
                open_trades.append(trade)
            else:
                trades.append(trade)

        # Update open trades from previous days
        still_open = []
        for t in open_trades:
            t["holding_days"] += 1
            # Check max holding days
            if t["holding_days"] > max_holding_days:
                t["exit_price"] = group.iloc[0]["open"]  # exit at next day open
                t["closed"] = True
                trades.append(t)
            else:
                # Check intraday price for profit/stop
                exited = False
                for idx, row in group.iterrows():
                    if row["low"] <= t["entry_price"] * (1 - stop_loss_pct):
                        t["exit_price"] = t["entry_price"] * (1 - stop_loss_pct)
                        t["closed"] = True
                        trades.append(t)
                        exited = True
                        break
                    elif row["high"] >= t["entry_price"] * (1 + profit_target_pct):
                        t["exit_price"] = t["entry_price"] * (1 + profit_target_pct)
                        t["closed"] = True
                        trades.append(t)
                        exited = True
                        break
                if not exited and not t["closed"]:
                    still_open.append(t)
        open_trades = still_open

    # Close any remaining open trades at last available price
    for t in open_trades:
        t["exit_price"] = df.iloc[-1]["close"]
        t["closed"] = True
        trades.append(t)

    trades_df = pd.DataFrame(trades)
    trades_df["return"] = (trades_df["exit_price"] - trades_df["entry_price"]) / trades_df["entry_price"]

    expected_return = trades_df["return"].mean()
    win_rate = (trades_df["return"] > 0).mean()
    avg_holding_days = trades_df["holding_days"].mean()

    print("Expected return per trade:", round(expected_return * 100, 3), "%")
    print("Win rate:", round(win_rate * 100, 2), "%")
    print("Average holding period (days):", round(avg_holding_days, 2))

def combined_strategy(csv_path, stop_loss_pct=0.005, profit_target_pct=0.01, max_holding_days=5):
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df.set_index('timestamp', inplace=True)
    df.index = df.index.tz_convert("America/New_York")
    df = df.between_time("09:30", "16:00")

    trades = []
    open_trades = []

    for date, group in df.groupby(df.index.date):
        group = group.sort_index()
        open_price = group.iloc[0]["open"]
        close_price = group.iloc[-1]["close"]

        # Determine bullish or bearish open
        if close_price > open_price:  # Bullish open
            entry_price = open_price
            hod = group["high"].max()
            exit_price = hod
            daily_return = (exit_price - entry_price) / entry_price
            trades.append({
                "date": date,
                "type": "bullish",
                "entry_price": entry_price,
                "exit_price": exit_price,
                "return": daily_return,
                "holding_days": 0
            })
        else:  # Bearish open
            entry_price = group.iloc[0]["low"]
            trade = {
                "entry_date": date,
                "entry_price": entry_price,
                "holding_days": 0,
                "type": "bearish",
                "closed": False
            }

            for idx, row in group.iterrows():
                if row["low"] <= entry_price * (1 - stop_loss_pct):
                    trade["exit_price"] = entry_price * (1 - stop_loss_pct)
                    trade["closed"] = True
                    break
                elif row["high"] >= entry_price * (1 + profit_target_pct):
                    trade["exit_price"] = entry_price * (1 + profit_target_pct)
                    trade["closed"] = True
                    break

            if not trade["closed"]:
                trade["holding_days"] += 1
                open_trades.append(trade)
            else:
                trade["return"] = (trade["exit_price"] - trade["entry_price"]) / trade["entry_price"]
                trades.append(trade)

        # Update open trades from previous days
        still_open = []
        for t in open_trades:
            t["holding_days"] += 1
            if t["holding_days"] > max_holding_days:
                t["exit_price"] = group.iloc[0]["open"]
                t["closed"] = True
                t["return"] = (t["exit_price"] - t["entry_price"]) / t["entry_price"]
                trades.append(t)
            else:
                exited = False
                for idx, row in group.iterrows():
                    if row["low"] <= t["entry_price"] * (1 - stop_loss_pct):
                        t["exit_price"] = t["entry_price"] * (1 - stop_loss_pct)
                        t["closed"] = True
                        t["return"] = (t["exit_price"] - t["entry_price"]) / t["entry_price"]
                        trades.append(t)
                        exited = True
                        break
                    elif row["high"] >= t["entry_price"] * (1 + profit_target_pct):
                        t["exit_price"] = t["entry_price"] * (1 + profit_target_pct)
                        t["closed"] = True
                        t["return"] = (t["exit_price"] - t["entry_price"]) / t["entry_price"]
                        trades.append(t)
                        exited = True
                        break
                if not exited and not t["closed"]:
                    still_open.append(t)
        open_trades = still_open

    # Close any remaining open trades at last available price
    for t in open_trades:
        t["exit_price"] = df.iloc[-1]["close"]
        t["closed"] = True
        t["return"] = (t["exit_price"] - t["entry_price"]) / t["entry_price"]
        trades.append(t)

    trades_df = pd.DataFrame(trades)
    overall_expected_return = trades_df["return"].mean()
    overall_win_rate = (trades_df["return"] > 0).mean()
    avg_holding_days = trades_df["holding_days"].mean()
    cumulative_returns = (1 + trades_df["return"]).cumprod() - 1

    print("Overall expected return per trade:", round(overall_expected_return * 100, 3), "%")
    print("Overall win rate:", round(overall_win_rate * 100, 2), "%")
    print("Average holding period (days):", round(avg_holding_days, 2))
    
    trades_df["cumulative_returns"] = cumulative_returns

# combined_strategy("data/GOOG_historical_data.csv", stop_loss_pct=0.005, profit_target_pct=0.01, max_holding_days=5)
# bearish_overnight_strategy("data/GOOG_historical_data.csv", stop_loss_pct=0.005, profit_target_pct=0.01)
# HOD_probability("data/GOOG_historical_data.csv")
# intraday_returns("data/GOOG_historical_data.csv")
