import os
import numpy as np

class Stats:
    def __init__(self, symbol):
        self.pess_trades = []
        self.opt_trades = []
        self.symbol = symbol
        self.intraday_equity = []
        self.starting_cash = 0
        self.current_cash = 0
        self.max_drawdown = 0
    
    def summary(initial_cash, pess_cash, opt_cash, avg_cash, 
                pess_win_rates, opt_win_rates, avg_win_rates, total_trades, equity_list):

        avg_pess_win_rate = calculate_win_rate(pess_win_rates)
        avg_opt_win_rate = calculate_win_rate(opt_win_rates)
        avg_avg_win_rate = calculate_win_rate(avg_win_rates)

        for scenario, cash, win_rate in [("Pessimistic", pess_cash, avg_pess_win_rate),
                                        ("Optimistic", opt_cash, avg_opt_win_rate),
                                        ("Average", avg_cash, avg_avg_win_rate)]:
            profit = cash - initial_cash
            profit_pct = (profit / initial_cash) * 100
            print(f"{scenario} Scenario:")
            print("  Initial Cash:", round(initial_cash, 2))
            print("  Final Cash:", round(cash, 2))
            print("  Net Profit ($):", round(profit, 2))
            print("  Profit %:", round(profit_pct, 2), "%")
            print(f"  Win Rate: {win_rate:.2%}" if win_rate is not None else "  No trades")
            print()

        print("Total Trades:", total_trades)
        max_drawdown_pct = calculate_drawdown(equity_list)
        calculate_streaks(equity_list)
        print()
        daily_pnls(equity_list)
        print()

        return avg_cash, avg_avg_win_rate, max_drawdown_pct

    def calculate_win_rate(win_rates):
        # pess_win_rate = pess_wins / total_trades if total_trades else None
        # opt_win_rate = opt_wins / total_trades if total_trades else None
        avg_win_rate = (
            sum(w for w in win_rates if w is not None) / len([w for w in win_rates if w is not None])
            if any(w is not None for w in win_rates) else None
        )

        return avg_win_rate

    def calculate_drawdown(equity_list):
        max_drawdowns_per_day = []

        for intraday_equity in equity_list:
            if not intraday_equity:
                continue  # skip empty days

            cum_max = intraday_equity[0]
            max_dd = 0.0

            for eq in intraday_equity:
                if eq > cum_max:
                    cum_max = eq
                drawdown = (cum_max - eq) / cum_max
                if drawdown > max_dd:
                    max_dd = drawdown

            max_drawdowns_per_day.append(max_dd * 100)

        max_drawdown_pct = max(max_drawdowns_per_day) if max_drawdowns_per_day else None

        print("Max Drawdown:", round(max_drawdown_pct, 2), "%")
        return max_drawdown_pct

    def calculate_streaks(equity_list):
        win_streak = 0
        loss_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        curr_win_loss = 0
        curr_loss_loss = 0
        max_win_gain = 0
        max_loss_loss_amount = 0

        for day in equity_list:
            daily_pnl = day[-1] - day[0]

            if daily_pnl > 0:
                win_streak += 1
                curr_win_loss += daily_pnl
                loss_streak = 0
                curr_loss_loss = 0
            elif daily_pnl < 0:
                loss_streak += 1
                curr_loss_loss += daily_pnl
                win_streak = 0
                curr_win_loss = 0
            else:
                win_streak = 0
                loss_streak = 0
                curr_win_loss = 0
                curr_loss_loss = 0

            if win_streak > max_win_streak:
                max_win_streak = win_streak
                max_win_gain = curr_win_loss

            if loss_streak > max_loss_streak:
                max_loss_streak = loss_streak
                max_loss_loss_amount = curr_loss_loss
        
        print(f"Consecutive Wins ($): {max_win_streak} ({max_win_gain})")
        print(f"Consecutive Losses ($): {max_loss_streak} ({max_loss_loss_amount})")
        return max_win_streak, max_loss_streak, max_win_gain, max_loss_loss_amount

    def daily_pnls(equity_list):
        daily_pnls = [day[-1] - day[0] for day in equity_list]

        total_days = len(daily_pnls)
        wins = [p for p in daily_pnls if p > 0]
        losses = [p for p in daily_pnls if p < 0]

        gross_profit = sum(wins)
        gross_loss = sum(losses)
        net_profit = gross_profit + gross_loss

        profit_per_day = np.mean(daily_pnls) if total_days > 0 else 0
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else np.inf

        print(f"Total Days: {total_days}")
        print(f"Gross Profit: {gross_profit:.2f}")
        print(f"Gross Loss: {gross_loss:.2f}")
        print(f"Net Profit: {net_profit:.2f}")
        print(f"Profit per Day: {profit_per_day:.2f}")
        print(f"Average Winning Day: {avg_win:.2f}")
        print(f"Average Losing Day: {avg_loss:.2f}")
        print(f"Profit Factor: {profit_factor:.2f}")

