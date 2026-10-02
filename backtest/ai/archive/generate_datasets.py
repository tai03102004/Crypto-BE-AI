import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import json
import hashlib
import pandas as pd
from typing import Dict, Any

from backtest.data.loader import DataLoader
from backtest.ai.dataset_builder import DatasetBuilder


def compute_file_sha256(filepath: Path) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()


def generate_and_save_dataset(
    partition: str,
    start_date: str,
    end_date: str,
    output_csv: Path,
    output_meta: Path
):
    print(f"\n=======================================================")
    print(f"  Generating Reconciled Dataset: {partition.upper()} ({start_date} -> {end_date})")
    print(f"=======================================================")

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    builder = DatasetBuilder(entry_period=55, exit_period=20, atr_multiplier=2.0)

    # 1. Load BTC data for macro context
    btc_df = DataLoader("BTCUSDT", "4h").load(start_date=start_date, end_date=end_date)

    dfs = []
    for symbol in symbols:
        df = DataLoader(symbol, "4h").load(start_date=start_date, end_date=end_date)
        asset_btc = btc_df if symbol != "BTCUSDT" else None
        ds = builder.build_reconciled_dataset(symbol=symbol, df=df, btc_df=asset_btc)
        print(f"  {symbol}: {len(ds)} reconciled trades extracted.")
        dfs.append(ds)

    final_df = pd.concat(dfs, ignore_index=True)
    # Sort chronologically by signal_time, then asset
    final_df = final_df.sort_values(by=["signal_time", "asset"]).reset_index(drop=True)

    # Save CSV
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(output_csv, index=False)
    file_hash = compute_file_sha256(output_csv)

    # Compute key stats
    win_rate = float((final_df["net_pnl"] > 0).mean() * 100.0)
    mean_r = float(final_df["target_realized_r"].mean())
    median_r = float(final_df["target_realized_r"].median())
    total_pnl = float(final_df["net_pnl"].sum())

    metadata: Dict[str, Any] = {
        "dataset_version": "1.0.0",
        "partition": partition,
        "filename": output_csv.name,
        "sha256": file_hash,
        "start_time": start_date,
        "end_time": end_date,
        "assets": symbols,
        "strategy_version": "DonchianBreakoutStrategy_55_20 (Turtle System 2, entry 55, exit 20, initial SL 2.0*ATR)",
        "execution_version": "Deterministic Backtester (Next-bar open entry, 0.05% fee, 0.03% slippage, 1% fixed fractional risk, 30% max exposure cap, 3% daily circuit breaker)",
        "feature_schema_version": "2.0.0 (14 snapshot features + 9 pre-breakout sequence/regime features: compression_duration_bars, natr_percentile_55, range_contraction_ratio, channel_tightness_to_atr, resistance_touch_count, pre_breakout_runup_5b, volume_trend_slope_10b, volume_percentile_55, macro_btc_natr_percentile_55 + 3 provenance timestamps)",
        "reconciliation_status": "100% exact trade-by-trade match with Frozen Backtest Engine trade logs",
        "trade_population_definition": "Sequential trades executed by frozen strategy upon breakout signals from flat cash state.",
        "row_count": len(final_df),
        "statistics": {
            "win_rate_pct": round(win_rate, 2),
            "mean_realized_r": round(mean_r, 4),
            "median_realized_r": round(median_r, 4),
            "total_net_pnl_usd": round(total_pnl, 2)
        }
    }

    with open(output_meta, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"  💾 Saved CSV: {output_csv} ({len(final_df)} rows, SHA256: {file_hash[:16]}...)")
    print(f"  📄 Saved Metadata: {output_meta}")
    print(f"  📊 Summary: Win Rate={win_rate:.1f}%, Mean R={mean_r:+.3f}R, Total PnL=${total_pnl:+.2f}")


def main():
    data_dir = Path(__file__).parent / "data"

    # 1. Dev 2022-2023
    generate_and_save_dataset(
        partition="dev",
        start_date="2022-01-01",
        end_date="2023-12-31",
        output_csv=data_dir / "breakouts_dev_2022_2023.csv",
        output_meta=data_dir / "breakouts_dev_2022_2023.meta.json"
    )

    # 2. Val 2024
    generate_and_save_dataset(
        partition="val",
        start_date="2024-01-01",
        end_date="2024-12-31",
        output_csv=data_dir / "breakouts_val_2024.csv",
        output_meta=data_dir / "breakouts_val_2024.meta.json"
    )

    # 3. OOS 2025-2026 (Final Holdout Evaluation)
    generate_and_save_dataset(
        partition="oos",
        start_date="2025-01-01",
        end_date="2026-10-02",
        output_csv=data_dir / "breakouts_oos_2025_2026.csv",
        output_meta=data_dir / "breakouts_oos_2025_2026.meta.json"
    )


if __name__ == "__main__":
    main()
