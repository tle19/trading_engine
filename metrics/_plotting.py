import matplotlib.pyplot as plt
import pandas as pd

class Plotting:
    def __init__(self, symbol):
        self.symbol = symbol
    
    def plot_equity(self, equity_list, symbol="", start_date="", end_date=""):
        equity_values = list(chain.from_iterable(equity_list))
        df = pd.DataFrame({"equity": equity_values})
        num_points = len(df)

        plt.figure(figsize=(14,6))
        plt.plot(df.index, df["equity"], label='Strategy', color='blue')

        months = pd.date_range(start=start_date, end=end_date, freq='MS')
        if len(months) > 12:
            step = int(np.ceil(len(months) / 12))
            months = months[::step]

        month_positions = np.linspace(0, num_points-1, len(months), dtype=int)
        plt.xticks(month_positions, [m.strftime('%b %Y') for m in months], rotation=45)

        plt.xlabel("Date")
        plt.ylabel("Portfolio Value")
        plt.title(f"{symbol} Strategy Equity ({start_date} to {end_date})")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()