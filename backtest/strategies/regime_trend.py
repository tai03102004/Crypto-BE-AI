import numpy as np
import pandas as pd
from .base import BaseStrategy, Signal


class RegimeFilteredTrendStrategy(BaseStrategy):
    """
    Trend Strategy with Multi-Factor Deterministic Market Regime Filter:
    1. Trend Direction: Fast EMA > Slow EMA AND Close > 200 EMA (HTF Macro Filter)
    2. Trend Strength (ADX): ADX > 20 (Filters out whipsaw choppy sideways regimes)
    3. Volume Confirmation: Volume > 1.2 * Volume SMA(20) (Filters out low-liquidity fakeouts)
    4. Volatility Regime (NATR): Normalized ATR between 0.4% and 3.5% (Filters dead market & erratic panics)
    """

    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        macro_period: int = 200,
        adx_period: int = 14,
        adx_threshold: float = 20.0,
        volume_multiplier: float = 1.2,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        risk_reward: float = 2.5
    ):
        super().__init__(name=f"Regime_Trend_{fast_period}_{slow_period}_ADX{int(adx_threshold)}")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.macro_period = macro_period
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.volume_multiplier = volume_multiplier
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.risk_reward = risk_reward

    def _calculate_adx(self, df: pd.DataFrame) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]

        plus_dm = high.diff()
        minus_dm = low.diff()

        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), -minus_dm, 0.0)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=self.adx_period).mean()

        plus_di = 100 * (pd.Series(plus_dm).rolling(window=self.adx_period).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(window=self.adx_period).mean() / atr)

        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
        adx = dx.rolling(window=self.adx_period).mean()
        return adx

    def on_bar(self, current_bar: pd.Series, history_df: pd.DataFrame) -> Signal:
        min_required = max(self.macro_period, self.slow_period, self.adx_period * 2) + 10
        if len(history_df) < min_required:
            return Signal(action="HOLD")

        closes = history_df["close"]
        highs = history_df["high"]
        lows = history_df["low"]
        volumes = history_df["volume"]

        # 1. EMAs
        ema_fast = closes.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = closes.ewm(span=self.slow_period, adjust=False).mean()
        ema_macro = closes.ewm(span=self.macro_period, adjust=False).mean()

        # 2. ATR & Normalized ATR (NATR)
        tr1 = highs - lows
        tr2 = (highs - closes.shift(1)).abs()
        tr3 = (lows - closes.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_series = tr.rolling(window=self.atr_period).mean()
        atr = atr_series.iloc[-1]
        current_close = current_bar["close"]
        natr = (atr / current_close) * 100

        # 3. Volume SMA
        vol_sma = volumes.rolling(window=20).mean().iloc[-1]
        current_vol = current_bar["volume"]

        # 4. ADX (Trend Strength)
        adx_series = self._calculate_adx(history_df)
        current_adx = adx_series.iloc[-1] if not adx_series.empty and not np.isnan(adx_series.iloc[-1]) else 0.0

        # Crossover detection
        fast_now = ema_fast.iloc[-1]
        fast_prev = ema_fast.iloc[-2]
        slow_now = ema_slow.iloc[-1]
        slow_prev = ema_slow.iloc[-2]
        macro_now = ema_macro.iloc[-1]

        # REGIME FILTERS CHECK:
        # a) Macro Trend Regime: Price strictly above 200 EMA
        is_bull_regime = current_close > macro_now and fast_now > macro_now
        # b) Volatility Regime: NATR between 0.4% and 3.5%
        is_healthy_volatility = 0.4 <= natr <= 3.5
        # c) Trend Strength Regime: ADX > threshold (market is actually trending)
        is_trending = current_adx >= self.adx_threshold
        # d) Volume Confirmation: Volume > threshold * SMA
        has_volume = current_vol >= (vol_sma * self.volume_multiplier)

        # Bullish Entry: Cross happened with all regime filters passing
        if fast_prev <= slow_prev and fast_now > slow_now:
            if is_bull_regime and is_healthy_volatility and is_trending and has_volume:
                stop_dist = atr * self.atr_multiplier
                stop_loss = current_close - stop_dist
                take_profit = current_close + (stop_dist * self.risk_reward)
                return Signal(
                    action="BUY",
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=0.85,
                    reason=f"Bullish Cross + Macro Trend + ADX({current_adx:.1f}) + Vol Surge"
                )

        # Exit Signal: Fast EMA crosses below Slow EMA
        elif fast_prev >= slow_prev and fast_now < slow_now:
            return Signal(action="CLOSE", reason="Bearish EMA Cross")

        return Signal(action="HOLD")
