import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from scipy.stats import spearmanr, pearsonr
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV, Ridge


def run_expected_r_model():
    print("=" * 95)
    print("  QUANT AI EXPERIMENT v2: EXPECTED-R REGRESSION MODEL")
    print("  Objective: Predict E[Realized R | X] directly from 14 frozen breakout features")
    print("  Temporal Walk-Forward: Fit on Dev (2022-2023) -> Evaluate on Val (2024)")
    print("  Status: Diagnostic Benchmark (No Snooping, Frozen Features, Locked OOS)")
    print("=" * 95)

    data_dir = Path(__file__).parent / "data"
    dev_path = data_dir / "breakouts_dev_2022_2023.csv"
    val_path = data_dir / "breakouts_val_2024.csv"

    assert dev_path.exists(), f"Dev dataset not found: {dev_path}"
    assert val_path.exists(), f"Val dataset not found: {val_path}"

    dev_df = pd.read_csv(dev_path)
    val_df = pd.read_csv(val_path)

    feature_cols = [
        "channel_width_pct",
        "channel_width_change",
        "breakout_magnitude_pct",
        "breakout_close_position",
        "dist_to_ema200_pct",
        "ema50_slope_5",
        "natr",
        "atr_expansion",
        "vol_ratio",
        "breakout_volume_zscore",
        "asset_ret_24h",
        "asset_ret_7d",
        "btc_ret_24h",
        "btc_natr"
    ]

    print(f"\n[1] Data Ingestion & Target Selection:")
    print(f"  Dev (2022-2023): {len(dev_df)} trades")
    print(f"  Val (2024):      {len(val_df)} trades")
    print(f"  Primary Target:  'target_realized_r' (True economic outcome of frozen exit logic)")

    y_dev = dev_df["target_realized_r"].values
    y_val = val_df["target_realized_r"].values

    print(f"\n  Target Distribution (Realized R):")
    print(f"  Dev: Mean={y_dev.mean():+.3f}R, Median={np.median(y_dev):+.3f}R, Std={y_dev.std():.3f}R, Min={y_dev.min():+.3f}R, Max={y_dev.max():+.3f}R")
    print(f"  Val: Mean={y_val.mean():+.3f}R, Median={np.median(y_val):+.3f}R, Std={y_val.std():.3f}R, Min={y_val.min():+.3f}R, Max={y_val.max():+.3f}R")

    # 2. Standardize Features strictly on Dev
    scaler = StandardScaler()
    X_dev_raw = dev_df[feature_cols].values
    X_val_raw = val_df[feature_cols].values

    X_dev = scaler.fit_transform(X_dev_raw)
    X_val = scaler.transform(X_val_raw)

    # 3. Fit Regularized Linear Regression (Ridge)
    # Objective selection of alpha strictly via 5-fold CV on Dev
    candidate_alphas = [0.1, 1.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0]
    ridge_cv = RidgeCV(alphas=candidate_alphas, cv=5)
    ridge_cv.fit(X_dev, y_dev)
    best_alpha = float(ridge_cv.alpha_)

    print(f"\n[2] Model Architecture: Ridge Regression")
    print(f"  Hyperparameter: L2 Alpha selected strictly on Dev 5-Fold CV = {best_alpha:.1f}")

    # Final fit on entire Dev
    model = Ridge(alpha=best_alpha, random_state=42)
    model.fit(X_dev, y_dev)

    intercept = float(model.intercept_)
    coefs = model.coef_

    coef_df = pd.DataFrame({
        "Feature": feature_cols,
        "Dev_Mean": scaler.mean_,
        "Dev_Std": scaler.scale_,
        "Coefficient_Beta": coefs,
        "Abs_Impact": np.abs(coefs)
    }).sort_values(by="Abs_Impact", ascending=False).reset_index(drop=True)

    print(f"\n" + "=" * 95)
    print(f"  FROZEN ESTIMATED COEFFICIENTS: E[Realized R] = Intercept + sum(Beta_j * X_j)")
    print(f"  Model Intercept: {intercept:+.4f}R (Expected baseline outcome at average market state)")
    print("=" * 95)
    print(f"{'Feature':<26} {'Dev Mean':<10} {'Dev Std':<10} {'Beta (dR/dStd)':<16} {'Interpretation'}")
    print("-" * 95)
    for _, row in coef_df.iterrows():
        direction = "Positive Expectancy (+)" if row["Coefficient_Beta"] > 0 else "Negative Expectancy (-)"
        print(f"{row['Feature']:<26} {row['Dev_Mean']:<10.2f} {row['Dev_Std']:<10.2f} {row['Coefficient_Beta']:<+16.4f} {direction}")

    # Predict Expected R
    dev_preds = model.predict(X_dev)
    val_preds = model.predict(X_val)
    val_df["pred_r"] = val_preds

    # -------------------------------------------------------------------------
    # GATE A: PREDICTIVE EVALUATION (Val 2024)
    # -------------------------------------------------------------------------
    print(f"\n" + "=" * 95)
    print(f"  GATE A: PREDICTIVE METRICS ON VALIDATION SET (2024)")
    print("=" * 95)

    mae_dev = np.mean(np.abs(dev_preds - y_dev))
    mae_val = np.mean(np.abs(val_preds - y_val))
    rmse_dev = np.sqrt(np.mean((dev_preds - y_dev) ** 2))
    rmse_val = np.sqrt(np.mean((val_preds - y_val) ** 2))

    pearson_dev, p_p_dev = pearsonr(dev_preds, y_dev)
    pearson_val, p_p_val = pearsonr(val_preds, y_val)

    spearman_dev, p_s_dev = spearmanr(dev_preds, y_dev)
    spearman_val, p_s_val = spearmanr(val_preds, y_val)

    # Decile spread
    val_sorted_pred = val_df.sort_values(by="pred_r", ascending=False).reset_index(drop=True)
    decile_n = max(1, len(val_df) // 10)
    top_decile_actual_r = val_sorted_pred.iloc[:decile_n]["target_realized_r"].mean()
    bottom_decile_actual_r = val_sorted_pred.iloc[-decile_n:]["target_realized_r"].mean()
    decile_spread = top_decile_actual_r - bottom_decile_actual_r

    print(f"  Predictive Metric        Dev (2022-2023)    Val (2024)         Notes")
    print(f"  -----------------------  -----------------  -----------------  -----------------------------------")
    print(f"  MAE                      {mae_dev:.4f}R            {mae_val:.4f}R            (Lower = better)")
    print(f"  RMSE                     {rmse_dev:.4f}R            {rmse_val:.4f}R            (Lower = better)")
    print(f"  Pearson Correlation (r)  {pearson_dev:+.4f} (p={p_p_dev:.3f})   {pearson_val:+.4f} (p={p_p_val:.3f})   (Linear alignment)")
    print(f"  Spearman Rank Corr (rho) {spearman_dev:+.4f} (p={p_s_dev:.3f})   {spearman_val:+.4f} (p={p_s_val:.3f})   (Ranking alignment: CRITICAL)")
    print(f"  Top Decile Actual Mean   -                  {top_decile_actual_r:+.3f}R           (Mean of top 10% highest pred R)")
    print(f"  Bottom Decile Actual Mean -                 {bottom_decile_actual_r:+.3f}R           (Mean of bottom 10% lowest pred R)")
    print(f"  Decile Spread (Top-Bot)  -                  {decile_spread:+.3f}R           (Positive = monotonic separation)")

    # -------------------------------------------------------------------------
    # GATE B: ECONOMIC EVALUATION ACROSS QUINTILES & DECISION RULES (Val 2024)
    # -------------------------------------------------------------------------
    print(f"\n" + "=" * 95)
    print(f"  GATE B: ECONOMIC RANKING & BUCKET MONOTONICITY (Val 2024)")
    print("=" * 95)

    val_df["pred_bucket"] = pd.qcut(val_df["pred_r"], q=5, labels=["Q1 (Lowest E[R])", "Q2", "Q3", "Q4", "Q5 (Highest E[R])"])
    bucket_table = val_df.groupby("pred_bucket", observed=False).agg(
        trades=("pred_r", "count"),
        min_pred=("pred_r", "min"),
        max_pred=("pred_r", "max"),
        mean_pred=("pred_r", "mean"),
        actual_win_rate=("target_realized_r", lambda s: (s > 0).mean() * 100.0),
        actual_mean_r=("target_realized_r", "mean"),
        total_pnl=("net_pnl", "sum")
    ).reset_index()

    print(f"\n  Quintile Monotonicity Test on Val 2024:")
    print(f"  {'Bucket':<18} {'Trades':<8} {'Pred R Range':<20} {'Mean Pred R':<14} {'Win Rate':<12} {'Actual Mean R':<16} {'Total PnL ($)'}")
    print(f"  {'-'*18} {'-'*8} {'-'*20} {'-'*14} {'-'*12} {'-'*16} {'-'*14}")
    for _, r in bucket_table.iterrows():
        r_range = f"[{r['min_pred']:+.2f}R to {r['max_pred']:+.2f}R]"
        print(f"  {r['pred_bucket']:<18} {int(r['trades']):<8} {r_range:<20} {r['mean_pred']:<+14.3f}R {r['actual_win_rate']:<12.1f}% {r['actual_mean_r']:<+16.3f}R ${r['total_pnl']:<+14.2f}")

    # Helper function for economic comparison
    def compute_trade_metrics(sub_df: pd.DataFrame) -> Dict[str, Any]:
        if len(sub_df) == 0:
            return {
                "n_trades": 0, "net_pnl": 0.0, "mean_r": 0.0, "win_rate": 0.0,
                "profit_factor": 0.0, "total_fees": 0.0, "max_consecutive_losses": 0
            }
        wins = sub_df[sub_df["net_pnl"] > 0]["net_pnl"].sum()
        losses = abs(sub_df[sub_df["net_pnl"] < 0]["net_pnl"].sum())
        pf = (wins / losses) if losses > 0 else (99.0 if wins > 0 else 0.0)

        pnl_series = (sub_df["net_pnl"] > 0).astype(int)
        loss_streak = 0
        max_streak = 0
        for val in pnl_series:
            if val == 0:
                loss_streak += 1
                if loss_streak > max_streak:
                    max_streak = loss_streak
            else:
                loss_streak = 0

        return {
            "n_trades": len(sub_df),
            "net_pnl": sub_df["net_pnl"].sum(),
            "mean_r": sub_df["target_realized_r"].mean(),
            "win_rate": (sub_df["net_pnl"] > 0).mean() * 100.0,
            "profit_factor": pf,
            "total_fees": sub_df["fees"].sum(),
            "max_consecutive_losses": max_streak
        }

    control = compute_trade_metrics(val_df)

    # Pre-specified decision rules:
    # Rule 1: Positive Expectancy (Pred R >= 0.0R)
    # Rule 2: Dev Median Cutoff (Pred R >= median(dev_preds))
    # Rule 3: Dev Mean Cutoff (Pred R >= mean(dev_preds))
    dev_median_r = float(np.median(dev_preds))
    dev_mean_r = float(np.mean(dev_preds))

    rules = [
        ("Positive Expected R (Pred R >= 0.0R)", 0.0),
        ("Dev Median Cutoff (Pred R >= {:.3f}R)".format(dev_median_r), dev_median_r),
        ("Dev Mean Cutoff (Pred R >= {:.3f}R)".format(dev_mean_r), dev_mean_r)
    ]

    print(f"\n  Economic Treatment Comparison across Pre-Specified Decision Rules:")
    print(f"  {'Decision Rule':<38} {'Trades':<8} {'Net PnL ($)':<14} {'Mean R':<12} {'PF':<8} {'Win Rate':<10} {'Fees ($)':<10} {'Max Streak'}")
    print(f"  {'-'*38} {'-'*8} {'-'*14} {'-'*12} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
    print(f"  {'Control (No Filter)':<38} {control['n_trades']:<8} ${control['net_pnl']:<+13.2f} {control['mean_r']:<+11.3f}R {control['profit_factor']:<8.2f} {control['win_rate']:<9.1f}% ${control['total_fees']:<9.2f} {control['max_consecutive_losses']}")

    treatments = {}
    for rule_name, thresh in rules:
        treat_df = val_df[val_df["pred_r"] >= thresh]
        m = compute_trade_metrics(treat_df)
        treatments[rule_name] = (thresh, m, treat_df)
        print(f"  {rule_name:<38} {m['n_trades']:<8} ${m['net_pnl']:<+13.2f} {m['mean_r']:<+11.3f}R {m['profit_factor']:<8.2f} {m['win_rate']:<9.1f}% ${m['total_fees']:<9.2f} {m['max_consecutive_losses']}")

    # -------------------------------------------------------------------------
    # GATE C: TAIL WINNER PROTECTION AUDIT (Val 2024)
    # -------------------------------------------------------------------------
    print(f"\n" + "=" * 95)
    print(f"  GATE C: TAIL WINNER PROTECTION AUDIT (Val 2024)")
    print("=" * 95)

    val_sorted = val_df.sort_values(by="target_realized_r", ascending=False).reset_index(drop=True)
    top_10_pct_count = max(1, int(np.ceil(0.10 * len(val_sorted))))  # 7 trades

    top1 = val_sorted.iloc[0]
    top3 = val_sorted.iloc[:3]
    top5 = val_sorted.iloc[:5]
    top10pct = val_sorted.iloc[:top_10_pct_count]

    print(f"\n  Inspection of Top 7 Tail Winners in Val 2024:")
    print(f"  {'Rank':<6} {'Trade ID':<16} {'Asset':<10} {'Entry Time':<20} {'Realized R':<14} {'Net PnL ($)':<14} {'Predicted E[R]'}")
    print(f"  {'-'*6} {'-'*16} {'-'*10} {'-'*20} {'-'*14} {'-'*14} {'-'*16}")
    for idx, r in top10pct.iterrows():
        print(f"  #{idx+1:<5} {r['trade_id']:<16} {r['asset']:<10} {r['entry_time']:<20} {r['target_realized_r']:<+13.3f}R ${r['net_pnl']:<+13.2f} {r['pred_r']:<+15.3f}R")

    print(f"\n  Tail Retention Matrix by Pre-Specified Decision Rules:")
    print(f"  {'Decision Rule':<38} {'Top 1':<8} {'Top 3':<8} {'Top 5':<8} {'Top 10% (7)':<14} {'Retained R':<14} {'Rejected R'}")
    print(f"  {'-'*38} {'-'*8} {'-'*8} {'-'*8} {'-'*14} {'-'*14} {'-'*10}")

    for rule_name, thresh in rules:
        retained = val_df[val_df["pred_r"] >= thresh]
        rejected = val_df[val_df["pred_r"] < thresh]

        top1_kept = "✅ 1/1" if top1["pred_r"] >= thresh else "❌ 0/1"
        top3_kept = f"{sum(top3['pred_r'] >= thresh)}/3"
        top5_kept = f"{sum(top5['pred_r'] >= thresh)}/5"
        top10_kept = f"{sum(top10pct['pred_r'] >= thresh)}/{top_10_pct_count}"

        retained_r = retained["target_realized_r"].sum()
        rejected_r = rejected["target_realized_r"].sum()

        print(f"  {rule_name:<38} {top1_kept:<8} {top3_kept:<8} {top5_kept:<8} {top10_kept:<14} {retained_r:<+13.2f}R {rejected_r:<+10.2f}R")

    # -------------------------------------------------------------------------
    # Cross-Asset Breakdown
    # -------------------------------------------------------------------------
    print(f"\n" + "=" * 95)
    print(f"  CROSS-ASSET BREAKDOWN ON VAL 2024")
    print("=" * 95)
    print(f"  {'Asset':<10} {'Trades':<8} {'Mean Pred R':<14} {'Baseline PnL':<16} {'Filtered PnL (Pred R >= 0.0R)'}")
    print(f"  {'-'*10} {'-'*8} {'-'*14} {'-'*16} {'-'*30}")
    for asset in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]:
        sub_all = val_df[val_df["asset"] == asset]
        sub_filt = sub_all[sub_all["pred_r"] >= 0.0]
        mean_pr = sub_all["pred_r"].mean()
        pnl_base = sub_all["net_pnl"].sum()
        pnl_filt = sub_filt["net_pnl"].sum()
        print(f"  {asset:<10} {len(sub_all):<8} {mean_pr:<+14.3f}R ${pnl_base:<+15.2f} ${pnl_filt:<+28.2f}")

    print("\n" + "=" * 95)
    print("  EXPERIMENT v2 COMPLETE: Full Gates A, B, C logged.")
    print("=" * 95 + "\n")


if __name__ == "__main__":
    run_expected_r_model()
