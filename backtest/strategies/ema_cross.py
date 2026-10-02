import numpy as np
import pandas as pd
from .base import BaseStrategy, Signal


class EMACrossoverStrategy(BaseStrategy):
    """
    Deterministic Trend-Following Strategy:
    - Long Entry: Fast EMA crosses ABOVE Slow EMA + Price > 200 EMA
    - Exit: Fast EMA crosses BELOW Slow EMA or Stop Loss hit
    - Stop Loss: Entry Price - (atr_multiplier * ATR)
    - Take Profit: Entry Price + (risk_reward * stop_distance)
    """

    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        trend_period: int = 200,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        risk_reward: float = 2.0
    ):
        super().__init__(name=f"EMA_Cross_{fast_period}_{slow_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.trend_period = trend_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.risk_reward = risk_reward

    def on_bar(self, current_bar: pd.Series, history_df: pd.DataFrame) -> Signal:
        min_required = max(self.trend_period, self.slow_period, self.atr_period) + 5
        if len(history_df) < min_required:
            return Signal(action="HOLD")

        closes = history_df["close"]
        highs = history_df["high"]
        lows = history_df["low"]

        # Calculate EMAs
        ema_fast = closes.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = closes.ewm(span=self.slow_period, adjust=False).mean()
        ema_trend = closes.ewm(span=self.trend_period, adjust=False).mean()

        # ATR calculation
        tr1 = highs - lows
        tr2 = (highs - closes.shift(1)).abs()
        tr3 = (lows - closes.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean().iloc[-1]

        # Check cross on the last 2 bars
        fast_now = ema_fast.iloc[-1]
        fast_prev = ema_fast.iloc[-2]
        slow_now = ema_slow.iloc[-1]
        slow_prev = ema_slow.iloc[-2]
        trend_now = ema_trend.iloc[-1]
        current_close = current_bar["close"]

        # Bullish Crossover in overall uptrend
        if fast_prev <= slow_prev and fast_now > slow_now and current_close > trend_now:
            stop_dist = atr * self.atr_multiplier
            stop_loss = current_close - stop_dist
            take_profit = current_close + (stop_dist * self.risk_reward)
            return Signal(
                action="BUY",
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=0.8,
                reason="Bullish EMA Cross above 200 EMA"
            )

        # Bearish Crossover (Exit Long)
        elif fast_prev >= slow_prev and fast_now < slow_now:
            return Signal(action="CLOSE", reason="Bearish EMA Cross")

        return Signal(action="HOLD")
