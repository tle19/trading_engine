from collections import deque

from strategies import Strategy, RiskManager
from utils import *

class VolumeDecayIndicator(Strategy):
    def __init__(self, symbol, fast_window=14, slow_window=28,
                 rsi_period=14, rsi_thresh=2, vol_decay_factor=2, vol_accel_factor=1.1,
                 stop_loss=0.001, take_profit=0.03, position_size=1.0,
                 target=0.01, loss=-0.03):
        super().__init__(symbol, stop_loss, take_profit, position_size)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.rsi_period = rsi_period
        self.rsi_thresh = rsi_thresh
        self.vol_decay_factor = vol_decay_factor
        self.vol_accel_factor = vol_accel_factor

        self.activated = False
        self.vol_anchor_high = 0
        self.vol_anchor_low = 0
        self.rolling_rsi = deque(maxlen=5)
        self.rolling_vol = deque(maxlen=2)

        self.risk_manager = RiskManager(pnl_target=target, pnl_loss=loss)

    def generate_signal(self, row):
        self.update(row)
        self.reset_data()
        self.reset_indicators()
        self.minimum_computations()

        # self.risk_manager.check_daily_target()
        # self.risk_manager.check_daily_stop()
        # if self.risk_manager.day_pause():
        #     return None

        vol = self.compute_volume_oscillator(self.volumes, self.fast_window, self.slow_window)
        rsi = self.compute_rsi(self.prices, self.rsi_period)
        
        if self.rolling_rsi and self.rolling_vol:
            #ema isntead?
            rsi_ma = sum(self.rolling_rsi) / len(self.rolling_rsi)
            vol_ma = sum(self.rolling_vol) / len(self.rolling_vol)
        self.rolling_rsi.append(rsi)
        self.rolling_vol.append(vol)
        
        status = self.check_status()
        if status is not None:
            return status
        if not self.trade_window((9, 30), (15, 00)) and self.position is None:
            return None

        signal = None
        if self.position is None and self.activated:
            signal = self.enter_trade(vol, rsi, rsi_ma, vol_ma)
        elif self.position is not None and self.activated:
            signal = self.exit_trade(vol, rsi, rsi_ma, vol_ma)
        return signal

    def enter_trade(self, vol, rsi, rsi_ma, vol_ma):
        if vol > self.vol_anchor_high:
            self.vol_anchor_high = vol
        elif vol < 0:
            self.vol_anchor_high = 0
        vol_cond = vol < self.vol_anchor_high / self.vol_decay_factor and vol > 0

        if vol_cond and rsi > rsi_ma + self.rsi_thresh and rsi > self.rolling_rsi[0] + self.rsi_thresh:
            signal = self.buy()
            # swing_point = self.compute_swing(mode="low")
            # self.stop_price = round(swing_point * (1 - self.stop_loss), 2)
            self.vol_anchor_high = 0
            # print(f"{self.ts} ENTRY (L): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
            return signal
        if vol_cond and rsi < rsi_ma - self.rsi_thresh and rsi < self.rolling_rsi[0] - self.rsi_thresh:
            signal = self.sell()
            # swing_point = self.compute_swing(mode="high")
            # self.stop_price = round(swing_point * (1 + self.stop_loss), 2)
            self.vol_anchor_high = 0
            # print(f"{self.ts} ENTRY (S): {self.entry_price}, STOP: {self.stop_price}, PROFIT: {self.profit_price}")
            return signal
        
    def exit_trade(self, vol, rsi, rsi_ma, vol_ma):
        if vol < self.vol_anchor_low:
            self.vol_anchor_low = vol
        vol_cond_low = vol > self.vol_anchor_low / self.vol_decay_factor
        if vol > self.vol_anchor_high:
            self.vol_anchor_high = vol
        vol_cond_high = vol < self.vol_anchor_high / self.vol_accel_factor and vol > 0
        vol_cond = vol_cond_high or vol_cond_low
        
        if self.position == "long" and vol_cond and rsi < rsi_ma - self.rsi_thresh and self.close > self.entry_price:
            self.stop_price = round(self.close, 2)
            self.vol_anchor_high = 0
            self.vol_anchor_low = 0
            # print(f"{self.ts} EXIT (L): {self.entry_price}, STOP: {self.stop_price}")
            return self.sell()
        if self.position == "short" and vol_cond and rsi > rsi_ma + self.rsi_thresh and self.close < self.entry_price:
            self.stop_price = round(self.close, 2)
            self.vol_anchor_high = 0
            self.vol_anchor_low = 0
            # print(f"{self.ts} EXIT (S): {self.entry_price}, STOP: {self.stop_price}")
            return self.buy()
      
    def reset_indicators(self):
        if self.trade_window((9, 30), (9, 30)):
            self.vol_anchor_high = 0
            self.vol_anchor_low = 0
            self.rolling_rsi = deque(maxlen=5)
            self.rolling_vol = deque(maxlen=2)
      
    def minimum_computations(self):
        if not self.activated:
            required_data = max(
                self.fast_window,
                self.slow_window,
                self.rsi_period,
            ) + 1
            self.activated = len(self.prices) > required_data

    def compute_swing(self, mode="low", window=2, lookback=7):
        if len(self.prices) < window * 2 + 1:
            return None
        
        highs = self.highs[-lookback:]
        lows = self.lows[-lookback:]
        n = len(highs)

        if mode == "high":
            for i in range(n - window - 1, window - 1, -1):
                left = highs[i - window:i]
                right = highs[i + 1:i + 1 + window]
                if highs[i] > max(left) and highs[i] > max(right):
                    return highs[i]
            return max(highs)

        elif mode == "low":
            for i in range(n - window - 1, window - 1, -1):
                left = lows[i - window:i]
                right = lows[i + 1:i + 1 + window]
                if lows[i] < min(left) and lows[i] < min(right):
                    return lows[i]
            return min(lows)