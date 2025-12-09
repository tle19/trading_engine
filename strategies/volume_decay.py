from collections import deque

from strategies import Strategy, RiskManager
from utils import *

class VolumeDecay(Strategy):
    def __init__(self, symbol, fast_window=14, slow_window=28, rsi_period=14,
                 rsi_thresh=2, vol_decay_factor=2, vol_accel_factor=1.1,
                 stop_loss=0.01, take_profit=0.01, position_size=1.0,
                 target=0.01, loss=-0.03):
        super().__init__(symbol, stop_loss, take_profit, position_size)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.rsi_period = rsi_period
        self.rsi_thresh = rsi_thresh
        self.vol_decay_factor = vol_decay_factor
        self.vol_accel_factor = vol_accel_factor

        self.activated = False
        self.lookback = 0
        self.vol_anchor = 0
        self.rsi_anchor = None
        self.rolling_rsi = deque(maxlen=20)
        self.rolling_vol = deque(maxlen=2)

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()

        vol = self.compute_volume_oscillator(self.volumes, self.fast_window, self.slow_window)
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        
        if self.rolling_rsi and self.rolling_vol:
            rsi_ma = sum(self.rolling_rsi) / len(self.rolling_rsi)
        self.rolling_rsi.append(rsi)
        self.rolling_vol.append(vol)
        
        status = self.check_status()
        if status is not None:
            return status
        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
            return None

        signal = None
        if self.position is None and self.activated:
            signal = self.enter_trade(vol, rsi, rsi_ma)
        # elif self.position is not None and self.activated:
        #     signal = self.exit_trade(vol, rsi, rsi_ma)
        return signal

    def enter_trade(self, vol, rsi, rsi_ma):
        if vol > self.vol_anchor:
            self.vol_anchor = vol
            self.rsi_anchor = rsi
            self.lookback = 0
        elif vol < 0:
            self.vol_anchor = 0
        self.lookback += 1
        vol_cond = vol > 0 and self.vol_anchor > 0.1 and vol < self.vol_anchor / self.vol_decay_factor

        if vol_cond and rsi > self.rsi_anchor + (self.rsi_thresh * self.lookback):
            signal = self.buy()
            swing_point = self.compute_swing(mode="low", window=2, lookback=self.lookback)
            upper_band, lower_band  = self.donchian_channel(self.lookback)
            diff = upper_band - lower_band
            self.stop_price = round(swing_point * (1 - 0.001), 2)
            # self.stop_price = round(((self.low + self.high) / 2) - diff, 2)
            self.profit_price = round(((self.low + self.high) / 2) + diff, 2)
            print(f"{self.ts} ENTRY (L): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
            self.vol_anchor = 0
            self.rsi_anchor = None
            return signal
        if vol_cond and rsi < self.rsi_anchor - (self.rsi_thresh * self.lookback):
            signal = self.sell()
            swing_point = self.compute_swing(mode="high", window=2, lookback=self.lookback)
            upper_band, lower_band  = self.donchian_channel(self.lookback)
            diff = upper_band - lower_band
            self.stop_price = round(swing_point * (1 + 0.001), 2)
            # self.stop_price = round(((self.low + self.high) / 2) + diff, 2)
            self.profit_price = round(((self.low + self.high) / 2) - diff, 2)
            print(f"{self.ts} ENTRY (S): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
            self.vol_anchor = 0
            self.rsi_anchor = None
            return signal

    def exit_trade(self, vol, rsi, rsi_ma):
        if vol < self.vol_anchor:
            self.vol_anchor = vol
        vol_cond = vol > self.vol_anchor
        
        if self.position == "long" and vol_cond and self.close > self.entry_price:
            self.stop_price = round(self.close, 2)
            self.vol_anchor = 0
            # print(f"{self.ts} EXIT (L): {self.entry_price}, STOP: {self.stop_price}")
            return self.sell()
        if self.position == "short" and vol_cond and self.close < self.entry_price:
            self.stop_price = round(self.close, 2)
            self.vol_anchor = 0
            # print(f"{self.ts} EXIT (S): {self.entry_price}, STOP: {self.stop_price}")
            return self.buy()
      
    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.lookback = 0
            self.vol_anchor = 0
            self.rsi_anchor = None
            self.rolling_rsi = deque(maxlen=20)
            self.rolling_vol = deque(maxlen=2)
      
    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.fast_window,
                self.slow_window,
                self.rsi_period,
            ) + 1
            self.activated = len(self.prices) > required_data

    # def donchian_channel(self, period):
    #     opens = self.opens[-period:]
    #     closes = self.prices[-period:]
    #     upper_band = max(max(opens), max(closes))
    #     lower_band = min(min(opens), min(closes))
    #     return upper_band, lower_band
        