import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
from typing import Dict, Any, List
from scipy.stats import spearmanr, pearsonr
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.tree import DecisionTreeRegressor, export_text


def run_oos_final_test():
    print("=" * 105)
    print("  OUT-OF-SAMPLE (OOS) FINAL CONFIRMATION TEST: 2025-01-01 -> 2026-10-02")
    print("  Status: Final Un-tampered Holdout Evaluation")
    print("  Rule: Zero Re-fitting on OOS, Zero Parameter Tuning, Frozen Dev/Val Models")
    print("=" * 105)

    data_dir = Path(__file__).parent / "data"
    dev_path = data_dir / "breakouts_dev_2022_2023.csv"
    val_path = data_dir / "breakouts_val_2024.csv"
    oos_path = data_dir / "breakouts_oos_2025_2026.csv"

    dev = pd.read_csv(dev_path)
    val = pd.read_csv(val_path)
    oos = pd.read_csv(oos_path)

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
    y_oos = oos["target_realized_r"].values

    print(f"\n[1] Data Partitions & Distribution:")
    print(f"  Dev (2022-2023): N = {len(dev):<3} | Mean R = {y_dev.mean():>+6.3f}R | WinRate = {(y_dev > 0).mean()*100:4.1f}% | Total PnL = ${dev['net_pnl'].sum():>+8.2f}")
    print(f"  Val (2024):      N = {len(val):<3} | Mean R = {y_val.mean():>+6.3f}R | WinRate = {(y_val > 0).mean()*100:4.1f}% | Total PnL = ${val['net_pnl'].sum():>+8.2f}")
    print(f"  OOS (2025-2026): N = {len(oos):<3} | Mean R = {y_oos.mean():>+6.3f}R | WinRate = {(y_oos > 0).mean()*100:4.1f}% | Total PnL = ${oos['net_pnl'].sum():>+8.2f}")

    # Temporal integrity check on OOS
    for idx, r in oos.iterrows():
        sig = pd.Timestamp(r["signal_time"])
        seq_src = pd.Timestamp(r["provenance_sequence_max_time"])
        btc_src = pd.Timestamp(r["provenance_btc_time"])
        assert seq_src < sig, f"OOS Leakage: seq time {seq_src} >= signal {sig}"
        assert btc_src <= sig, f"OOS Leakage: btc time {btc_src} > signal {sig}"
    print(f"  ✅ OOS Temporal Integrity: 100% of rows strictly satisfy zero lookahead assertions.")

    # -------------------------------------------------------------------------
    # Helper to evaluate on OOS
    # -------------------------------------------------------------------------
    def evaluate_model_on_oos(
        model_name: str,
        feature_set: List[str],
        model_type: str,
        alpha: float = 500.0,
        tree_depth: int = 2,
        tree_min_leaf: int = 15
    ) -> Dict[str, Any]:
        X_dev_raw = dev[feature_set].values
        X_oos_raw = oos[feature_set].values

        scaler = StandardScaler()
        X_dev_scaled = scaler.fit_transform(X_dev_raw)
        X_oos_scaled = scaler.transform(X_oos_raw)

        if model_type == "null":
            dev_pred = np.full_like(y_dev, fill_value=y_dev.mean())
            oos_pred = np.full_like(y_oos, fill_value=y_dev.mean())
            rules_str = "Constant prediction = Dev Mean"
        elif model_type == "ridge":
            model = Ridge(alpha=alpha, random_state=42)
            model.fit(X_dev_scaled, y_dev)
            oos_pred = model.predict(X_oos_scaled)
            rules_str = f"Ridge L2 alpha={alpha}"
        elif model_type == "tree":
            model = DecisionTreeRegressor(max_depth=tree_depth, min_samples_leaf=tree_min_leaf, random_state=42)
            model.fit(X_dev_raw, y_dev)
            oos_pred = model.predict(X_oos_raw)
            rules_str = export_text(model, feature_names=feature_set).strip()
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        # Metrics on OOS
        mae = float(np.mean(np.abs(oos_pred - y_oos)))
        rmse = float(np.sqrt(np.mean((oos_pred - y_oos) ** 2)))

        if np.all(oos_pred == oos_pred[0]):
            p_corr, p_pval = 0.0, 1.0
            s_corr, s_pval = 0.0, 1.0
            order = np.arange(len(y_oos))
        else:
            p_corr, p_pval = pearsonr(oos_pred, y_oos)
            s_corr, s_pval = spearmanr(oos_pred, y_oos)
            order = np.argsort(oos_pred)

        n_20 = max(1, int(len(y_oos) * 0.20))  # 24 trades in OOS (20% of 123)
        bot_idx = order[:n_20]
        top_idx = order[-n_20:]

        top_r = y_oos[top_idx]
        bot_r = y_oos[bot_idx]

        top_mean = float(np.mean(top_r))
        bot_mean = float(np.mean(bot_r))
        top_median = float(np.median(top_r))
        bot_median = float(np.median(bot_r))
        top_wr = float((top_r > 0).mean() * 100.0)
        bot_wr = float((bot_r > 0).mean() * 100.0)
        top_pnl = float(oos.iloc[top_idx]["net_pnl"].sum())
        bot_pnl = float(oos.iloc[bot_idx]["net_pnl"].sum())

        # Stability: drop top 1 winner from top 20%
        sorted_top_r = np.sort(top_r)
        top_mean_no_outlier = float(sorted_top_r[:-1].mean())
        top_pnl_no_outlier = float(oos.iloc[top_idx].sort_values("net_pnl")["net_pnl"].iloc[:-1].sum())

        return {
            "model_name": model_name,
            "rules": rules_str,
            "pred": oos_pred,
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
            "top_mean_no_outlier": top_mean_no_outlier,
            "top_pnl_no_outlier": top_pnl_no_outlier
        }

    # Models to test on OOS
    models = [
        ("Model 0: Null Baseline", snapshot_14, "null"),
        ("Model 1: Linear Ridge on Snapshot 14", snapshot_14, "ridge"),
        ("Model 2: Linear Ridge on Sequence 9", sequence_9, "ridge"),
        ("Model 3: Linear Ridge on Combined 23", combined_23, "ridge"),
        ("Model 4: Shallow Tree on Combined 23", combined_23, "tree"),
        ("Model 5: Shallow Tree on Sequence 9", sequence_9, "tree")
    ]

    results = []
    for name, f_set, m_type in models:
        res = evaluate_model_on_oos(name, f_set, m_type)
        results.append(res)

    print("\n" + "=" * 105)
    print("  OOS EVALUATION RESULTS MATRIX (2025-01-01 -> 2026-10-02, N = 123 Trades)")
    print("=" * 105)
    print(f"  {'Model Architecture':<36} {'Pearson r':<16} {'Spearman rho':<16} {'Top 20% Mean':<14} {'Bot 20% Mean':<14} {'Mean Spread'}")
    print(f"  {'-'*36} {'-'*16} {'-'*16} {'-'*14} {'-'*14} {'-'*12}")

    for r in results:
        p_str = f"{r['pearson']:>+6.3f} (p={r['pearson_p']:.3f})"
        s_str = f"{r['spearman']:>+6.3f} (p={r['spearman_p']:.3f})"
        print(f"  {r['model_name']:<36} {p_str:<16} {s_str:<16} {r['top_mean']:>+10.3f}R   {r['bot_mean']:>+10.3f}R   {r['spread_mean']:>+10.3f}R")

    print("\n" + "=" * 105)
    print("  ECONOMIC SEPARATION ON OOS (Top 20% vs Bottom 20%, N = 24 Trades each)")
    print("=" * 105)
    print(f"  {'Model Architecture':<36} {'Top PnL ($)':<14} {'Bot PnL ($)':<14} {'Top WinRate':<14} {'Bot WinRate':<14} {'Top Mean w/o Top 1'}")
    print(f"  {'-'*36} {'-'*14} {'-'*14} {'-'*14} {'-'*14} {'-'*18}")

    for r in results:
        print(f"  {r['model_name']:<36} ${r['top_pnl']:>+9.2f}    ${r['bot_pnl']:>+9.2f}    {r['top_wr']:>5.1f}%        {r['bot_wr']:>5.1f}%        {r['top_mean_no_outlier']:>+14.3f}R")

    # -------------------------------------------------------------------------
    # ANSWERING THE 3 CORE QUESTIONS
    # -------------------------------------------------------------------------
    print("\n" + "=" * 105)
    print("  SYNTHESIS: ANSWERING THE 3 OOS CONFIRMATION QUESTIONS")
    print("=" * 105)

    # Let's inspect Model 2 (Ridge on Sequence 9) and Model 4 (Tree on Combined 23) in detail
    m_ridge_seq = results[2]
    m_tree_comb = results[4]

    print("\n[QUESTION 1: DIRECTION - Did Top predicted outperform Bottom predicted?]")
    print(f"  Control Baseline (123 trades): Mean R = {y_oos.mean():+.3f}R, Total PnL = ${oos['net_pnl'].sum():+.2f}")
    print(f"  Model 2 (Linear Sequence 9):   Top 20% PnL = ${m_ridge_seq['top_pnl']:+.2f} ({m_ridge_seq['top_mean']:+.3f}R) vs Bot 20% PnL = ${m_ridge_seq['bot_pnl']:+.2f} ({m_ridge_seq['bot_mean']:+.3f}R)")
    print(f"  Model 4 (Tree Combined 23):    Top 20% PnL = ${m_tree_comb['top_pnl']:+.2f} ({m_tree_comb['top_mean']:+.3f}R) vs Bot 20% PnL = ${m_tree_comb['bot_pnl']:+.2f} ({m_tree_comb['bot_mean']:+.3f}R)")

    print("\n[QUESTION 2: MAGNITUDE - Did the economic spread survive OOS?]")
    print(f"  Model 2 (Linear Sequence 9):   Spread = {m_ridge_seq['spread_mean']:+.3f}R | PnL Spread = ${m_ridge_seq['top_pnl'] - m_ridge_seq['bot_pnl']:+.2f}")
    print(f"  Model 4 (Tree Combined 23):    Spread = {m_tree_comb['spread_mean']:+.3f}R | PnL Spread = ${m_tree_comb['top_pnl'] - m_tree_comb['bot_pnl']:+.2f}")

    print("\n[QUESTION 3: STABILITY - Does performance survive outlier removal?]")
    print(f"  Model 2 (Linear Sequence 9):   Top 20% Mean without Top 1 Winner = {m_ridge_seq['top_mean_no_outlier']:+.3f}R (PnL = ${m_ridge_seq['top_pnl_no_outlier']:+.2f})")
    print(f"  Model 4 (Tree Combined 23):    Top 20% Mean without Top 1 Winner = {m_tree_comb['top_mean_no_outlier']:+.3f}R (PnL = ${m_tree_comb['top_pnl_no_outlier']:+.2f})")

    # Top winners in OOS
    print("\n" + "=" * 105)
    print("  TAIL INSPECTION: TOP 5 WINNERS IN OOS (2025-2026)")
    print("=" * 105)
    oos_sorted = oos.sort_values(by="target_realized_r", ascending=False).reset_index(drop=True)
    top5_oos = oos_sorted.iloc[:5]
    print(f"  {'Rank':<6} {'Trade ID':<16} {'Asset':<10} {'Entry Time':<20} {'Realized R':<14} {'Net PnL ($)':<14}")
    print(f"  {'-'*6} {'-'*16} {'-'*10} {'-'*20} {'-'*14} {'-'*14}")
    for idx, r in top5_oos.iterrows():
        print(f"  #{idx+1:<5} {r['trade_id']:<16} {r['asset']:<10} {r['entry_time']:<20} {r['target_realized_r']:>+10.3f}R   ${r['net_pnl']:>+10.2f}")

    print("\n" + "=" * 105)
    print("  OOS FINAL CONFIRMATION TEST COMPLETED.")
    print("=" * 105 + "\n")


if __name__ == "__main__":
    run_oos_final_test()
