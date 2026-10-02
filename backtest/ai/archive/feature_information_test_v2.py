import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
from typing import Dict, Any, List
from scipy.stats import spearmanr, pearsonr
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV, Ridge
from sklearn.tree import DecisionTreeRegressor, export_text


def run_feature_information_test_v2():
    print("=" * 100)
    print("  FEATURE INFORMATION TEST v2: PRE-BREAKOUT TEMPORAL STRUCTURE vs SNAPSHOT")
    print("  Question: Does pre-breakout temporal history provide predictive information absent from snapshot?")
    print("  Protocol: 3 Fixed Models (Null -> Ridge -> Shallow Tree depth=2) across 3 Representations")
    print("  Rule: Strictly No Grid Search, No Model Shopping, Locked OOS 2025-2026")
    print("=" * 100)

    data_dir = Path(__file__).parent / "data"
    dev = pd.read_csv(data_dir / "breakouts_dev_2022_2023.csv")
    val = pd.read_csv(data_dir / "breakouts_val_2024.csv")

    snapshot_14 = [
        "channel_width_pct", "channel_width_change", "breakout_magnitude_pct",
        "breakout_close_position", "dist_to_ema200_pct", "ema50_slope_5",
        "natr", "atr_expansion", "vol_ratio", "breakout_volume_zscore",
        "asset_ret_24h", "asset_ret_7d", "btc_ret_24h", "btc_natr"
    ]

    sequence_9 = [
        "compression_duration_bars", "natr_percentile_55", "range_contraction_ratio",
        "channel_tightness_to_atr", "resistance_touch_count", "pre_breakout_runup_5b",
        "volume_trend_slope_10b", "volume_percentile_55", "macro_btc_natr_percentile_55"
    ]

    combined_23 = snapshot_14 + sequence_9

    y_dev = dev["target_realized_r"].values
    y_val = val["target_realized_r"].values

    print(f"\n[1] Partitions & Targets:")
    print(f"  Dev (2022-2023): {len(dev)} trades | Mean R = {y_dev.mean():+.3f}R | Median = {np.median(y_dev):+.3f}R")
    print(f"  Val (2024):      {len(val)} trades  | Mean R = {y_val.mean():+.3f}R | Median = {np.median(y_val):+.3f}R")

    # Temporal integrity audit on Val
    time_violations = 0
    for idx, r in val.iterrows():
        sig = pd.Timestamp(r["signal_time"])
        seq_src = pd.Timestamp(r["provenance_sequence_max_time"])
        if seq_src >= sig:
            time_violations += 1
    assert time_violations == 0, f"Critical Leakage: {time_violations} rows violated sequence timestamp integrity!"
    print(f"  ✅ Temporal Integrity: 100% of sequence features satisfy max(source_time) < signal_time.")

    # Helper evaluation function
    def evaluate_representation(rep_name: str, feature_set: List[str]):
        print(f"\n" + "-" * 100)
        print(f"  REPRESENTATION: {rep_name} ({len(feature_set)} features)")
        print("-" * 100)

        X_dev_raw = dev[feature_set].values
        X_val_raw = val[feature_set].values

        scaler = StandardScaler()
        X_dev = scaler.fit_transform(X_dev_raw)
        X_val = scaler.transform(X_val_raw)

        # 1. Null Model
        null_pred = np.full_like(y_val, fill_value=y_dev.mean())

        # 2. Linear Ridge (alpha chosen strictly via Dev CV)
        candidate_alphas = [0.1, 1.0, 5.0, 10.0, 50.0, 100.0, 200.0, 500.0]
        ridge_cv = RidgeCV(alphas=candidate_alphas, cv=5)
        ridge_cv.fit(X_dev, y_dev)
        best_alpha = float(ridge_cv.alpha_)
        ridge = Ridge(alpha=best_alpha, random_state=42)
        ridge.fit(X_dev, y_dev)
        ridge_pred = ridge.predict(X_val)

        # 3. Shallow Tree (depth=2, min_leaf=15)
        tree = DecisionTreeRegressor(max_depth=2, min_samples_leaf=15, random_state=42)
        tree.fit(X_dev_raw, y_dev)
        tree_pred = tree.predict(X_val_raw)

        print(f"  Ridge optimal CV alpha on Dev = {best_alpha:.1f}")
        print(f"  Tree rules (Dev):\n    " + "\n    ".join(export_text(tree, feature_names=feature_set).strip().split("\n")))

        def compute_metrics(y_pred: np.ndarray) -> Dict[str, Any]:
            mae = float(np.mean(np.abs(y_pred - y_val)))
            rmse = float(np.sqrt(np.mean((y_pred - y_val) ** 2)))
            
            if np.all(y_pred == y_pred[0]):
                p_corr, p_pval = 0.0, 1.0
                s_corr, s_pval = 0.0, 1.0
                order = np.arange(len(y_val))
            else:
                p_corr, p_pval = pearsonr(y_pred, y_val)
                s_corr, s_pval = spearmanr(y_pred, y_val)
                order = np.argsort(y_pred)

            n_20 = max(1, int(len(y_val) * 0.20))
            bot_idx = order[:n_20]
            top_idx = order[-n_20:]

            top_r = y_val[top_idx]
            bot_r = y_val[bot_idx]

            top_mean = float(np.mean(top_r))
            bot_mean = float(np.mean(bot_r))
            top_median = float(np.median(top_r))
            bot_median = float(np.median(bot_r))
            top_wr = float((top_r > 0).mean() * 100.0)
            bot_wr = float((bot_r > 0).mean() * 100.0)
            top_pnl = float(val.iloc[top_idx]["net_pnl"].sum())
            bot_pnl = float(val.iloc[bot_idx]["net_pnl"].sum())

            # Outlier robustness: drop top 1 winner from top 20%
            sorted_top_r = np.sort(top_r)
            top_mean_no_outlier = float(sorted_top_r[:-1].mean())

            return {
                "mae": mae,
                "rmse": rmse,
                "pearson": p_corr,
                "pearson_p": p_pval,
                "spearman": s_corr,
                "spearman_p": s_pval,
                "top_mean": top_mean,
                "bot_mean": bot_mean,
                "spread_mean": top_mean - bot_mean,
                "top_median": top_median,
                "bot_median": bot_median,
                "spread_median": top_median - bot_median,
                "top_wr": top_wr,
                "bot_wr": bot_wr,
                "top_pnl": top_pnl,
                "bot_pnl": bot_pnl,
                "top_mean_no_outlier": top_mean_no_outlier
            }

        m_null = compute_metrics(null_pred)
        m_ridge = compute_metrics(ridge_pred)
        m_tree = compute_metrics(tree_pred)

        print(f"\n  {'Evaluation Dimension':<28} {'Model 0: Null':<18} {'Model 1: Ridge':<22} {'Model 2: Shallow Tree':<22}")
        print(f"  {'-'*28} {'-'*18} {'-'*22} {'-'*22}")
        print(f"  {'[A] Spearman Rho (p-val)':<28} {m_null['spearman']:<+7.4f} (p={m_null['spearman_p']:.3f}) {m_ridge['spearman']:<+7.4f} (p={m_ridge['spearman_p']:.3f})    {m_tree['spearman']:<+7.4f} (p={m_tree['spearman_p']:.3f})")
        print(f"  {'[A] Pearson r (p-val)':<28} {m_null['pearson']:<+7.4f} (p={m_null['pearson_p']:.3f}) {m_ridge['pearson']:<+7.4f} (p={m_ridge['pearson_p']:.3f})    {m_tree['pearson']:<+7.4f} (p={m_tree['pearson_p']:.3f})")
        print(f"  {'[A] MAE (R)':<28} {m_null['mae']:<18.4f} {m_ridge['mae']:<22.4f} {m_tree['mae']:<22.4f}")
        print(f"  {'[B] Top 20% Mean Realized R':<28} {m_null['top_mean']:<+18.3f}R {m_ridge['top_mean']:<+21.3f}R {m_tree['top_mean']:<+21.3f}R")
        print(f"  {'[B] Bot 20% Mean Realized R':<28} {m_null['bot_mean']:<+18.3f}R {m_ridge['bot_mean']:<+21.3f}R {m_tree['bot_mean']:<+21.3f}R")
        print(f"  {'[B] Mean Spread (Top - Bot)':<28} {m_null['spread_mean']:<+18.3f}R {m_ridge['spread_mean']:<+21.3f}R {m_tree['spread_mean']:<+21.3f}R")
        print(f"  {'[B] Top 20% Median R':<28} {m_null['top_median']:<+18.3f}R {m_ridge['top_median']:<+21.3f}R {m_tree['top_median']:<+21.3f}R")
        print(f"  {'[B] Bot 20% Median R':<28} {m_null['bot_median']:<+18.3f}R {m_ridge['bot_median']:<+21.3f}R {m_tree['bot_median']:<+21.3f}R")
        print(f"  {'[B] Median Spread (Top - Bot)':<28} {m_null['spread_median']:<+18.3f}R {m_ridge['spread_median']:<+21.3f}R {m_tree['spread_median']:<+21.3f}R")
        print(f"  {'[B] Top vs Bot Win Rate':<28} {m_null['top_wr']:<5.1f}% vs {m_null['bot_wr']:<5.1f}% {m_ridge['top_wr']:<5.1f}% vs {m_ridge['bot_wr']:<5.1f}%  {m_tree['top_wr']:<5.1f}% vs {m_tree['bot_wr']:<5.1f}%")
        print(f"  {'[B] Top vs Bot Total PnL':<28} ${m_null['top_pnl']:<+6.1f} vs ${m_null['bot_pnl']:<+6.1f} ${m_ridge['top_pnl']:<+6.1f} vs ${m_ridge['bot_pnl']:<+6.1f}  ${m_tree['top_pnl']:<+6.1f} vs ${m_tree['bot_pnl']:<+6.1f}")
        print(f"  {'[C] Top 20% Mean w/o Top 1':<28} {m_null['top_mean_no_outlier']:<+18.3f}R {m_ridge['top_mean_no_outlier']:<+21.3f}R {m_tree['top_mean_no_outlier']:<+21.3f}R")

        return m_null, m_ridge, m_tree

    # Run comparisons
    res_snap = evaluate_representation("Representation 1: Snapshot 14 (Baseline)", snapshot_14)
    res_seq = evaluate_representation("Representation 2: Sequence 9 (Pre-Breakout Structure)", sequence_9)
    res_comb = evaluate_representation("Representation 3: Combined 23 (Snapshot + Sequence)", combined_23)

    print("\n" + "=" * 100)
    print("  FEATURE INFORMATION TEST v2 COMPLETE.")
    print("=" * 100 + "\n")


if __name__ == "__main__":
    run_feature_information_test_v2()
