import numpy as np
import pandas as pd
from .base import BaseStrategy, Signal


class RSIBollingerStrategy(BaseStrategy):
    """
    Deterministic Mean-Reversion Strategy:
    - Long Entry: Close <= Lower BB and RSI < rsi_oversold (e.g. 30)
    - Exit: Close >= Middle BB (SMA 20) or RSI > 60 or Stop Loss hit
    - Stop Loss: Entry Price - (atr_multiplier * ATR)
    - Take Profit: Upper Bollinger Band or risk_reward * stop_distance
    """

    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_exit: float = 55.0,
        atr_period: int = 14,
        atr_multiplier: float = 1.5,
        risk_reward: float = 2.0
    ):
        super().__init__(name=f"RSI_BB_{bb_period}_{rsi_period}")
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_exit = rsi_exit
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.risk_reward = risk_reward

    def on_bar(self, current_bar: pd.Series, history_df: pd.DataFrame) -> Signal:
        min_required = max(self.bb_period, self.rsi_period, self.atr_period) + 5
        if len(history_df) < min_required:
            return Signal(action="HOLD")

        closes = history_df["close"]
        highs = history_df["high"]
        lows = history_df["low"]

        # Bollinger Bands
        sma = closes.rolling(window=self.bb_period).mean()
        std = closes.rolling(window=self.bb_period).std()
        upper_bb = sma + (std * self.bb_std)
        lower_bb = sma - (std * self.bb_std)

        # RSI (Wilder's Smoothing)
        delta = closes.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / self.rsi_period, min_periods=self.rsi_period).mean()
        avg_loss = loss.ewm(alpha=1 / self.rsi_period, min_periods=self.rsi_period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        # ATR
        tr1 = highs - lows
        tr2 = (highs - closes.shift(1)).abs()
        tr3 = (lows - closes.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean().iloc[-1]

        current_close = current_bar["close"]
        current_lower = lower_bb.iloc[-1]
        current_sma = sma.iloc[-1]
        current_rsi = rsi.iloc[-1]

        # Buy condition
        if current_close <= current_lower and current_rsi < self.rsi_oversold:
            stop_dist = atr * self.atr_multiplier
            stop_loss = current_close - stop_dist
            take_profit = current_close + (stop_dist * self.risk_reward)
            return Signal(
                action="BUY",
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.75,
                reason=f"RSI oversold ({current_rsi:.1f}) + pierced lower BB"
            )

        # Mean reversion exit condition
        elif current_close >= current_sma or current_rsi >= self.rsi_exit:
            return Signal(action="CLOSE", reason="Mean Reversion Reached (SMA/RSI)")

        return Signal(action="HOLD")
