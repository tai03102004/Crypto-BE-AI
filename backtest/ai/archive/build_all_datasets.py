import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np

from backtest.data.loader import DataLoader
from backtest.ai.dataset_builder import DatasetBuilder

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def build_and_save_partitions(
    assets: list = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
):
    print("=" * 80)
    print("  BUILDING ML DATASETS FOR BREAKOUT QUALITY EVALUATION")
    print("  Partition 1: Development (In-Sample: 2022-01-01 -> 2024-01-01)")
    print("  Partition 2: Validation (2024-01-01 -> 2025-01-01)")
    print("  Out-of-Sample (2025-2026): [STRICTLY EXCLUDED / UNTOUCHED]")
    print("=" * 80)

    builder = DatasetBuilder(entry_period=55, exit_period=20, atr_multiplier=2.0)

    partitions = {
        "dev": ("2022-01-01", "2024-01-01"),
        "val": ("2024-01-01", "2025-01-01")
    }

    for p_name, (start_dt, end_dt) in partitions.items():
        print(f"\n⏳ Processing Partition: {p_name.upper()} [{start_dt} -> {end_dt}]...")

        # 1. Load BTC 4h for macro context
        btc_loader = DataLoader(symbol="BTCUSDT", interval="4h")
        btc_df = btc_loader.load(start_date=start_dt, end_date=end_dt, fill_missing=True)

        partition_dfs = []

        for symbol in assets:
            print(f"  Extracting setups for {symbol} (4h)...")
            loader = DataLoader(symbol=symbol, interval="4h")
            asset_df = loader.load(start_date=start_dt, end_date=end_dt, fill_missing=True)

            asset_ds = builder.build_dataset_for_asset(
                symbol=symbol,
                df=asset_df,
                btc_df=btc_df if symbol != "BTCUSDT" else None,
                warmup_bars=60
            )
            print(f"    -> Found {len(asset_ds)} breakout events for {symbol}.")
            partition_dfs.append(asset_ds)

        full_partition_df = pd.concat(partition_dfs, ignore_index=True)
        # Sort strictly chronologically by signal_time
        full_partition_df.sort_values(by="signal_time", inplace=True)
        full_partition_df.reset_index(drop=True, inplace=True)

        # Save to CSV
        out_file = DATA_DIR / f"breakouts_{p_name}_{start_dt[:4]}_{end_dt[:4]}.csv"
        full_partition_df.to_csv(out_file, index=False)
        print(f"  💾 Saved {len(full_partition_df)} total breakout setups to: {out_file.name}")

        # Summary statistics
        realized_r = full_partition_df["target_realized_r"]
        mfe_r = full_partition_df["target_mfe_r"]
        win_count = (realized_r > 0).sum()
        total_count = len(full_partition_df)
        hit_1r = (full_partition_df["target_hit_1r"] == 1).sum()
        hit_2r = (full_partition_df["target_hit_2r"] == 1).sum()
        hit_3r = (full_partition_df["target_hit_3r"] == 1).sum()

        print("  📊 Partition Statistics:")
        print(f"     Total Events       : {total_count}")
        print(f"     Realized Win Rate  : {(win_count / total_count * 100):.1f}% ({win_count} wins / {total_count - win_count} losses)")
        print(f"     Mean Realized R    : {realized_r.mean():+.3f}R (Median: {realized_r.median():+.3f}R)")
        print(f"     MFE >= 1R Reach Rate: {(hit_1r / total_count * 100):.1f}%")
        print(f"     MFE >= 2R Reach Rate: {(hit_2r / total_count * 100):.1f}%")
        print(f"     MFE >= 3R Reach Rate: {(hit_3r / total_count * 100):.1f}%")


if __name__ == "__main__":
    build_and_save_partitions()
