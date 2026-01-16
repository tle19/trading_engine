import numpy as np
import pandas as pd

class Stats:
    def __init__(self, symbol):
        self.symbol = symbol

        self.trade_history = []
        self.intraday_equity = {}
        
        self.daily_pnls = []

        self.start_date = None
        self.end_date = None
        self.duration = None

        self.equity_initial = 0
        self.equity_final = 0
        self.gross_profit = 0
        self.gross_loss = 0
        self.net_profit = 0
        self.net_profit_pct = 0

        self.win_rate = 0
        self.win_streak = 0
        self.loss_streak = 0
        self.max_gain_streak = 0
        self.max_loss_streak = 0

        self.max_drawdown = 0
        self.sharpe_ratio = 0
        self.cagr = 0
        self.profit_factor = 0

        self.total_trades = 0
        self.avg_market_exposure = 0
        self.avg_trade_duration = 0
        self.time_in_market = 0

        self.daily_win_rate = 0
        self.avg_day = 0
        self.best_day = 0
        self.worst_day = 0
        self.day_win_streak = 0
        self.day_loss_streak = 0
        self.max_day_gain_streak = 0
        self.max_day_loss_streak = 0

    def update_data(self, trade_history, intraday_equity):
        self.trade_history = trade_history
        self.intraday_equity = [v for k, v in sorted(intraday_equity.items())]
        self._update_dates(intraday_equity)

    def summary(self):
        self._calculate_pnls()
        self._calculate_win_rates()
        self._calculate_streaks()
        self._calculate_daily_streaks()
        self._calculate_drawdown()
        self._calculate_sharpe_ratio()
        self._calculate_cagr()
        self._calculate_trade_behavior()
        
        print("=" * 50)
        print(f"{self.symbol} PERFORMANCE SUMMARY")
        print("=" * 50)
        print(f"Start:                      {self.start_date.date()}")
        print(f"End:                        {self.end_date.date()}")
        print(f"Duration:                   {self.duration.days} days")
        print("-" * 50)

        # --- Equity ---
        print(f"Equity Initial:             ${self.equity_initial:.2f}")
        print(f"Equity Final:               ${self.equity_final:.2f}")
        print(f"Net Profit:                 ${self.net_profit:.2f} ({self.net_profit_pct:.2%})")
        print(f"Gross Profit:               ${self.gross_profit:.2f}")
        print(f"Gross Loss:                 ${self.gross_loss:.2f}")
        print("-" * 50)

        # --- Trade Performance ---
        print(f"Win Rate:                   {self.win_rate:.2%}")
        print(f"Consecutive Wins:           {self.win_streak} (${self.max_gain_streak:.2f})")
        print(f"Consecutive Losses:         {self.loss_streak} (${self.max_loss_streak:.2f})")
        print("-" * 50)

         # --- Risk-Adjusted Performance ---
        print(f"Max Drawdown:               {self.max_drawdown:.2%}")
        print(f"Sharpe Ratio:               {self.sharpe_ratio:.2f}")
        print(f"CAGR:                       {self.cagr:.2%}")
        print(f"Profit Factor:              {self.profit_factor:.2f}")
        print("-" * 50)

        # --- Trade Behavior ---
        print(f"Total Trades:               {self.total_trades}")
        print(f"Average Trade Duration:     {self.avg_trade_duration:.2f} minutes")
        print(f"Average Market Exposure:    {self.avg_market_exposure:.2%}")
        print(f"Time in Market:             {self.time_in_market:.2%}")
        print("-" * 50)

        # --- Daily Performance ---
        print(f"Daily Win Rate:             {self.daily_win_rate:.2%}")
        print(f"Average Daily PnL:          ${self.avg_day:.2f}")
        print(f"Best Daily PnL:             ${self.best_day:.2f}")
        print(f"Worst Daily PnL:            ${self.worst_day:.2f}")
        print(f"Consecutive Daily Wins:     {self.day_win_streak} (${self.max_day_gain_streak:.2f})")
        print(f"Consecutive Daily Losses:   {self.day_loss_streak} (${self.max_day_loss_streak:.2f})")
        print("-" * 50)

    def _update_dates(self, intraday_equity):
        dates = sorted(intraday_equity)
        self.start_date = dates[0]
        self.end_date = dates[-1]
        self.duration = self.end_date - self.start_date

    def _calculate_pnls(self):
        self.equity_initial = self.intraday_equity[0]
        self.equity_final = self.intraday_equity[-1]
        self.gross_profit = sum(trade["pnl"] for trade in self.trade_history if trade["pnl"] > 0)
        self.gross_loss = sum(-trade["pnl"] for trade in self.trade_history if trade["pnl"] < 0)
        self.net_profit = self.gross_profit - self.gross_loss
        self.net_profit_pct = (self.net_profit / self.equity_initial)
        self.profit_factor = abs(self.gross_profit / self.gross_loss) if self.gross_loss != 0 else np.inf

        daily_dict = {}
        for trade in self.trade_history:
            date = trade["entry_time"].split("T")[0]
            daily_dict[date] = daily_dict.get(date, 0.0) + trade["pnl"]
        self.daily_pnls = list(daily_dict.values())
         
    def _calculate_win_rates(self):
        wins = [1 if trade["pnl"] > 0 else 0 for trade in self.trade_history]
        self.win_rate = np.mean(wins)

        daily_pnls_array = np.array(self.daily_pnls)
        win_mask = (daily_pnls_array > 0).astype(int)
        self.daily_win_rate = np.mean(win_mask)

    def _calculate_streaks(self):
        cur_wins = cur_losses = 0
        cur_gain = cur_loss = 0

        for trade in self.trade_history:
            pnl = trade["pnl"]

            if pnl > 0:
                cur_wins += 1
                cur_gain += pnl
                cur_losses = cur_loss = 0
            elif pnl < 0:
                cur_losses += 1
                cur_loss += pnl
                cur_wins = cur_gain = 0
            else:
                cur_wins = cur_losses = 0
                cur_gain = cur_loss = 0
            
            self.win_streak = max(self.win_streak, cur_wins)
            self.loss_streak = max(self.loss_streak, cur_losses)
            self.max_gain_streak = max(self.max_gain_streak, cur_gain)
            self.max_loss_streak = min(self.max_loss_streak, cur_loss)

    def _calculate_daily_streaks(self):
        self.best_day = max(self.daily_pnls)
        self.worst_day = min(self.daily_pnls)
        self.avg_day = np.mean(self.daily_pnls)

        cur_wins = cur_losses = 0
        cur_gain = cur_loss = 0

        for pnl in self.daily_pnls:
            if pnl > 0:
                cur_wins += 1
                cur_gain += pnl
                cur_losses = cur_loss = 0
            elif pnl < 0:
                cur_losses += 1
                cur_loss += pnl
                cur_wins = cur_gain = 0
            else:
                cur_wins = cur_losses = 0
                cur_gain = cur_loss = 0
            
            self.day_win_streak = max(self.day_win_streak, cur_wins)
            self.day_loss_streak = max(self.day_loss_streak, cur_losses)
            self.max_day_gain_streak = max(self.max_day_gain_streak, cur_gain)
            self.max_day_loss_streak = min(self.max_day_loss_streak, cur_loss)

    def _calculate_drawdown(self):
        cum_max = np.maximum.accumulate(self.intraday_equity)
        drawdowns = (cum_max - self.intraday_equity) / cum_max
        self.max_drawdown = np.max(drawdowns)

    def _calculate_sharpe_ratio(self, risk_free_rate=0.05):
        daily_returns = np.array(self.daily_pnls) / self.equity_initial
        mean = np.mean(daily_returns)
        std = np.std(daily_returns, ddof=1)

        daily_rf = (1 + risk_free_rate) ** (1/252) - 1
        excess_daily_return = mean - daily_rf

        self.sharpe_ratio = np.sqrt(252) * (excess_daily_return / std)

    def _calculate_cagr(self):
        years = self.duration.days / 365.25
        if years <= 0:
            return 0.0
        self.cagr = (self.equity_final / self.equity_initial) ** (1 / years) - 1
    
    def _calculate_trade_behavior(self):
        total_seconds = self.duration.total_seconds()
        total_duration = 0
        time_weighted_exposure = 0
        for trade in self.trade_history:
            entry_time = pd.Timestamp(trade["entry_time"])
            exit_time = pd.Timestamp(trade["exit_time"])
            duration_sec = (exit_time - entry_time).total_seconds()

            total_duration += duration_sec
            time_weighted_exposure += duration_sec * trade["position_size"]

        self.total_trades = len(self.trade_history)
        self.avg_trade_duration = total_duration / 60 / self.total_trades
        self.avg_market_exposure = time_weighted_exposure / total_seconds
        self.time_in_market = total_duration / total_seconds
    
    def get_data_dict(self):
        data = {
            # --- General Info ---
            "Symbol": self.symbol,
            "Start": str(self.start_date),
            "End": str(self.end_date),
            "Duration": str(self.duration),

            # --- Equity & Outcome ---
            "Equity Initial": float(self.equity_initial),
            "Equity Final": float(self.equity_final),
            "Net Profit": float(self.net_profit),
            "Net Profit %": float(self.net_profit_pct),
            "Gross Profit": float(self.gross_profit),
            "Gross Loss": float(self.gross_loss),

            # --- Trade Performance ---
            "Win Rate": float(self.win_rate),
            "Consecutive Wins": int(self.win_streak),
            "Max Gain": float(self.max_gain_streak),
            "Consecutive Losses": int(self.loss_streak),
            "Max Loss": float(self.max_loss_streak),

            # --- Risk-Adjusted Performance ---
            "Max Drawdown": float(self.max_drawdown),
            "Sharpe Ratio": float(self.sharpe_ratio),
            "CAGR": float(self.cagr),
            "Profit Factor": float(self.profit_factor),

            # --- Trade Behavior ---
            "Total Trades": int(self.total_trades),
            "Average Trade Duration": float(self.avg_trade_duration),
            "Average Market Exposure": float(self.avg_market_exposure),
            "Time in Market": float(self.time_in_market),

            # --- Daily Performance ---
            "Daily Win Rate": float(self.daily_win_rate),
            "Average Daily PnL": float(self.avg_day),
            "Best Daily PnL": float(self.best_day),
            "Worst Daily PnL": float(self.worst_day),
            "Consecutive Daily Wins": int(self.day_win_streak),
            "Max Daily Gain": float(self.max_day_gain_streak),
            "Consecutive Daily Losses": int(self.day_loss_streak),
            "Max Daily Loss": float(self.max_day_loss_streak)
        }

        return data