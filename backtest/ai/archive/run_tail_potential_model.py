import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
from typing import Dict, Any, List
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss


def run_tail_potential_model():
    print("=" * 95)
    print("  QUANT AI EXPERIMENT v3: TAIL-POTENTIAL CLASSIFIER")
    print("  Objective: Predict P(MFE >= 2.0R | X) - Excursion & Runner Discovery")
    print("  Temporal Walk-Forward: Fit on Dev (2022-2023) -> Evaluate on Val (2024)")
    print("  Status: Diagnostic Benchmark (No Snooping, Frozen Features, Locked OOS)")
    print("=" * 95)

    data_dir = Path(__file__).parent / "data"
    dev_path = data_dir / "breakouts_dev_2022_2023.csv"
    val_path = data_dir / "breakouts_val_2024.csv"

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

    # Target: MFE >= 2.0R (Setup has potential to expand at least 2 risk units favorably)
    y_dev = (dev_df["target_mfe_r"] >= 2.0).astype(int).values
    y_val = (val_df["target_mfe_r"] >= 2.0).astype(int).values

    dev_rate = y_dev.mean()
    val_rate = y_val.mean()

    print(f"\n[1] Target Definition: target_mfe_r >= 2.0R")
    print(f"  Dev Base Rate: {dev_rate * 100:.2f}% ({y_dev.sum()}/{len(y_dev)} trades with MFE >= 2R)")
    print(f"  Val Base Rate: {val_rate * 100:.2f}% ({y_val.sum()}/{len(y_val)} trades with MFE >= 2R)")

    # Standardize
    scaler = StandardScaler()
    X_dev = scaler.fit_transform(dev_df[feature_cols].values)
    X_val = scaler.transform(val_df[feature_cols].values)

    # Fit Logistic Regression
    model = LogisticRegression(penalty="l2", C=1.0, solver="lbfgs", random_state=42)
    model.fit(X_dev, y_dev)

    intercept = float(model.intercept_[0])
    coefs = model.coef_[0]

    coef_df = pd.DataFrame({
        "Feature": feature_cols,
        "Dev_Mean": scaler.mean_,
        "Dev_Std": scaler.scale_,
        "Beta": coefs,
        "Odds_Ratio": np.exp(coefs),
        "Abs_Impact": np.abs(coefs)
    }).sort_values(by="Abs_Impact", ascending=False).reset_index(drop=True)

    print(f"\n" + "=" * 95)
    print(f"  FROZEN ESTIMATED COEFFICIENTS: P(MFE >= 2.0R)")
    print(f"  Model Intercept: {intercept:+.4f} (Base Probability = {1/(1+np.exp(-intercept))*100:.1f}%)")
    print("=" * 95)
    print(f"{'Feature':<26} {'Dev Mean':<10} {'Dev Std':<10} {'Beta':<10} {'Odds Ratio':<12} {'Interpretation'}")
    print("-" * 95)
    for _, row in coef_df.iterrows():
        direction = "Expands Tail (+)" if row["Beta"] > 0 else "Compresses Tail (-)"
        print(f"{row['Feature']:<26} {row['Dev_Mean']:<10.2f} {row['Dev_Std']:<10.2f} {row['Beta']:<+10.4f} {row['Odds_Ratio']:<12.4f} {direction}")

    dev_probs = model.predict_proba(X_dev)[:, 1]
    val_probs = model.predict_proba(X_val)[:, 1]
    val_df["tail_prob"] = val_probs

    # -------------------------------------------------------------------------
    # GATE A: PREDICTIVE METRICS (Val 2024)
    # -------------------------------------------------------------------------
    print(f"\n" + "=" * 95)
    print(f"  GATE A: PREDICTIVE EVALUATION ON VALIDATION SET (2024)")
    print("=" * 95)

    roc_auc_dev = roc_auc_score(y_dev, dev_probs)
    roc_auc_val = roc_auc_score(y_val, val_probs)
    pr_auc_dev = average_precision_score(y_dev, dev_probs)
    pr_auc_val = average_precision_score(y_val, val_probs)

    brier_dev = brier_score_loss(y_dev, dev_probs)
    brier_val = brier_score_loss(y_val, val_probs)
    climatology_brier_val = np.mean((dev_rate - y_val) ** 2)
    brier_skill_score = 1.0 - (brier_val / climatology_brier_val)

    print(f"  Predictive Metric        Dev (2022-2023)    Val (2024)         Notes")
    print(f"  -----------------------  -----------------  -----------------  -----------------------------------")
    print(f"  ROC-AUC                  {roc_auc_dev:.4f}             {roc_auc_val:.4f}             (0.50 = random)")
    print(f"  PR-AUC (Avg Precision)   {pr_auc_dev:.4f}             {pr_auc_val:.4f}             (Val Prior = {val_rate:.4f})")
    print(f"  Brier Score              {brier_dev:.4f}             {brier_val:.4f}             (Lower = better)")
    print(f"  Naive Brier (Prior)      -                  {climatology_brier_val:.4f}             (Climatology from Dev)")
    print(f"  Brier Skill Score (BSS)  -                  {brier_skill_score:+.4f}             (> 0 means superior to prior)")

    # Quintile breakdown
    val_df["prob_bucket"] = pd.qcut(val_df["tail_prob"], q=5, labels=["Q1 (Lowest)", "Q2", "Q3", "Q4", "Q5 (Highest)"])
    ranking = val_df.groupby("prob_bucket", observed=False).agg(
        trades=("tail_prob", "count"),
        mean_p=("tail_prob", "mean"),
        actual_hit_rate=("target_mfe_r", lambda s: (s >= 2.0).mean() * 100.0),
        mean_mfe_r=("target_mfe_r", "mean"),
        actual_realized_r=("target_realized_r", "mean"),
        total_pnl=("net_pnl", "sum")
    ).reset_index()

    print(f"\n  Quintile Monotonicity Test on Val 2024 (P(MFE >= 2R)):")
    print(f"  {'Bucket':<14} {'Trades':<8} {'Mean Prob':<12} {'MFE>=2R %':<12} {'Mean MFE R':<14} {'Mean Realized R':<18} {'Total PnL ($)'}")
    print(f"  {'-'*14} {'-'*8} {'-'*12} {'-'*12} {'-'*14} {'-'*18} {'-'*14}")
    for _, r in ranking.iterrows():
        print(f"  {r['prob_bucket']:<14} {int(r['trades']):<8} {r['mean_p']:<12.3f} {r['actual_hit_rate']:<12.1f}% {r['mean_mfe_r']:<+14.3f}R {r['actual_realized_r']:<+18.3f}R ${r['total_pnl']:<+14.2f}")

    # -------------------------------------------------------------------------
    # GATE C: TAIL PROTECTION AUDIT
    # -------------------------------------------------------------------------
    print(f"\n" + "=" * 95)
    print(f"  GATE C: TAIL WINNER AUDIT (How does Tail-Potential Model score the top winners?)")
    print("=" * 95)

    val_sorted = val_df.sort_values(by="target_realized_r", ascending=False).reset_index(drop=True)
    top10pct = val_sorted.iloc[:7]

    print(f"\n  Inspection of Top 7 Tail Winners in Val 2024:")
    print(f"  {'Rank':<6} {'Trade ID':<16} {'Asset':<10} {'Entry Time':<20} {'Realized R':<14} {'MFE R':<12} {'Tail Prob P(MFE>=2R)'}")
    print(f"  {'-'*6} {'-'*16} {'-'*10} {'-'*20} {'-'*14} {'-'*12} {'-'*22}")
    for idx, r in top10pct.iterrows():
        print(f"  #{idx+1:<5} {r['trade_id']:<16} {r['asset']:<10} {r['entry_time']:<20} {r['target_realized_r']:<+13.3f}R {r['target_mfe_r']:<+11.2f}R {r['tail_prob']:.4f}")

    print("\n" + "=" * 95)
    print("  EXPERIMENT v3 COMPLETE: Tail-Potential Classifier logged.")
    print("=" * 95 + "\n")


if __name__ == "__main__":
    run_tail_potential_model()
