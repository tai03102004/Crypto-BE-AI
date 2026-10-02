import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


class FeatureExtractor:
    """
    Self-contained feature extractor for live Stage A execution.
    Extracts the exact 23 features (14 snapshot + 9 sequence) strictly up to bar t.
    Identical logic to DatasetBuilder without any dependencies on the backtest engine.
    """

    def __init__(
        self,
        entry_period: int = 55,
        exit_period: int = 20,
        atr_period: int = 14,
        atr_multiplier: float = 2.0
    ):
        self.entry_period = entry_period
        self.exit_period = exit_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier

    @staticmethod
    def _compute_atr_series(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def extract_features_at_t(
        self,
        t_idx: int,
        df: pd.DataFrame,
        btc_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Extracts 14 snapshot features + 9 sequence features strictly using data <= t.
        Guarantees zero future leakage and matches frozen training schema.
        """
        hist = df.iloc[: t_idx + 1]
        current_bar = hist.iloc[-1]
        signal_timestamp = current_bar["timestamp"]
        close_t = float(current_bar["close"])
        high_t = float(current_bar["high"])
        low_t = float(current_bar["low"])
        vol_t = float(current_bar["volume"])

        # 1. Structure Features
        prior_highs = hist["high"].iloc[- (self.entry_period + 1): -1]
        prior_lows = hist["low"].iloc[- (self.exit_period + 1): -1]

        upper_ch = float(prior_highs.max())
        lower_ch = float(prior_lows.min())

        channel_width_pct = ((upper_ch - lower_ch) / close_t) * 100.0 if close_t > 0 else 0.0
        breakout_magnitude_pct = ((close_t - upper_ch) / upper_ch) * 100.0 if upper_ch > 0 else 0.0

        if len(hist) > self.entry_period + 6:
            p_highs_5 = hist["high"].iloc[- (self.entry_period + 6): -6]
            p_lows_5 = hist["low"].iloc[- (self.exit_period + 6): -6]
            width_5 = ((p_highs_5.max() - p_lows_5.min()) / hist["close"].iloc[-6]) * 100.0
            channel_width_change = (channel_width_pct - width_5) / (width_5 + 1e-6)
        else:
            channel_width_change = 0.0

        bar_range = high_t - low_t
        if bar_range > 1e-8:
            breakout_close_position = float(np.clip((close_t - low_t) / bar_range, 0.0, 1.0))
        else:
            breakout_close_position = 0.5

        # EMAs and Slopes
        ema50_series = hist["close"].ewm(span=50, adjust=False).mean()
        ema200_series = hist["close"].ewm(span=200, adjust=False).mean()
        ema50_t = float(ema50_series.iloc[-1])
        ema200_t = float(ema200_series.iloc[-1])

        dist_to_ema200_pct = ((close_t - ema200_t) / ema200_t) * 100.0 if ema200_t > 0 else 0.0

        if len(ema50_series) >= 6 and ema50_series.iloc[-6] > 0:
            ema50_slope_5 = ((ema50_t - ema50_series.iloc[-6]) / ema50_series.iloc[-6]) * 100.0
        else:
            ema50_slope_5 = 0.0

        # 2. Volatility Features
        atr_series = self._compute_atr_series(hist["high"], hist["low"], hist["close"], period=self.atr_period)
        atr_t = float(atr_series.iloc[-1])
        natr = (atr_t / close_t) * 100.0 if close_t > 0 else 0.0

        atr_sma20 = float(atr_series.rolling(20).mean().iloc[-1]) if len(atr_series) >= 20 else atr_t
        atr_expansion = (atr_t / (atr_sma20 + 1e-8))

        # 3. Volume Features
        vol_mean_20 = float(hist["volume"].rolling(20).mean().iloc[-1]) if len(hist) >= 20 else vol_t
        vol_std_20 = float(hist["volume"].rolling(20).std().iloc[-1]) if len(hist) >= 20 else 1.0
        vol_ratio = (vol_t / (vol_mean_20 + 1e-8))
        breakout_volume_zscore = float((vol_t - vol_mean_20) / (vol_std_20 + 1e-8))

        # 4. Asset Momentum Features
        asset_ret_24h = ((close_t - hist["close"].iloc[-7]) / hist["close"].iloc[-7]) * 100.0 if len(hist) >= 7 else 0.0
        asset_ret_7d = ((close_t - hist["close"].iloc[-43]) / hist["close"].iloc[-43]) * 100.0 if len(hist) >= 43 else 0.0

        # 5. Macro BTC Context Features
        if btc_df is not None:
            btc_hist = btc_df[btc_df["timestamp"] <= signal_timestamp]
            btc_close_t = float(btc_hist["close"].iloc[-1])
            btc_ret_24h = ((btc_close_t - btc_hist["close"].iloc[-7]) / btc_hist["close"].iloc[-7]) * 100.0 if len(btc_hist) >= 7 else 0.0
            btc_atr = float(self._compute_atr_series(btc_hist["high"], btc_hist["low"], btc_hist["close"], period=14).iloc[-1])
            btc_natr = (btc_atr / btc_close_t) * 100.0 if btc_close_t > 0 else 0.0
        else:
            btc_ret_24h = asset_ret_24h
            btc_natr = natr

        # Sequence Features
        sequence_features = self.extract_sequence_features_pre_t(
            t_idx=t_idx,
            df=df,
            signal_timestamp=signal_timestamp,
            btc_df=btc_df
        )

        return {
            # Snapshot 14
            "channel_width_pct": channel_width_pct,
            "channel_width_change": channel_width_change,
            "breakout_magnitude_pct": breakout_magnitude_pct,
            "breakout_close_position": breakout_close_position,
            "dist_to_ema200_pct": dist_to_ema200_pct,
            "ema50_slope_5": ema50_slope_5,
            "natr": natr,
            "atr_expansion": atr_expansion,
            "vol_ratio": vol_ratio,
            "breakout_volume_zscore": breakout_volume_zscore,
            "asset_ret_24h": asset_ret_24h,
            "asset_ret_7d": asset_ret_7d,
            "btc_ret_24h": btc_ret_24h,
            "btc_natr": btc_natr,
            # Sequence 9
            **sequence_features
        }

    def extract_sequence_features_pre_t(
        self,
        t_idx: int,
        df: pd.DataFrame,
        signal_timestamp: Any,
        btc_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Extracts 9 pre-breakout sequence features strictly using data <= t-1.
        """
        pre_hist = df.iloc[: t_idx]
        assert len(pre_hist) >= 55, f"Insufficient history ({len(pre_hist)}) for pre-breakout sequence features"

        close_series = pre_hist["close"]
        high_series = pre_hist["high"]
        low_series = pre_hist["low"]
        vol_series = pre_hist["volume"]

        atr_series = self._compute_atr_series(high_series, low_series, close_series, period=self.atr_period)
        atr_pre = float(atr_series.iloc[-1])
        close_pre = float(close_series.iloc[-1])

        # 1. compression_duration_bars
        bar_ranges = high_series - low_series
        is_tight = bar_ranges <= (1.5 * atr_series)
        compression_duration = 0
        for tight in is_tight.iloc[-55:].values[::-1]:
            if bool(tight):
                compression_duration += 1
            else:
                break

        # 2. natr_percentile_55
        natr_55 = (atr_series.iloc[-55:] / close_series.iloc[-55:]) * 100.0
        current_natr_pre = float(natr_55.iloc[-1])
        natr_percentile_55 = float((natr_55 <= current_natr_pre).mean())

        # 3. range_contraction_ratio
        range_5 = float(high_series.iloc[-5:].max() - low_series.iloc[-5:].min())
        range_20 = float(high_series.iloc[-20:].max() - low_series.iloc[-20:].min())
        range_contraction_ratio = (range_5 / (range_20 + 1e-8)) if range_20 > 0 else 1.0

        # 4. channel_tightness_to_atr
        upper_55_pre = float(high_series.iloc[-55:].max())
        lower_20_pre = float(low_series.iloc[-20:].max())
        ch_width_pre = upper_55_pre - lower_20_pre
        channel_tightness_to_atr = (ch_width_pre / (atr_pre + 1e-8)) if atr_pre > 0 else 0.0

        # 5. resistance_touch_count
        touches = (high_series.iloc[-55:] >= (0.99 * upper_55_pre)).sum()
        resistance_touch_count = int(touches)

        # 6. pre_breakout_runup_5b
        c_t1 = float(close_series.iloc[-1])
        c_t6 = float(close_series.iloc[-6])
        pre_breakout_runup_5b = float(((c_t1 - c_t6) / c_t6) * 100.0) if c_t6 > 0 else 0.0

        # 7. volume_trend_slope_10b
        v10 = vol_series.iloc[-10:].values
        mean_v10 = np.mean(v10) + 1e-8
        v10_norm = v10 / mean_v10
        x10 = np.arange(10)
        slope_10b = float(np.polyfit(x10, v10_norm, deg=1)[0])

        # 8. volume_percentile_55
        avg_vol_5 = float(vol_series.iloc[-5:].mean())
        v55 = vol_series.iloc[-55:].values
        volume_percentile_55 = float((v55 <= avg_vol_5).mean())

        # 9. macro_btc_natr_percentile_55
        if btc_df is not None:
            btc_pre = btc_df[btc_df["timestamp"] < signal_timestamp]
            assert len(btc_pre) >= 55, f"Insufficient BTC history ({len(btc_pre)}) for percentile calculation"
            btc_atr_series = self._compute_atr_series(btc_pre["high"], btc_pre["low"], btc_pre["close"], period=14)
            btc_natr_55 = (btc_atr_series.iloc[-55:] / btc_pre["close"].iloc[-55:]) * 100.0
            current_btc_natr = float(btc_natr_55.iloc[-1])
            macro_btc_natr_percentile_55 = float((btc_natr_55 <= current_btc_natr).mean())
        else:
            macro_btc_natr_percentile_55 = natr_percentile_55

        return {
            "compression_duration_bars": compression_duration,
            "natr_percentile_55": natr_percentile_55,
            "range_contraction_ratio": range_contraction_ratio,
            "channel_tightness_to_atr": channel_tightness_to_atr,
            "resistance_touch_count": resistance_touch_count,
            "pre_breakout_runup_5b": pre_breakout_runup_5b,
            "volume_trend_slope_10b": slope_10b,
            "volume_percentile_55": volume_percentile_55,
            "macro_btc_natr_percentile_55": macro_btc_natr_percentile_55
        }
