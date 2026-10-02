import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss


def run_baseline_model():
    print("=" * 95)
    print("  QUANT AI EXPERIMENT: LOGISTIC REGRESSION DIAGNOSTIC BASELINE")
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

    print(f"\n[1] Data Ingestion & Split:")
    print(f"  Dev (2022-2023): {len(dev_df)} trades (BTC={len(dev_df[dev_df['asset']=='BTCUSDT'])}, ETH={len(dev_df[dev_df['asset']=='ETHUSDT'])}, SOL={len(dev_df[dev_df['asset']=='SOLUSDT'])}, BNB={len(dev_df[dev_df['asset']=='BNBUSDT'])})")
    print(f"  Val (2024):      {len(val_df)} trades (BTC={len(val_df[val_df['asset']=='BTCUSDT'])}, ETH={len(val_df[val_df['asset']=='ETHUSDT'])}, SOL={len(val_df[val_df['asset']=='SOLUSDT'])}, BNB={len(val_df[val_df['asset']=='BNBUSDT'])})")

    # 14 Frozen Numeric Features
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

    print(f"\n[2] Feature Schema: All {len(feature_cols)} features locked without arbitrary pruning:")
    for i, col in enumerate(feature_cols, 1):
        print(f"  {i:02d}. {col}")

    # Target: Realized R > 0 (Binary Win vs Loss)
    y_dev = (dev_df["target_realized_r"] > 0).astype(int).values
    y_val = (val_df["target_realized_r"] > 0).astype(int).values

    dev_win_rate = y_dev.mean()
    val_win_rate = y_val.mean()
    print(f"\n[3] Target Distribution (y = target_realized_r > 0):")
    print(f"  Dev Base Rate: {dev_win_rate * 100:.2f}% ({y_dev.sum()}/{len(y_dev)} wins)")
    print(f"  Val Base Rate: {val_win_rate * 100:.2f}% ({y_val.sum()}/{len(y_val)} wins)")

    # 4. Standard Scaler strictly fit on Dev
    scaler = StandardScaler()
    X_dev_raw = dev_df[feature_cols].values
    X_val_raw = val_df[feature_cols].values

    X_dev = scaler.fit_transform(X_dev_raw)
    X_val = scaler.transform(X_val_raw)

    # 5. Fit Logistic Regression with L2 Regularization
    # C=1.0 default L2 penalty
    model = LogisticRegression(penalty="l2", C=1.0, solver="lbfgs", random_state=42)
    model.fit(X_dev, y_dev)

    # 6. Report Frozen Coefficients & Odds Ratios
    intercept = float(model.intercept_[0])
    coefs = model.coef_[0]

    coef_df = pd.DataFrame({
        "Feature": feature_cols,
        "Dev_Mean": scaler.mean_,
        "Dev_Std": scaler.scale_,
        "Coefficient_Beta": coefs,
        "Odds_Ratio": np.exp(coefs),
        "Abs_Impact": np.abs(coefs)
    }).sort_values(by="Abs_Impact", ascending=False).reset_index(drop=True)

    print(f"\n" + "=" * 95)
    print(f"  FROZEN ESTIMATED COEFFICIENTS (Fit strictly on Dev 2022-2023)")
    print(f"  Model Intercept: {intercept:+.4f} (Base Log-Odds, Baseline Win Prob = {1/(1+np.exp(-intercept))*100:.1f}%)")
    print("=" * 95)
    print(f"{'Feature':<26} {'Dev Mean':<10} {'Dev Std':<10} {'Beta':<10} {'Odds Ratio':<12} {'Interpretation'}")
    print("-" * 95)
    for _, row in coef_df.iterrows():
        direction = "Positive (+)" if row["Coefficient_Beta"] > 0 else "Negative (-)"
        print(f"{row['Feature']:<26} {row['Dev_Mean']:<10.2f} {row['Dev_Std']:<10.2f} {row['Coefficient_Beta']:<+10.4f} {row['Odds_Ratio']:<12.4f} {direction}")

    # Predict Probabilities
    dev_probs = model.predict_proba(X_dev)[:, 1]
    val_probs = model.predict_proba(X_val)[:, 1]
    val_df["pred_prob"] = val_probs

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

    # Naive Brier Score (predicting constant historical base rate dev_win_rate)
    naive_brier_val = np.mean((val_win_rate - y_val) ** 2)
    climatology_brier_val = np.mean((dev_win_rate - y_val) ** 2)
    brier_skill_score = 1.0 - (brier_val / climatology_brier_val)

    print(f"  Predictive Metric        Dev (2022-2023)    Val (2024)         Notes")
    print(f"  -----------------------  -----------------  -----------------  -----------------------------------")
    print(f"  ROC-AUC                  {roc_auc_dev:.4f}             {roc_auc_val:.4f}             (0.50 = random)")
    print(f"  PR-AUC (Avg Precision)   {pr_auc_dev:.4f}             {pr_auc_val:.4f}             (Val Prior = {val_win_rate:.4f})")
    print(f"  Brier Score              {brier_dev:.4f}             {brier_val:.4f}             (Lower = better)")
    print(f"  Naive Brier (Prior)      -                  {climatology_brier_val:.4f}             (Climatology from Dev)")
    print(f"  Brier Skill Score (BSS)  -                  {brier_skill_score:+.4f}             (> 0 means superior to prior)")

    # Ranking Quality by Probability Quintiles on Val
    print(f"\n  Ranking Quality on Val 2024 by Probability Quintiles:")
    val_df["prob_bucket"] = pd.qcut(val_df["pred_prob"], q=5, labels=["Q1 (Lowest)", "Q2", "Q3", "Q4", "Q5 (Highest)"])
    ranking_table = val_df.groupby("prob_bucket", observed=False).agg(
        trades=("pred_prob", "count"),
        min_p=("pred_prob", "min"),
        max_p=("pred_prob", "max"),
        mean_p=("pred_prob", "mean"),
        actual_win_rate=("target_realized_r", lambda s: (s > 0).mean() * 100.0),
        mean_realized_r=("target_realized_r", "mean"),
        total_pnl=("net_pnl", "sum")
    ).reset_index()

    print(f"  {'Bucket':<14} {'Trades':<8} {'Prob Range':<16} {'Mean P':<10} {'Win Rate':<12} {'Mean R':<12} {'Total PnL ($)'}")
    print(f"  {'-'*14} {'-'*8} {'-'*16} {'-'*10} {'-'*12} {'-'*12} {'-'*14}")
    for _, r in ranking_table.iterrows():
        p_range = f"[{r['min_p']:.2f} - {r['max_p']:.2f}]"
        print(f"  {r['prob_bucket']:<14} {int(r['trades']):<8} {p_range:<16} {r['mean_p']:<10.3f} {r['actual_win_rate']:<12.1f}% {r['mean_realized_r']:<+12.3f}R ${r['total_pnl']:<+14.2f}")

    # -------------------------------------------------------------------------
    # GATE B: ECONOMIC EVALUATION (Val 2024)
    # -------------------------------------------------------------------------
    print(f"\n" + "=" * 95)
    print(f"  GATE B: ECONOMIC COMPARISON ON VAL 2024 (Control vs Treatment)")
    print("=" * 95)

    # Pre-specified decision rules:
    # Rule 1: Prior base rate threshold p >= dev_win_rate (0.297)
    # Rule 2: Standard classifier threshold p >= 0.50
    # Rule 3: Median Dev probability threshold p >= median(dev_probs)
    median_dev_p = float(np.median(dev_probs))
    rules = [
        ("Base Rate Cutoff (p >= 0.297)", dev_win_rate),
        ("Median Dev Cutoff (p >= {:.3f})".format(median_dev_p), median_dev_p),
        ("High Conviction (p >= 0.500)", 0.50)
    ]

    # Calculate metrics for a subset of trades
    def compute_trade_metrics(sub_df: pd.DataFrame) -> Dict[str, Any]:
        if len(sub_df) == 0:
            return {
                "n_trades": 0, "net_pnl": 0.0, "mean_r": 0.0, "win_rate": 0.0,
                "profit_factor": 0.0, "total_fees": 0.0, "max_consecutive_losses": 0
            }
        wins = sub_df[sub_df["net_pnl"] > 0]["net_pnl"].sum()
        losses = abs(sub_df[sub_df["net_pnl"] < 0]["net_pnl"].sum())
        pf = (wins / losses) if losses > 0 else (99.0 if wins > 0 else 0.0)

        # Max loss streak
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
            "max_consecutive_losses": max_streak,
            "total_bars_held": sub_df["target_holding_bars"].sum() if "target_holding_bars" in sub_df.columns else 0
        }

    control_metrics = compute_trade_metrics(val_df)

    print(f"\n  Baseline Control: 100% of trades accepted (N = {control_metrics['n_trades']})")
    print(f"  PnL: ${control_metrics['net_pnl']:+.2f} | Mean R: {control_metrics['mean_r']:+.3f}R | PF: {control_metrics['profit_factor']:.2f} | Fees: ${control_metrics['total_fees']:.2f} | Max Loss Streak: {control_metrics['max_consecutive_losses']}")

    print(f"\n  Treatment Comparisons across Pre-Specified Decision Rules:")
    print(f"  {'Decision Rule':<32} {'Trades':<8} {'Net PnL ($)':<14} {'Mean R':<12} {'PF':<8} {'Win Rate':<10} {'Fees ($)':<10} {'Max Streak'}")
    print(f"  {'-'*32} {'-'*8} {'-'*14} {'-'*12} {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
    print(f"  {'Control (No Filter)':<32} {control_metrics['n_trades']:<8} ${control_metrics['net_pnl']:<+13.2f} {control_metrics['mean_r']:<+11.3f}R {control_metrics['profit_factor']:<8.2f} {control_metrics['win_rate']:<9.1f}% ${control_metrics['total_fees']:<9.2f} {control_metrics['max_consecutive_losses']}")

    treatments = {}
    for rule_name, threshold in rules:
        treat_df = val_df[val_df["pred_prob"] >= threshold]
        t_metrics = compute_trade_metrics(treat_df)
        treatments[rule_name] = (threshold, t_metrics, treat_df)
        pnl_diff = t_metrics['net_pnl'] - control_metrics['net_pnl']
        print(f"  {rule_name:<32} {t_metrics['n_trades']:<8} ${t_metrics['net_pnl']:<+13.2f} {t_metrics['mean_r']:<+11.3f}R {t_metrics['profit_factor']:<8.2f} {t_metrics['win_rate']:<9.1f}% ${t_metrics['total_fees']:<9.2f} {t_metrics['max_consecutive_losses']}")

    # -------------------------------------------------------------------------
    # GATE C: TAIL PROTECTION AUDIT (Val 2024)
    # -------------------------------------------------------------------------
    print(f"\n" + "=" * 95)
    print(f"  GATE C: TAIL WINNER PROTECTION AUDIT (Val 2024)")
    print("=" * 95)

    val_sorted = val_df.sort_values(by="target_realized_r", ascending=False).reset_index(drop=True)
    n_val = len(val_sorted)
    top_10_pct_count = max(1, int(np.ceil(0.10 * n_val)))  # Top 7 trades in Val

    top1 = val_sorted.iloc[0]
    top3 = val_sorted.iloc[:3]
    top5 = val_sorted.iloc[:5]
    top10pct = val_sorted.iloc[:top_10_pct_count]

    print(f"\n  Inspection of Top 7 Tail Winners in Val 2024 (Realized R > +4.0R):")
    print(f"  {'Rank':<6} {'Trade ID':<16} {'Asset':<10} {'Entry Time':<20} {'Realized R':<14} {'Net PnL ($)':<14} {'Model Prob'}")
    print(f"  {'-'*6} {'-'*16} {'-'*10} {'-'*20} {'-'*14} {'-'*14} {'-'*10}")
    for idx, r in top10pct.iterrows():
        print(f"  #{idx+1:<5} {r['trade_id']:<16} {r['asset']:<10} {r['entry_time']:<20} {r['target_realized_r']:<+13.3f}R ${r['net_pnl']:<+13.2f} {r['pred_prob']:.4f}")

    print(f"\n  Tail Retention Matrix by Pre-Specified Decision Rules:")
    print(f"  {'Decision Rule':<32} {'Top 1':<8} {'Top 3':<8} {'Top 5':<8} {'Top 10% (7)':<14} {'Retained R':<14} {'Rejected R'}")
    print(f"  {'-'*32} {'-'*8} {'-'*8} {'-'*8} {'-'*14} {'-'*14} {'-'*10}")

    for rule_name, threshold in rules:
        retained = val_df[val_df["pred_prob"] >= threshold]
        rejected = val_df[val_df["pred_prob"] < threshold]

        top1_kept = "✅ 1/1" if top1["pred_prob"] >= threshold else "❌ 0/1"
        top3_kept = f"{sum(top3['pred_prob'] >= threshold)}/3"
        top5_kept = f"{sum(top5['pred_prob'] >= threshold)}/5"
        top10_kept = f"{sum(top10pct['pred_prob'] >= threshold)}/{top_10_pct_count}"

        retained_r = retained["target_realized_r"].sum()
        rejected_r = rejected["target_realized_r"].sum()

        print(f"  {rule_name:<32} {top1_kept:<8} {top3_kept:<8} {top5_kept:<8} {top10_kept:<14} {retained_r:<+13.2f}R {rejected_r:<+10.2f}R")

    # -------------------------------------------------------------------------
    # Cross-Asset Diagnostic: Did model learn asset identity?
    # -------------------------------------------------------------------------
    print(f"\n" + "=" * 95)
    print(f"  CROSS-ASSET BREAKDOWN ON VAL 2024 (Checking for Asset-Identity Bias)")
    print("=" * 95)
    print(f"  {'Asset':<10} {'Trades':<8} {'Mean Prob':<12} {'Baseline PnL':<15} {'Filtered PnL (p>=0.297)':<24} {'Filtered PnL (p>=0.50)'}")
    print(f"  {'-'*10} {'-'*8} {'-'*12} {'-'*15} {'-'*24} {'-'*22}")
    for asset in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]:
        sub_all = val_df[val_df["asset"] == asset]
        sub_p1 = sub_all[sub_all["pred_prob"] >= dev_win_rate]
        sub_p3 = sub_all[sub_all["pred_prob"] >= 0.50]
        mean_p = sub_all["pred_prob"].mean()
        pnl_base = sub_all["net_pnl"].sum()
        pnl_p1 = sub_p1["net_pnl"].sum()
        pnl_p3 = sub_p3["net_pnl"].sum()
        print(f"  {asset:<10} {len(sub_all):<8} {mean_p:<12.3f} ${pnl_base:<+14.2f} ${pnl_p1:<+23.2f} ${pnl_p3:<+21.2f}")

    print("\n" + "=" * 95)
    print("  EXPERIMENT COMPLETE: Full Gates A, B, C logged.")
    print("=" * 95 + "\n")


if __name__ == "__main__":
    run_baseline_model()
