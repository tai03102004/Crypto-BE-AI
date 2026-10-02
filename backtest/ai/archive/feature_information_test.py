import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, pearsonr
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.tree import DecisionTreeRegressor, export_text


def run_feature_information_test():
    print("=" * 95)
    print("  FEATURE INFORMATION TEST v1: TESTING PREDICTIVE CONTENT IN 14 BREAKOUT FEATURES")
    print("  Question: Does the frozen 14-feature snapshot contain predictive signal for Realized R?")
    print("  Design: 3 Fixed Complexity Levels (Null -> Linear Ridge -> Single Shallow Tree)")
    print("  Rule: Strictly No Grid Search, No Model Shopping, Locked OOS 2025-2026")
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

    X_dev_raw = dev_df[feature_cols].values
    y_dev = dev_df["target_realized_r"].values

    X_val_raw = val_df[feature_cols].values
    y_val = val_df["target_realized_r"].values

    # Preprocessing strictly on Dev
    scaler = StandardScaler()
    X_dev_scaled = scaler.fit_transform(X_dev_raw)
    X_val_scaled = scaler.transform(X_val_raw)

    print(f"\n[1] Partitions & Target:")
    print(f"  Dev (2022-2023): N = {len(dev_df)} trades | Mean R = {y_dev.mean():+.3f}R | Std = {y_dev.std():.3f}R")
    print(f"  Val (2024):      N = {len(val_df)} trades  | Mean R = {y_val.mean():+.3f}R | Std = {y_val.std():.3f}R")

    # =========================================================================
    # MODEL 0: NULL MODEL (Climatology / Prior Mean Baseline)
    # =========================================================================
    null_dev_pred = np.full_like(y_dev, fill_value=y_dev.mean())
    null_val_pred = np.full_like(y_val, fill_value=y_dev.mean())

    # =========================================================================
    # MODEL 1: LINEAR HYPOTHESIS (Ridge Regression, alpha=200 from Dev 5-Fold CV)
    # =========================================================================
    ridge = Ridge(alpha=200.0, random_state=42)
    ridge.fit(X_dev_scaled, y_dev)
    ridge_dev_pred = ridge.predict(X_dev_scaled)
    ridge_val_pred = ridge.predict(X_val_scaled)

    # =========================================================================
    # MODEL 2: NONLINEAR HYPOTHESIS (Single Shallow Decision Tree)
    # Fixed a priori: max_depth=2, min_samples_leaf=15 (Strictly NO tuning on Val!)
    # =========================================================================
    tree = DecisionTreeRegressor(
        max_depth=2,
        min_samples_leaf=15,
        random_state=42
    )
    # Note: Decision trees are scale-invariant, can use raw features for maximum readability
    tree.fit(X_dev_raw, y_dev)
    tree_dev_pred = tree.predict(X_dev_raw)
    tree_val_pred = tree.predict(X_val_raw)

    print(f"\n[2] Inspected Shallow Tree Architecture (max_depth=2, min_samples_leaf=15):")
    tree_rules = export_text(tree, feature_names=feature_cols)
    print("  " + "\n  ".join(tree_rules.strip().split("\n")))

    # =========================================================================
    # METRICS EVALUATION
    # =========================================================================
    def evaluate_model(name: str, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
        mae = float(np.mean(np.abs(y_pred - y_true)))
        rmse = float(np.sqrt(np.mean((y_pred - y_true) ** 2)))
        
        # If all predictions are identical (Null model), correlation is undefined (0.0)
        if np.all(y_pred == y_pred[0]):
            p_corr, p_pval = 0.0, 1.0
            s_corr, s_pval = 0.0, 1.0
            top20_mean = float(y_true.mean())
            bot20_mean = float(y_true.mean())
        else:
            p_corr, p_pval = pearsonr(y_pred, y_true)
            s_corr, s_pval = spearmanr(y_pred, y_true)
            
            # Sort by predicted R
            order = np.argsort(y_pred)
            n_20 = max(1, int(len(y_true) * 0.20))
            bot20_idx = order[:n_20]
            top20_idx = order[-n_20:]
            bot20_mean = float(np.mean(y_true[bot20_idx]))
            top20_mean = float(np.mean(y_true[top20_idx]))

        spread = top20_mean - bot20_mean
        return {
            "name": name,
            "mae": mae,
            "rmse": rmse,
            "pearson": p_corr,
            "pearson_pval": p_pval,
            "spearman": s_corr,
            "spearman_pval": s_pval,
            "top20_mean": top20_mean,
            "bot20_mean": bot20_mean,
            "spread": spread
        }

    null_val_res = evaluate_model("Model 0: Null Model (Prior Mean)", y_val, null_val_pred)
    ridge_val_res = evaluate_model("Model 1: Linear Ridge (alpha=200)", y_val, ridge_val_pred)
    tree_val_res = evaluate_model("Model 2: Shallow Tree (depth=2)", y_val, tree_val_pred)

    null_dev_res = evaluate_model("Model 0: Null Model (Dev)", y_dev, null_dev_pred)
    ridge_dev_res = evaluate_model("Model 1: Linear Ridge (Dev)", y_dev, ridge_dev_pred)
    tree_dev_res = evaluate_model("Model 2: Shallow Tree (Dev)", y_dev, tree_dev_pred)

    print(f"\n" + "=" * 95)
    print(f"  GATE A: PRIMARY INFORMATION COMPARISON ON VAL (2024)")
    print("=" * 95)
    print(f"  {'Metric':<28} {'Model 0: Null':<18} {'Model 1: Ridge':<18} {'Model 2: Shallow Tree':<22}")
    print(f"  {'-'*28} {'-'*18} {'-'*18} {'-'*22}")
    print(f"  {'MAE':<28} {null_val_res['mae']:<18.4f}R {ridge_val_res['mae']:<18.4f}R {tree_val_res['mae']:<22.4f}R")
    print(f"  {'RMSE':<28} {null_val_res['rmse']:<18.4f}R {ridge_val_res['rmse']:<18.4f}R {tree_val_res['rmse']:<22.4f}R")
    print(f"  {'Pearson Correlation (r)':<28} {null_val_res['pearson']:<+18.4f} {ridge_val_res['pearson']:<+18.4f} {tree_val_res['pearson']:<+22.4f}")
    print(f"  {'Pearson p-value':<28} {null_val_res['pearson_pval']:<18.3f} {ridge_val_res['pearson_pval']:<18.3f} {tree_val_res['pearson_pval']:<22.3f}")
    print(f"  {'Spearman Rank Corr (rho)':<28} {null_val_res['spearman']:<+18.4f} {ridge_val_res['spearman']:<+18.4f} {tree_val_res['spearman']:<+22.4f}")
    print(f"  {'Spearman p-value':<28} {null_val_res['spearman_pval']:<18.3f} {ridge_val_res['spearman_pval']:<18.3f} {tree_val_res['spearman_pval']:<22.3f}")
    print(f"  {'Top 20% Actual Mean R':<28} {null_val_res['top20_mean']:<+18.3f}R {ridge_val_res['top20_mean']:<+18.3f}R {tree_val_res['top20_mean']:<+22.3f}R")
    print(f"  {'Bottom 20% Actual Mean R':<28} {null_val_res['bot20_mean']:<+18.3f}R {ridge_val_res['bot20_mean']:<+18.3f}R {tree_val_res['bot20_mean']:<+22.3f}R")
    print(f"  {'Spread (Top 20% - Bot 20%)':<28} {null_val_res['spread']:<+18.3f}R {ridge_val_res['spread']:<+18.3f}R {tree_val_res['spread']:<+22.3f}R")

    print(f"\n" + "=" * 95)
    print(f"  REFERENCE: IN-SAMPLE BENCHMARK ON DEV (2022-2023)")
    print("=" * 95)
    print(f"  {'Metric':<28} {'Model 0: Null':<18} {'Model 1: Ridge':<18} {'Model 2: Shallow Tree':<22}")
    print(f"  {'-'*28} {'-'*18} {'-'*18} {'-'*22}")
    print(f"  {'Spearman Rank Corr (rho)':<28} {null_dev_res['spearman']:<+18.4f} {ridge_dev_res['spearman']:<+18.4f} {tree_dev_res['spearman']:<+22.4f}")
    print(f"  {'Pearson Correlation (r)':<28} {null_dev_res['pearson']:<+18.4f} {ridge_dev_res['pearson']:<+18.4f} {tree_dev_res['pearson']:<+22.4f}")
    print(f"  {'Spread (Top 20% - Bot 20%)':<28} {null_dev_res['spread']:<+18.3f}R {ridge_dev_res['spread']:<+18.3f}R {tree_dev_res['spread']:<+22.3f}R")

    # Quintile detail for Shallow Tree on Val
    val_df["tree_pred"] = tree_val_pred
    val_df["tree_leaf"] = tree.apply(X_val_raw)
    print(f"\n" + "=" * 95)
    print(f"  SHALLOW TREE LEAF BREAKDOWN ON VAL 2024:")
    print("=" * 95)
    leaf_summary = val_df.groupby("tree_leaf").agg(
        trades=("tree_pred", "count"),
        pred_r=("tree_pred", "mean"),
        actual_win_rate=("target_realized_r", lambda s: (s > 0).mean() * 100.0),
        actual_mean_r=("target_realized_r", "mean"),
        total_pnl=("net_pnl", "sum")
    ).reset_index()
    print(f"  {'Leaf Node':<12} {'Trades':<8} {'Predicted R':<16} {'Actual Win Rate':<18} {'Actual Mean R':<18} {'Total PnL ($)'}")
    print(f"  {'-'*12} {'-'*8} {'-'*16} {'-'*18} {'-'*18} {'-'*14}")
    for _, row in leaf_summary.iterrows():
        print(f"  Node #{int(row['tree_leaf']):<6} {int(row['trades']):<8} {row['pred_r']:<+16.3f}R {row['actual_win_rate']:<18.1f}% {row['actual_mean_r']:<+18.3f}R ${row['total_pnl']:<+14.2f}")

    print("\n" + "=" * 95)
    print("  FEATURE INFORMATION TEST v1 COMPLETE.")
    print("=" * 95 + "\n")


if __name__ == "__main__":
    run_feature_information_test()
