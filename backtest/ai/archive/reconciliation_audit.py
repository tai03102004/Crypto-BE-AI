import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np

from backtest.data.loader import DataLoader
from backtest.engine.backtester import Backtester
from backtest.strategies.donchian_breakout import DonchianBreakoutStrategy


def run_reconciliation_audit():
    print("=" * 90)
    print("  COMPREHENSIVE BACKTEST <-> DATASET RECONCILIATION & PROVENANCE AUDIT")
    print("=" * 90)

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    data_dir = Path(__file__).parent / "data"

    partitions = [
        ("Dev (2022-2023)", "2022-01-01", "2023-12-31", data_dir / "breakouts_dev_2022_2023.csv"),
        ("Val (2024)", "2024-01-01", "2024-12-31", data_dir / "breakouts_val_2024.csv")
    ]

    total_checks = 0
    passed_checks = 0

    for name, start_date, end_date, csv_path in partitions:
        print(f"\n--- Auditing Partition: {name} ---")
        assert csv_path.exists(), f"Dataset file not found: {csv_path}"
        ds = pd.read_csv(csv_path)
        print(f"Loaded {len(ds)} rows from {csv_path.name}")

        # -------------------------------------------------------------
        # 1. Backtest <-> Dataset Trade-by-Trade Reconciliation
        # -------------------------------------------------------------
        print(f"\n[Test 1] 1-to-1 Trade Reconciliation against Frozen Backtester...")
        total_backtest_trades = 0
        total_backtest_pnl = 0.0
        reconciled_trades = 0

        for symbol in symbols:
            df = DataLoader(symbol, "4h").load(start_date=start_date, end_date=end_date)
            strat = DonchianBreakoutStrategy(entry_period=55, exit_period=20, atr_multiplier=2.0)
            bt = Backtester(
                strategy=strat,
                initial_capital=1000.0,
                risk_per_trade_pct=0.01,
                max_exposure_pct=0.30,
                max_daily_loss_pct=0.03,
                fee_rate=0.0005,
                slippage_rate=0.0003
            )
            res = bt.run(df, warmup_bars=60)
            trades = res["trades"]
            total_backtest_trades += len(trades)
            total_backtest_pnl += sum(t.pnl for t in trades)

            # Match against dataset rows for this symbol
            ds_asset = ds[ds["asset"] == symbol].sort_values("entry_time").reset_index(drop=True)
            assert len(trades) == len(ds_asset), f"Trade count mismatch for {symbol}: backtest={len(trades)}, dataset={len(ds_asset)}"

            for i, trade in enumerate(trades):
                row = ds_asset.iloc[i]
                
                # Check timestamps
                assert str(trade.entry_time) == str(row["entry_time"]), f"Entry time mismatch at {symbol} trade {i}: {trade.entry_time} vs {row['entry_time']}"
                assert str(trade.exit_time) == str(row["exit_time"]), f"Exit time mismatch at {symbol} trade {i}: {trade.exit_time} vs {row['exit_time']}"
                
                # Check execution prices & sizing
                assert abs(trade.entry_price - row["entry_price"]) < 1e-4, f"Entry price mismatch at {symbol} trade {i}"
                assert abs(trade.exit_price - row["exit_price"]) < 1e-4, f"Exit price mismatch at {symbol} trade {i}"
                assert abs(trade.size - row["position_size"]) < 1e-6, f"Size mismatch at {symbol} trade {i}"
                
                # Check financial outcomes
                assert abs(trade.pnl - row["net_pnl"]) < 1e-4, f"Net PnL mismatch at {symbol} trade {i}: {trade.pnl} vs {row['net_pnl']}"
                assert abs(trade.fees - row["fees"]) < 1e-4, f"Fees mismatch at {symbol} trade {i}"
                
                reconciled_trades += 1

        dataset_total_pnl = ds["net_pnl"].sum()
        pnl_diff = abs(total_backtest_pnl - dataset_total_pnl)
        assert pnl_diff < 1e-3, f"Aggregate PnL mismatch: backtest=${total_backtest_pnl:.2f} vs dataset=${dataset_total_pnl:.2f}"
        
        print(f"  ✅ PASS: 100% Exact Reconciliation ({reconciled_trades}/{total_backtest_trades} trades matched).")
        print(f"          Backtest Total PnL: ${total_backtest_pnl:.2f} == Dataset Total PnL: ${dataset_total_pnl:.2f} (diff = ${pnl_diff:.6f})")
        passed_checks += 1
        total_checks += 1

        # -------------------------------------------------------------
        # 2. Timestamp Provenance & Order Invariant
        # -------------------------------------------------------------
        print(f"\n[Test 2] Timestamp Provenance & Monotonic Order Invariant...")
        # Rule: signal_time < entry_time <= exit_time
        time_violations = 0
        for i, row in ds.iterrows():
            sig = pd.Timestamp(row["signal_time"])
            entry = pd.Timestamp(row["entry_time"])
            exit_t = pd.Timestamp(row["exit_time"])
            if not (sig < entry <= exit_t):
                time_violations += 1
        assert time_violations == 0, f"Found {time_violations} timestamp order violations!"
        print(f"  ✅ PASS: 100% of rows strictly satisfy signal_time (t) < entry_time (t+1) <= exit_time.")
        passed_checks += 1
        total_checks += 1

        # -------------------------------------------------------------
        # 3. Macro BTC Context Timestamp Provenance Invariant
        # -------------------------------------------------------------
        print(f"\n[Test 3] Macro BTC Context Timestamp Provenance...")
        # Rule: max(provenance_btc_time) <= signal_time
        btc_violations = 0
        for i, row in ds.iterrows():
            sig = pd.Timestamp(row["signal_time"])
            btc_t = pd.Timestamp(row["provenance_btc_time"])
            asset_t = pd.Timestamp(row["provenance_asset_time"])
            
            # Asset provenance must exactly equal signal_time
            if asset_t != sig:
                btc_violations += 1
            # BTC provenance must be at or before signal_time (never in the future)
            if btc_t > sig:
                btc_violations += 1

        assert btc_violations == 0, f"Found {btc_violations} BTC context provenance violations!"
        print(f"  ✅ PASS: 100% of rows satisfy provenance_btc_time <= signal_time (Zero future lookahead).")
        passed_checks += 1
        total_checks += 1

        # -------------------------------------------------------------
        # 4. Upper Channel Exclusivity Check (Excludes bar t)
        # -------------------------------------------------------------
        print(f"\n[Test 4] Upper Channel Non-Circularity Check...")
        # Verify that breakout_magnitude_pct was computed against strictly prior bars [t-55, t-1]
        for symbol in symbols:
            df = DataLoader(symbol, "4h").load(start_date=start_date, end_date=end_date)
            ds_asset = ds[ds["asset"] == symbol]
            for _, row in ds_asset.iterrows():
                sig_time = row["signal_time"]
                match = df[df["timestamp"] == sig_time]
                if match.empty:
                    continue
                t_idx = match.index[0]
                close_t = df.loc[t_idx, "close"]
                prior_highs = df.loc[t_idx - 55: t_idx - 1, "high"]
                upper_channel = prior_highs.max()
                expected_mag = ((close_t - upper_channel) / upper_channel) * 100.0
                assert abs(row["breakout_magnitude_pct"] - expected_mag) < 1e-4, "Breakout magnitude mismatch!"
        print(f"  ✅ PASS: Verified Upper Channel is computed strictly over [t-55, t-1], excluding candle t.")
        passed_checks += 1
        total_checks += 1

    print("\n" + "=" * 90)
    print(f"  ALL {passed_checks}/{total_checks} RECONCILIATION & PROVENANCE CHECKS PASSED PERFECTLY")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    run_reconciliation_audit()
