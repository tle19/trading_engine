from datetime import datetime
from collections import defaultdict
import numpy as np

class Stats:
    def __init__(self, symbol):
        self.symbol = symbol

        self.trades = []
        self.trade_pnls = []
        self.intraday_equity = {}

        self.starting_cash = 0
        self.curr_cash = 0
        self.equity_peak = 0

        self.win_rate = None
        self.daily_win_rate = None
        self.total_trades = 0

        self.max_drawdown = 0
        self.win_streak = 0
        self.loss_streak = 0
        self.max_gain_streak = 0
        self.max_loss_streak = 0

        self.gross_profit = 0
        self.gross_loss = 0
        self.net_profit = 0
        self.net_profit_pct = 0
        self.avg_change = 0
        self.profit_factor = None
        self.sharpe_ratio = None

        self.daily_pnls = []
        self.best_day = self.worst_day = self.avg_day = 0
        self.day_win_streak = self.day_loss_streak = 0
        self.max_day_gain_streak = self.max_day_loss_streak = 0

        self.start_date = None
        self.end_date = None
        self.duration = None
        
    def update_trade(self, pnl):
        result = 1 if pnl > 0 else 0
        self.trades.append(result)
        self.trade_pnls.append(pnl)
    
    def update_intraday_equity(self, ts, equity):
        self.intraday_equity[ts] = equity

    def update_dates(self, start_date: str, end_date: str):
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.duration = self.end_date - self.start_date if self.start_date and self.end_date else None

    def summary(self):
        self.total_trades = len(self.trades)
        intraday_equity = list(self.intraday_equity.values())
        self.starting_cash = intraday_equity[0]
        self.curr_cash = intraday_equity[-1]
        self._calculate_drawdown(intraday_equity)
        self._calculate_streaks(intraday_equity) # fix, this is incorrect
        self._calculate_pnls(intraday_equity)
        self._calculate_daily_pnls()
        self._calculate_win_rates()
        self._calculate_sharpe_ratio()

        print("=" * 50)
        print(f"{self.symbol} PERFORMANCE SUMMARY")
        print("=" * 50)
        print(f"Start:                      {self.start_date}")
        print(f"End:                        {self.end_date}")
        print(f"Duration:                   {self.duration}")
        print("-" * 50)

        # --- Equity / Performance ---
        print(f"Final Equity:               ${self.curr_cash:.2f}")
        print(f"Equity Peak:                ${self.equity_peak:.2f}")
        print(f"Max Drawdown:               {self.max_drawdown:.2f}%")
        print(f"Win Rate:                   {self.win_rate:.2%}" if self.win_rate is not None else "No trades")
        print(f"Daily Win Rate:             {self.daily_win_rate:.2%}" if self.daily_win_rate is not None else "No trades")
        print("-" * 50)

        # --- Trade statistics ---
        print(f"Total Trades:               {self.total_trades}")
        print(f"Consecutive Wins:           {self.win_streak} (${self.max_gain_streak:.2f})")
        print(f"Consecutive Losses:         {self.loss_streak} (${self.max_loss_streak:.2f})")
        print("-" * 50)

         # --- PnL / Risk stats ---
        print(f"Gross Profit:               ${self.gross_profit:.2f}")
        print(f"Gross Loss:                 ${-self.gross_loss:.2f}")
        print(f"Net Profit:                 ${self.net_profit:.2f} ({self.net_profit_pct:.2f}%)")
        print(f"Avg Δ per step:             ${self.avg_change:.2f}")
        print(f"Profit Factor:              {self.profit_factor:.2f}")
        print(f"Sharpe Ratio:               {self.sharpe_ratio:.2f}")
        print("-" * 50)

        # --- Daily stats ---
        print(f"Best Daily PnL:             ${self.best_day:.2f}")
        print(f"Worst Daily PnL:            ${self.worst_day:.2f}")
        print(f"Average Daily PnL:          ${self.avg_day:.2f}")
        print(f"Consecutive Daily Wins:     {self.day_win_streak} (${self.max_day_gain_streak:.2f})")
        print(f"Consecutive Daily Losses:   {self.day_loss_streak} (${self.max_day_loss_streak:.2f})")
        print("-" * 50)

    def _calculate_win_rates(self):
        self.win_rate = np.mean(self.trades)

        daily_pnls_array = np.array(self.daily_pnls)
        win_mask = (daily_pnls_array > 0).astype(int)
        self.daily_win_rate = np.mean(win_mask)

    def _calculate_drawdown(self, intraday_equity):
        cum_max = np.maximum.accumulate(intraday_equity)
        drawdowns = (cum_max - intraday_equity) / cum_max
        self.max_drawdown = np.max(drawdowns) * 100

    def _calculate_streaks(self, intraday_equity):
        changes = np.diff(intraday_equity)

        cur_wins = cur_losses = 0
        cur_gain = cur_loss = 0.0

        for ch in changes:
            if ch > 0:
                cur_wins += 1
                cur_gain += ch
                cur_losses = cur_loss = 0
            elif ch < 0:
                cur_losses += 1
                cur_loss += ch
                cur_wins = cur_gain = 0
            else:
                cur_wins = cur_losses = 0
                cur_gain = cur_loss = 0

            self.win_streak = max(self.win_streak, cur_wins)
            self.loss_streak = max(self.loss_streak, cur_losses)
            self.max_gain_streak = max(self.max_gain_streak, cur_gain)
            self.max_loss_streak = min(self.max_loss_streak, cur_loss)

    def _calculate_pnls(self, intraday_equity):
        changes = np.diff(intraday_equity)
        wins = changes[changes > 0]
        losses = changes[changes < 0]

        self.equity_peak = max(intraday_equity) if intraday_equity else 0
        self.gross_profit = wins.sum()
        self.gross_loss = abs(losses.sum())
        self.net_profit = self.gross_profit - self.gross_loss
        self.net_profit_pct = (self.net_profit / self.starting_cash) * 100
        self.avg_change = np.mean(changes)
        self.profit_factor = abs(self.gross_profit / self.gross_loss) if self.gross_loss != 0 else np.inf
    
    def _calculate_daily_pnls(self):
        daily_equity = defaultdict(list)
        for ts, eq in self.intraday_equity.items():
            daily_equity[ts.date()].append((ts, eq))

        for day, values in daily_equity.items():
            values.sort(key=lambda x: x[0])
            first_eq = values[0][1]
            last_eq = values[-1][1]
            self.daily_pnls.append(last_eq - first_eq)

        self.best_day = max(self.daily_pnls)
        self.worst_day = min(self.daily_pnls)
        self.avg_day = np.mean(self.daily_pnls)

        current_win = current_loss = 0
        current_win_sum = current_loss_sum = 0

        for pnl in self.daily_pnls:
            if pnl > 0:
                current_win += 1
                current_win_sum += pnl
                current_loss = 0
                current_loss_sum = 0

                if current_win > self.day_win_streak:
                    self.day_win_streak = current_win
                    self.max_day_gain_streak = current_win_sum
                elif current_win == self.day_win_streak:
                    self.max_day_gain_streak = max(self.max_day_gain_streak, current_win_sum)

            elif pnl < 0:
                current_loss += 1
                current_loss_sum += pnl
                current_win = 0
                current_win_sum = 0

                if current_loss > self.day_loss_streak:
                    self.day_loss_streak = current_loss
                    self.max_day_loss_streak = current_loss_sum
                elif current_loss == self.day_loss_streak:
                    self.max_day_loss_streak = min(self.max_day_loss_streak, current_loss_sum)

            else:
                current_win = current_loss = 0
                current_win_sum = current_loss_sum = 0

    def _calculate_sharpe_ratio(self, risk_free_rate=0.05):
        daily_returns = np.array(self.daily_pnls) / self.starting_cash
        mean = np.mean(daily_returns)
        std = np.std(daily_returns, ddof=1)

        daily_rf = (1 + risk_free_rate) ** (1/252) - 1
        excess_daily_return = mean - daily_rf

        self.sharpe_ratio = np.sqrt(252) * (excess_daily_return / std)
    
    def get_time_loss(self):
        # find time of day where loss is irrecoverable, set loss there
        # dont want to stop out day if loss is in very beggining of day (could recover)
        raise NotImplementedError
    
    def get_data_dict(self):
        data = {
            # --- General info ---
            "Symbol": self.symbol,
            "Start": str(self.start_date),
            "End": str(self.end_date),
            "Duration": str(self.duration),

            # --- Equity / Performance ---
            "Final Equity": float(self.curr_cash),
            "Equity Peak": float(self.equity_peak),
            "Max Drawdown": float(self.max_drawdown),
            "Win Rate": float(self.win_rate),
            "Daily Win Rate": float(self.daily_win_rate),

            # --- Trade statistics ---
            "Total Trades": int(self.total_trades),
            "Consecutive Wins": int(self.win_streak),
            "Max Win Gain": float(self.max_gain_streak),
            "Consecutive Losses": int(self.loss_streak),
            "Max Loss": float(self.max_loss_streak),

            # --- PnL / Risk stats ---
            "Gross Profit": float(self.gross_profit),
            "Gross Loss": float(self.gross_loss),
            "Net Profit": float(self.net_profit),
            "Net Profit %": float(self.net_profit_pct),
            "Avg Δ per step": float(self.avg_change),
            "Profit Factor": float(self.profit_factor),

            # --- Daily stats ---
            "Best Daily PnL": float(self.best_day),
            "Worst Daily PnL": float(self.worst_day),
            "Average Daily PnL": float(self.avg_day),
            "Consecutive Daily Wins": int(self.day_win_streak),
            "Max Daily Gain": float(self.max_day_gain_streak),
            "Consecutive Daily Losses": int(self.day_loss_streak),
            "Max Daily Loss": float(self.max_day_loss_streak)
        }

        return data
    