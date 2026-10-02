import sys
import hashlib
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


def compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def freeze_ai_model():
    print("=" * 90)
    print("  AI FILTER MODEL FREEZE: EXPORTING PRODUCTION ARTIFACTS")
    print("  Period: 2022-01-01 -> 2024-12-31 (Dev + Val, N = 193)")
    print("  Architecture: Linear Ridge (alpha = 500.0) | Representation: Combined 23")
    print("=" * 90)

    data_dir = Path(__file__).parent / "data"
    dev_path = data_dir / "breakouts_dev_2022_2023.csv"
    val_path = data_dir / "breakouts_val_2024.csv"

    dev = pd.read_csv(dev_path)
    val = pd.read_csv(val_path)
    train_df = pd.concat([dev, val], ignore_index=True)

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

    X_train_raw = train_df[combined_23].values
    y_train = train_df["target_realized_r"].values

    # Fit Scaler
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_raw)

    # Fit Ridge
    ridge = Ridge(alpha=500.0, random_state=42)
    ridge.fit(X_train_scaled, y_train)

    # In-sample predictions & threshold derivation
    train_preds = ridge.predict(X_train_scaled)
    th_p20 = float(np.percentile(train_preds, 20))

    # Output directory
    models_dir = Path(__file__).parent / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    scaler_file = models_dir / "frozen_scaler_v1.joblib"
    model_file = models_dir / "frozen_ridge_v1.joblib"
    manifest_file = models_dir / "model_manifest.json"

    joblib.dump(scaler, scaler_file)
    joblib.dump(ridge, model_file)

    scaler_sha256 = compute_sha256(scaler_file)
    model_sha256 = compute_sha256(model_file)

    manifest = {
        "model_name": "Frozen_Negative_Veto_Ridge_v1",
        "version": "1.0.0",
        "created_at": "2026-10-02T16:20:00Z",
        "status": "CANDIDATE_FOR_SHADOW_PAPER_TRADING",
        "training_metadata": {
            "period_start": "2022-01-01",
            "period_end": "2024-12-31",
            "total_training_trades": len(train_df),
            "assets": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
            "target": "target_realized_r"
        },
        "hyperparameters": {
            "model_type": "sklearn.linear_model.Ridge",
            "alpha": 500.0,
            "random_state": 42,
            "fit_intercept": True
        },
        "features": {
            "feature_count": len(combined_23),
            "snapshot_14": snapshot_14,
            "sequence_9": sequence_9,
            "all_features": combined_23
        },
        "decision_rule": {
            "threshold_type": "in_sample_20th_percentile",
            "threshold_r": th_p20,
            "rule": "veto if predicted_r < threshold_r else pass"
        },
        "artifacts": {
            "scaler_filename": scaler_file.name,
            "scaler_sha256": scaler_sha256,
            "model_filename": model_file.name,
            "model_sha256": model_sha256
        },
        "model_parameters": {
            "intercept": float(ridge.intercept_),
            "coefficients": {feat: float(coef) for feat, coef in zip(combined_23, ridge.coef_)}
        }
    }

    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    print("\n✅ Successfully exported frozen artifacts:")
    print(f"  Scaler:   {scaler_file.name} (SHA256: {scaler_sha256[:16]}...)")
    print(f"  Model:    {model_file.name} (SHA256: {model_sha256[:16]}...)")
    print(f"  Manifest: {manifest_file.name}")
    print(f"  Frozen Threshold (theta): {th_p20:+.6f}R")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    freeze_ai_model()
