import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

from backtest.data.loader import DataLoader
from backtest.engine.costs import TradingCosts
from backtest.engine.backtester import Backtester
from backtest.strategies.donchian_breakout import DonchianBreakoutStrategy


class DatasetBuilder:
    """
    Constructs clean ML datasets for Breakout Quality Evaluation.
    Strictly enforces separation between:
      - Feature Vector: Derived SOLELY from bars <= t (timestamp t close).
      - Target Vector: Derived SOLELY from future bars t+1 to exit.
      - Full Provenance: Tracks source timestamps of both asset and macro BTC candles.
      - Exact Reconciliation: Guarantees 1-to-1 equivalence with Backtest Engine trade logs.
    """

    def __init__(
        self,
        entry_period: int = 55,
        exit_period: int = 20,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        fee_rate: float = 0.0005,
        slippage_rate: float = 0.0003
    ):
        self.entry_period = entry_period
        self.exit_period = exit_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.costs = TradingCosts(fee_rate=fee_rate, slippage_rate=slippage_rate)

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
        Extracts 14 numeric features strictly using data slice df.iloc[: t_idx + 1].
        Under NO circumstances does this function access any index > t_idx.
        Tracks source timestamps to guarantee provenance and zero future leakage.
        """
        hist = df.iloc[: t_idx + 1]
        current_bar = hist.iloc[-1]
        signal_timestamp = current_bar["timestamp"]
        close_t = float(current_bar["close"])
        high_t = float(current_bar["high"])
        low_t = float(current_bar["low"])
        vol_t = float(current_bar["volume"])

        # 1. Structure Features
        # Donchian channel strictly over [t - entry_period, t - 1] (excludes bar t)
        prior_highs = hist["high"].iloc[- (self.entry_period + 1): -1]
        prior_lows = hist["low"].iloc[- (self.exit_period + 1): -1]

        # Audit check: Ensure bar t is NOT in prior_highs
        assert hist.index[-1] not in prior_highs.index, "Leakage: candle t index included in upper channel!"
        assert hist["timestamp"].iloc[-1] not in hist.loc[prior_highs.index, "timestamp"].values, "Leakage: candle t timestamp included in upper channel!"

        upper_ch = float(prior_highs.max())
        lower_ch = float(prior_lows.min())

        channel_width_pct = ((upper_ch - lower_ch) / close_t) * 100.0 if close_t > 0 else 0.0
        breakout_magnitude_pct = ((close_t - upper_ch) / upper_ch) * 100.0 if upper_ch > 0 else 0.0

        # Channel width change over previous 5 bars
        if len(hist) > self.entry_period + 6:
            p_highs_5 = hist["high"].iloc[- (self.entry_period + 6): -6]
            p_lows_5 = hist["low"].iloc[- (self.exit_period + 6): -6]
            width_5 = ((p_highs_5.max() - p_lows_5.min()) / hist["close"].iloc[-6]) * 100.0
            channel_width_change = (channel_width_pct - width_5) / (width_5 + 1e-6)
        else:
            channel_width_change = 0.0

        # Breakout close position within bar t range [0.0, 1.0]
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

        # 5. Macro BTC Context Features & Provenance Timestamp
        if btc_df is not None:
            # Strictly match BTC data at or before current timestamp
            btc_hist = btc_df[btc_df["timestamp"] <= signal_timestamp]
            assert not btc_hist.empty, f"No BTC data found at or before {signal_timestamp}"
            btc_provenance_time = btc_hist["timestamp"].iloc[-1]
            # Provenance Invariant: btc_provenance_time <= signal_timestamp
            assert btc_provenance_time <= signal_timestamp, "BTC leakage: provenance time exceeds signal time!"

            btc_close_t = float(btc_hist["close"].iloc[-1])
            btc_ret_24h = ((btc_close_t - btc_hist["close"].iloc[-7]) / btc_hist["close"].iloc[-7]) * 100.0 if len(btc_hist) >= 7 else 0.0
            btc_atr = float(self._compute_atr_series(btc_hist["high"], btc_hist["low"], btc_hist["close"], period=14).iloc[-1])
            btc_natr = (btc_atr / btc_close_t) * 100.0 if btc_close_t > 0 else 0.0
        else:
            # If asset is BTCUSDT, use its own momentum and volatility
            btc_provenance_time = signal_timestamp
            btc_ret_24h = asset_ret_24h
            btc_natr = natr

        # Extract Pre-Breakout Sequence Representation v2 strictly over [t-55, t-1]
        sequence_features = self.extract_sequence_features_pre_t(
            t_idx=t_idx,
            df=df,
            signal_timestamp=signal_timestamp,
            btc_df=btc_df
        )

        return {
            # Snapshot Features (14)
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
            # Sequence / Pre-Breakout Features (9)
            **sequence_features,
            # Provenance Timestamps
            "provenance_asset_time": signal_timestamp,
            "provenance_btc_time": btc_provenance_time
        }

    def extract_sequence_features_pre_t(
        self,
        t_idx: int,
        df: pd.DataFrame,
        signal_timestamp: Any,
        btc_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Extracts 9 pre-breakout sequence/regime features strictly using data <= t-1.
        Under NO circumstances does this function access index t or any index > t.
        Enforces self-auditing temporal assertions: max(source_timestamp) < signal_timestamp.
        """
        # Slice strictly prior to candle t: [0, t - 1]
        pre_hist = df.iloc[: t_idx]
        assert len(pre_hist) >= 55, f"Insufficient history ({len(pre_hist)}) for pre-breakout sequence features"

        # TEMPORAL INTEGRITY ASSERTIONS
        max_asset_src = pre_hist["timestamp"].iloc[-1]
        assert max_asset_src < signal_timestamp, (
            f"Temporal Leakage Violation: max asset pre-history timestamp {max_asset_src} >= signal {signal_timestamp}"
        )
        assert df.iloc[t_idx]["timestamp"] not in pre_hist["timestamp"].values, (
            "Temporal Leakage Violation: candle t timestamp found inside pre-breakout history!"
        )

        close_series = pre_hist["close"]
        high_series = pre_hist["high"]
        low_series = pre_hist["low"]
        vol_series = pre_hist["volume"]

        atr_series = self._compute_atr_series(high_series, low_series, close_series, period=self.atr_period)
        atr_pre = float(atr_series.iloc[-1])
        close_pre = float(close_series.iloc[-1])

        # ---------------------------------------------------------------------
        # 1. compression_duration_bars
        # Definition: Consecutive bars ending at t-1 where bar range (H - L) <= 1.5 * ATR14
        # Window: Pre-breakout [t - 55, t - 1]
        # Uses current bar: False
        # Available at signal time: True
        # Economic hypothesis: Extended quiet price action clears overhang before breakout.
        # ---------------------------------------------------------------------
        bar_ranges = high_series - low_series
        is_tight = bar_ranges <= (1.5 * atr_series)
        compression_duration = 0
        for tight in is_tight.iloc[-55:].values[::-1]:
            if bool(tight):
                compression_duration += 1
            else:
                break

        # ---------------------------------------------------------------------
        # 2. natr_percentile_55
        # Definition: Percentile rank of NATR at t-1 relative to 55 bars ending at t-1
        # Window: [t - 55, t - 1]
        # Uses current bar: False
        # Available at signal time: True
        # Economic hypothesis: Low percentile indicates volatility contraction prior to expansion.
        # ---------------------------------------------------------------------
        natr_55 = (atr_series.iloc[-55:] / close_series.iloc[-55:]) * 100.0
        current_natr_pre = float(natr_55.iloc[-1])
        natr_percentile_55 = float((natr_55 <= current_natr_pre).mean())

        # ---------------------------------------------------------------------
        # 3. range_contraction_ratio
        # Definition: High-low range of last 5 bars [t-5, t-1] / range of last 20 bars [t-20, t-1]
        # Window: [t - 20, t - 1]
        # Uses current bar: False
        # Available at signal time: True
        # Economic hypothesis: Ratio < 0.5 indicates severe coiled spring compression immediately before breakout.
        # ---------------------------------------------------------------------
        range_5 = float(high_series.iloc[-5:].max() - low_series.iloc[-5:].min())
        range_20 = float(high_series.iloc[-20:].max() - low_series.iloc[-20:].min())
        range_contraction_ratio = (range_5 / (range_20 + 1e-8))

        # ---------------------------------------------------------------------
        # 4. channel_tightness_to_atr
        # Definition: 55-bar Donchian channel width at t-1 divided by ATR14 at t-1
        # Window: [t - 55, t - 1]
        # Uses current bar: False
        # Available at signal time: True
        # Economic hypothesis: Low ratio identifies rectangular consolidation vs wild wide swings.
        # ---------------------------------------------------------------------
        upper_55_pre = float(high_series.iloc[-55:].max())
        lower_20_pre = float(low_series.iloc[-20:].min())
        channel_width_abs = upper_55_pre - lower_20_pre
        channel_tightness_to_atr = float(channel_width_abs / (atr_pre + 1e-8))

        # ---------------------------------------------------------------------
        # 5. resistance_touch_count
        # Definition: Number of bars in [t-55, t-1] where High >= 0.99 * UpperChannel_55[t-1]
        # Window: [t - 55, t - 1]
        # Uses current bar: False
        # Available at signal time: True
        # Economic hypothesis: Repeated tests of resistance without breakdown indicate persistent demand absorbing limit sell orders.
        # ---------------------------------------------------------------------
        touches = (high_series.iloc[-55:] >= (0.99 * upper_55_pre)).sum()
        resistance_touch_count = int(touches)

        # ---------------------------------------------------------------------
        # 6. pre_breakout_runup_5b
        # Definition: Percentage price return from Close[t-6] to Close[t-1]
        # Window: [t - 6, t - 1]
        # Uses current bar: False
        # Available at signal time: True
        # Economic hypothesis: Breakouts emerging directly from a base have near 0% pre-runup; breakouts already up 8-15% into resistance are exhausted.
        # ---------------------------------------------------------------------
        c_t1 = float(close_series.iloc[-1])
        c_t6 = float(close_series.iloc[-6])
        pre_breakout_runup_5b = float(((c_t1 - c_t6) / c_t6) * 100.0) if c_t6 > 0 else 0.0

        # ---------------------------------------------------------------------
        # 7. volume_trend_slope_10b
        # Definition: Linear regression slope of normalized volume over 10 bars [t-10, t-1]
        # Window: [t - 10, t - 1]
        # Uses current bar: False
        # Available at signal time: True
        # Economic hypothesis: Declining volume slope during consolidation indicates diminishing selling pressure.
        # ---------------------------------------------------------------------
        v10 = vol_series.iloc[-10:].values
        mean_v10 = np.mean(v10) + 1e-8
        v10_norm = v10 / mean_v10
        x10 = np.arange(10)
        # Analytical slope: Cov(x, y) / Var(x)
        slope_10b = float(np.polyfit(x10, v10_norm, deg=1)[0])

        # ---------------------------------------------------------------------
        # 8. volume_percentile_55
        # Definition: Percentile rank of 5-bar average volume [t-5, t-1] relative to past 55-bar volume
        # Window: [t - 55, t - 1]
        # Uses current bar: False
        # Available at signal time: True
        # Economic hypothesis: Identifies whether the pre-breakout market state was dormant vs churning.
        # ---------------------------------------------------------------------
        avg_vol_5 = float(vol_series.iloc[-5:].mean())
        v55 = vol_series.iloc[-55:].values
        volume_percentile_55 = float((v55 <= avg_vol_5).mean())

        # ---------------------------------------------------------------------
        # 9. macro_btc_natr_percentile_55
        # Definition: Percentile rank of BTC NATR at t-1 relative to 55 BTC bars ending at or before t-1
        # Window: [t - 55, t - 1] (BTC)
        # Uses current bar: False
        # Available at signal time: True
        # Economic hypothesis: Contextual macro compression — when BTC is in low volatility decile, market-wide trend expansion is cleanest.
        # ---------------------------------------------------------------------
        if btc_df is not None:
            btc_pre = btc_df[btc_df["timestamp"] < signal_timestamp]
            assert not btc_pre.empty, f"No BTC data found strictly before {signal_timestamp}"
            max_btc_src = btc_pre["timestamp"].iloc[-1]
            assert max_btc_src < signal_timestamp, (
                f"Temporal Leakage Violation: max BTC pre-history timestamp {max_btc_src} >= signal {signal_timestamp}"
            )
            assert len(btc_pre) >= 55, f"Insufficient BTC history ({len(btc_pre)}) for percentile calculation"
            btc_atr_series = self._compute_atr_series(btc_pre["high"], btc_pre["low"], btc_pre["close"], period=14)
            btc_natr_55 = (btc_atr_series.iloc[-55:] / btc_pre["close"].iloc[-55:]) * 100.0
            current_btc_natr = float(btc_natr_55.iloc[-1])
            macro_btc_natr_percentile_55 = float((btc_natr_55 <= current_btc_natr).mean())
        else:
            # Asset is BTCUSDT: use its own NATR percentile
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
            "macro_btc_natr_percentile_55": macro_btc_natr_percentile_55,
            "provenance_sequence_max_time": str(max_asset_src)
        }

    def build_reconciled_dataset(
        self,
        symbol: str,
        df: pd.DataFrame,
        btc_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Builds the 1-to-1 Reconciled Dataset matching the Frozen Backtest Engine.
        Executes the strategy sequentially, records each trade, and maps its feature vector
        strictly to the candle t close prior to entry.
        """
        strategy = DonchianBreakoutStrategy(
            entry_period=self.entry_period,
            exit_period=self.exit_period,
            atr_multiplier=self.atr_multiplier
        )
        bt = Backtester(
            strategy=strategy,
            initial_capital=1000.0,
            risk_per_trade_pct=0.01,
            max_exposure_pct=0.30,
            max_daily_loss_pct=0.03,
            fee_rate=self.costs.fee_rate,
            slippage_rate=self.costs.slippage_rate
        )
        res = bt.run(df, warmup_bars=60)
        trades = res["trades"]

        rows = []
        for t_idx, trade in enumerate(trades):
            # Find the entry bar index
            entry_match = df[df["timestamp"] == trade.entry_time]
            if entry_match.empty:
                continue
            entry_idx = entry_match.index[0]
            signal_idx = entry_idx - 1
            if signal_idx < 0:
                continue

            # Signal timestamp is strictly bar t (one bar prior to entry)
            signal_bar = df.iloc[signal_idx]
            features = self.extract_features_at_t(t_idx=signal_idx, df=df, btc_df=btc_df)

            # Compute initial risk unit R
            hist_t = df.iloc[: signal_idx + 1]
            atr_t = float(self._compute_atr_series(hist_t["high"], hist_t["low"], hist_t["close"], period=self.atr_period).iloc[-1])
            dollar_risk_per_unit = trade.entry_price - (trade.entry_price - self.atr_multiplier * atr_t)
            initial_dollar_risk = trade.size * dollar_risk_per_unit

            # Realized R
            realized_r = trade.pnl / initial_dollar_risk if initial_dollar_risk > 0 else 0.0

            # Excursions during trade holding period
            exit_match = df[df["timestamp"] == trade.exit_time]
            exit_idx = exit_match.index[0] if not exit_match.empty else len(df) - 1

            holding_slice = df.iloc[entry_idx: exit_idx + 1]
            max_high = holding_slice["high"].max()
            min_low = holding_slice["low"].min()

            mfe_r = (max_high - trade.entry_price) / dollar_risk_per_unit if dollar_risk_per_unit > 0 else 0.0
            mae_r = (trade.entry_price - min_low) / dollar_risk_per_unit if dollar_risk_per_unit > 0 else 0.0

            row = {
                "trade_id": f"{symbol}_{t_idx + 1:03d}",
                "asset": symbol,
                "signal_time": signal_bar["timestamp"],
                "entry_time": trade.entry_time,
                "exit_time": trade.exit_time,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "position_size": trade.size,
                "net_pnl": trade.pnl,
                "pnl_pct": trade.pnl_pct * 100.0,
                "fees": trade.fees,
                "target_realized_r": realized_r,
                "target_mfe_r": mfe_r,
                "target_mae_r": mae_r,
                "target_hit_1r": 1 if mfe_r >= 1.0 else 0,
                "target_hit_2r": 1 if mfe_r >= 2.0 else 0,
                "target_hit_3r": 1 if mfe_r >= 3.0 else 0,
                "target_exit_reason": trade.exit_reason,
                "target_holding_bars": len(holding_slice),
                **features
            }
            rows.append(row)

        return pd.DataFrame(rows)
