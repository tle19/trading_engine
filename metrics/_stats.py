from datetime import datetime
import numpy as np

class Stats:
    def __init__(self, symbol):
        self.symbol = symbol

        self.pess_trades = []
        self.opt_trades = []
        self.pess_pnls = []
        self.opt_pnls = []
        self.intraday_equity = []

        self.starting_cash = 0
        self.pess_cash = 0
        self.opt_cash = 0
        self.avg_cash = 0

        self.pess_win_rate = None
        self.opt_win_rate = None
        self.avg_win_rate = None
        self.total_trades = 0

        self.max_drawdown = 0
        self.max_win_streak = 0
        self.max_loss_streak = 0
        self.max_win_gain = 0
        self.max_loss_loss = 0

        self.gross_profit = 0
        self.gross_loss = 0
        self.net_profit = 0
        self.net_profit_pct = 0
        self.avg_change = 0
        self.profit_factor = np.inf

        self.start_date = None
        self.end_date = None
        self.duration = None
        self.equity_peak = 0

    def update_trade(self, pnl, mode):
        result = 1 if pnl > 0 else 0
        if mode == "pess":
            self.pess_trades.append(result)
            self.pess_pnls.append(pnl)
        elif mode == "opt":
            self.opt_trades.append(result)
            self.opt_pnls.append(pnl)

    def update_intraday_equity(self, equity):
        self.intraday_equity.append(equity)

    def update_cash_vals(self, cash, pess_cash, opt_cash, avg_cash):
        self.starting_cash = cash
        self.pess_cash = pess_cash
        self.opt_cash = opt_cash
        self.avg_cash = avg_cash

    def update_dates(self, start_date="", end_date=""):
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.duration = self.end_date - self.start_date if self.start_date and self.end_date else None

    def summary(self, mode=""):
        self.total_trades = len(self.pess_trades)
        self.equity_peak = max(self.intraday_equity) if self.intraday_equity else 0
        self._calculate_win_rates()
        self._calculate_drawdown()
        self._calculate_streaks()
        self._daily_pnls()
        
        if mode == "pess":
            cash, win_rate, name = self.pess_cash, self.pess_win_rate, "PESSIMISTIC"
        elif mode == "opt":
            cash, win_rate, name = self.opt_cash, self.opt_win_rate, "OPTIMISTIC"
        else:
            cash, win_rate, name = self.avg_cash, self.avg_win_rate, "BASE"
        
        print("-" * 40)
        print(f"\n{self.symbol} PERFORMANCE SUMMARY {name}")
        print("-" * 40)
        print(f"Start:                 {self.start_date}")
        print(f"End:                   {self.end_date}")
        print(f"Duration:              {self.duration}")
        print("-" * 40)
        print(f"Win Rate:              {win_rate:.2%}" if win_rate is not None else "  No trades")
        print(f"Equity Final:          ${cash:.2f}")
        print(f"Equity Peak:           ${self.equity_peak:.2f}")
        print(f"Max. Drawdown:         {self.max_drawdown:.2f}%")
        print(f"Consec Wins:           {self.max_win_streak} (${self.max_win_gain:.2f})")
        print(f"Consec Losses:         {self.max_loss_streak} (${self.max_loss_loss:.2f})")
        print(f"# of Trades:           {self.total_trades}")
        print(f"Gross Profit:          ${self.gross_profit:.2f}")
        print(f"Gross Loss:            $({self.gross_loss:.2f})")
        print(f"Net Profit:            ${self.net_profit:.2f} ({self.net_profit_pct:.2f}%)")
        print(f"Avg Δ per step:        ${self.avg_change:.2f}")
        print(f"Profit Factor:         {self.profit_factor:.2f}")

    def _calculate_win_rates(self):
        self.pess_win_rate = self._calculate_win_rate(self.pess_trades)
        self.opt_win_rate = self._calculate_win_rate(self.opt_trades)
        if self.pess_win_rate is not None and self.opt_win_rate is not None:
            self.avg_win_rate = (self.pess_win_rate + self.opt_win_rate) / 2
        else:
            self.avg_win_rate = None

    def _calculate_win_rate(self, trades):
        return sum(trades) / len(trades) if trades else None
    
    def _calculate_drawdown(self):
        if not self.intraday_equity:
            self.max_drawdown = 0
            return

        equity = np.array(self.intraday_equity)
        cum_max = np.maximum.accumulate(equity)
        drawdowns = (cum_max - equity) / cum_max
        self.max_drawdown = np.max(drawdowns) * 100
            
    def _calculate_streaks(self):
        if len(self.intraday_equity) < 2:
            self.max_win_streak = self.max_loss_streak = 0
            self.max_win_gain = self.max_loss_loss = 0
            return

        changes = np.diff(self.intraday_equity)

        # Wins
        win_mask = changes > 0
        if win_mask.any():
            # label consecutive True regions
            win_labels = np.cumsum(~win_mask)
            unique_labels = np.unique(win_labels[win_mask])
            win_streaks = np.array([np.sum(win_mask[win_labels == lbl]) for lbl in unique_labels])
            win_gains = np.array([np.sum(changes[win_labels == lbl]) for lbl in unique_labels])
            self.max_win_streak = win_streaks.max()
            self.max_win_gain = win_gains.max()
        else:
            self.max_win_streak = self.max_win_gain = 0

        # Losses
        loss_mask = changes < 0
        if loss_mask.any():
            loss_labels = np.cumsum(~loss_mask)
            unique_labels = np.unique(loss_labels[loss_mask])
            loss_streaks = np.array([np.sum(loss_mask[loss_labels == lbl]) for lbl in unique_labels])
            loss_losses = np.array([np.sum(changes[loss_labels == lbl]) for lbl in unique_labels])
            self.max_loss_streak = loss_streaks.max()
            self.max_loss_loss = loss_losses.min()
        else:
            self.max_loss_streak = self.max_loss_loss = 0
        
    def _daily_pnls(self):
        if len(self.intraday_equity) < 2:
            self.gross_profit = self.gross_loss = self.net_profit = self.avg_change = 0
            self.profit_factor = np.inf
            return

        changes = np.diff(self.intraday_equity)
        wins = changes[changes > 0]
        losses = changes[changes < 0]

        self.gross_profit = wins.sum()
        self.gross_loss = abs(losses.sum())
        self.net_profit = self.gross_profit - self.gross_loss
        self.net_profit_pct = (self.net_profit / self.starting_cash) * 100
        self.avg_change = np.mean(changes)
        self.profit_factor = abs(self.gross_profit / self.gross_loss) if self.gross_loss != 0 else np.inf

    def get_data_dict(self):
        profit = self.avg_cash - self.starting_cash
        profit_pct = (profit / self.starting_cash) * 100 if self.starting_cash else 0

        data = {
            "Equity Final [$]": float(self.avg_cash),
            "Return [$]": profit,
            "Return [%]": profit_pct,
            "Win Rate [%]": float(self.avg_win_rate * 100) if self.avg_win_rate is not None else None,
            "Equity Peak [$]": float(self.equity_peak),
            "Max Drawdown [%]": float(self.max_drawdown),
            "Consec Wins": int(self.max_win_streak),
            "Max Win Gain [$]": float(self.max_win_gain),
            "Consec Losses": int(self.max_loss_streak),
            "Max Loss [$]": float(self.max_loss_loss),
            "# Trades": int(self.total_trades),
            "Gross Profit [$]": float(self.gross_profit),
            "Gross Loss [$]": float(self.gross_loss),
            "Net Profit [$]": float(self.net_profit),
            "Avg Δ per step [$]": float(self.avg_change),
            "Profit Factor": float(self.profit_factor)
        }
        return data