import numpy as np
import pandas as pd
from .base import BaseStrategy, Signal


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean().iloc[-1]
    return float(atr) if not np.isnan(atr) else 0.0


class DonchianBreakoutStrategy(BaseStrategy):
    """
    Classic Turtle Trading Donchian Channel Breakout:
    - Version A: System 1 (20-bar breakout, 10-bar exit)
    - Version B: System 2 (55-bar breakout, 20-bar exit)
    Channel is strictly computed over [t - entry_period, t - 1] (excludes bar t to avoid lookahead bias).
    Initial Stop Loss: 2 * ATR.
    """

    def __init__(
        self,
        entry_period: int = 20,
        exit_period: int = 10,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        name_suffix: str = ""
    ):
        name = f"Donchian_{entry_period}_{exit_period}" + (f"_{name_suffix}" if name_suffix else "")
        super().__init__(name=name)
        self.entry_period = entry_period
        self.exit_period = exit_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier

    def on_bar(self, current_bar: pd.Series, history_df: pd.DataFrame) -> Signal:
        min_required = max(self.entry_period, self.exit_period, self.atr_period) + 5
        if len(history_df) < min_required:
            return Signal(action="HOLD")

        # Exclude current bar to prevent self-referencing lookahead bias
        prior_highs = history_df["high"].iloc[- (self.entry_period + 1): -1]
        prior_lows = history_df["low"].iloc[- (self.exit_period + 1): -1]

        upper_channel = prior_highs.max()
        lower_channel = prior_lows.min()

        current_close = current_bar["close"]
        atr = calculate_atr(history_df, self.atr_period)

        # Breakout Entry: Current close breaks above upper channel
        if current_close > upper_channel:
            stop_loss = current_close - (atr * self.atr_multiplier)
            return Signal(
                action="BUY",
                stop_loss=stop_loss,
                take_profit=current_close * 10.0,  # Let trend run; exit via lower channel
                confidence=0.8,
                reason=f"Breakout above {self.entry_period}-bar Upper Channel (${upper_channel:.2f})"
            )

        # Breakout Exit: Current close falls below lower channel
        elif current_close < lower_channel:
            return Signal(
                action="CLOSE",
                reason=f"Breakdown below {self.exit_period}-bar Lower Channel (${lower_channel:.2f})"
            )

        return Signal(action="HOLD")


class DonchianATRTrailingStrategy(BaseStrategy):
    """
    Version C: Donchian Breakout with ATR Trailing Stop (Chandelier-style).
    - Entry: Close breaks above entry_period Upper Channel.
    - Initial SL: Close - (atr_multiplier * ATR).
    - Trailing SL: Ratchets up on every candle to max(current_SL, Close - trail_multiplier * ATR).
    - Exit: Triggered when price hits the trailing stop, riding trends indefinitely.
    """

    def __init__(
        self,
        entry_period: int = 20,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        trail_multiplier: float = 2.5
    ):
        super().__init__(name=f"Donchian_{entry_period}_ATR_Trailing")
        self.entry_period = entry_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.trail_multiplier = trail_multiplier

    def on_bar(self, current_bar: pd.Series, history_df: pd.DataFrame) -> Signal:
        min_required = max(self.entry_period, self.atr_period) + 5
        if len(history_df) < min_required:
            return Signal(action="HOLD")

        prior_highs = history_df["high"].iloc[- (self.entry_period + 1): -1]
        upper_channel = prior_highs.max()

        current_close = current_bar["close"]
        atr = calculate_atr(history_df, self.atr_period)

        # Trailing stop ratchet target
        trailing_sl_candidate = current_close - (atr * self.trail_multiplier)

        # Breakout Entry
        if current_close > upper_channel:
            stop_loss = current_close - (atr * self.atr_multiplier)
            return Signal(
                action="BUY",
                stop_loss=stop_loss,
                take_profit=current_close * 10.0,
                trailing_stop=trailing_sl_candidate,
                confidence=0.85,
                reason=f"Breakout above {self.entry_period}-bar Upper Channel (${upper_channel:.2f})"
            )

        # In-position: emit updated trailing stop to ratchet up
        return Signal(
            action="HOLD",
            trailing_stop=trailing_sl_candidate,
            reason="Trailing stop ratchet update"
        )
