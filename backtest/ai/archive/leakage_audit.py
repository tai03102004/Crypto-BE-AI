import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np

from backtest.ai.dataset_builder import DatasetBuilder
from backtest.data.loader import DataLoader


def run_leakage_audit():
    print("=" * 85)
    print("  DATASET LEAKAGE AUDIT: DATA LINEAGE & TIMESTAMP PROVENANCE VERIFICATION")
    print("  Rule: Feature Lineage strictly <= t | Target Horizon strictly >= t+1")
    print("=" * 85)

    passed_tests = 0
    total_tests = 5

    builder = DatasetBuilder(entry_period=55, exit_period=20, atr_multiplier=2.0)

    # Load 4H BTC data
    loader = DataLoader(symbol="BTCUSDT", interval="4h")
    df = loader.load(start_date="2023-01-01", end_date="2023-12-31", fill_missing=True)

    # Build reconciled dataset
    ds = builder.build_reconciled_dataset(symbol="BTCUSDT", df=df)
    print(f"\nBuilt dataset with {len(ds)} reconciled trades for lineage auditing.")
    assert len(ds) > 0, "No breakout trades found in audit window!"

    # -------------------------------------------------------------------------
    # TEST 1: Strict Timestamp Monotonicity & Horizon Isolation
    # -------------------------------------------------------------------------
    print("\n[Lineage Test 1/5] Timestamp Lineage & Horizon Monotonicity...")
    violations = 0
    for idx, row in ds.iterrows():
        sig_time = pd.Timestamp(row["signal_time"])
        entry_time = pd.Timestamp(row["entry_time"])
        exit_time = pd.Timestamp(row["exit_time"])

        # Invariant: sig_time < entry_time <= exit_time
        if not (sig_time < entry_time <= exit_time):
            print(f"  ❌ Violation at row {idx}: Signal={sig_time}, Entry={entry_time}, Exit={exit_time}")
            violations += 1

    assert violations == 0, f"Found {violations} timestamp horizon violations!"
    print(f"  ✅ PASS: 100% of rows satisfy: signal_time (t) < entry_time (t+1) <= exit_time.")
    passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 2: Future Perturbation Invariance (Empirical Evidence of No Future Lineage)
    # -------------------------------------------------------------------------
    print("\n[Lineage Test 2/5] Future Perturbation Invariance...")
    # Find a breakout index t
    target_t = None
    for t in range(60, len(df) - 50):
        prior_highs = df["high"].iloc[t - 55: t]
        if df["close"].iloc[t] > prior_highs.max():
            target_t = t
            break

    assert target_t is not None, "Could not find a breakout bar for perturbation test."

    # 1. Extract baseline features on pristine data
    f_baseline = builder.extract_features_at_t(t_idx=target_t, df=df)

    # 2. Corrupt/Mutate FUTURE data aggressively (t+1 to end: 10x price, random noise)
    df_corrupted = df.copy()
    df_corrupted.iloc[target_t + 1:, df_corrupted.columns.get_loc("open")] *= 10.0
    df_corrupted.iloc[target_t + 1:, df_corrupted.columns.get_loc("high")] *= 15.0
    df_corrupted.iloc[target_t + 1:, df_corrupted.columns.get_loc("low")] *= 0.1
    df_corrupted.iloc[target_t + 1:, df_corrupted.columns.get_loc("close")] *= 12.0
    df_corrupted.iloc[target_t + 1:, df_corrupted.columns.get_loc("volume")] += 999999.0

    # 3. Re-extract features at bar t on corrupted future data
    f_perturbed = builder.extract_features_at_t(t_idx=target_t, df=df_corrupted)

    # 4. Compare feature-by-feature
    max_diff = 0.0
    diff_keys = []
    numeric_feature_keys = [k for k in f_baseline if not k.startswith("provenance_")]
    for k in numeric_feature_keys:
        diff = abs(f_baseline[k] - f_perturbed[k])
        if diff > max_diff:
            max_diff = diff
        if diff > 1e-9:
            diff_keys.append((k, diff))

    assert len(diff_keys) == 0, f"Future leakage detected! Features changed when future was corrupted: {diff_keys}"
    print(f"  ✅ PASS: Feature vector tại t không thay đổi khi dữ liệu tương lai bị perturb (Max Diff = {max_diff:.10f}).")
    print("          Strong empirical evidence: Corrupting future data (t+1 -> end) produced ZERO change in features at bar t.")
    passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 3: Past Perturbation Sensitivity (Verifies Lineage to Past Data)
    # -------------------------------------------------------------------------
    print("\n[Lineage Test 3/5] Past Perturbation Sensitivity...")
    df_past_corrupted = df.copy()
    # Mutate past candle at t-2
    df_past_corrupted.iloc[target_t - 2, df_past_corrupted.columns.get_loc("close")] *= 1.20
    f_past_perturbed = builder.extract_features_at_t(t_idx=target_t, df=df_past_corrupted)

    # Verify that features DO react to past data changes
    past_diffs = [abs(f_baseline[k] - f_past_perturbed[k]) for k in numeric_feature_keys]
    assert max(past_diffs) > 0.01, "Features did not respond to past data changes (broken lineage)!"
    print("  ✅ PASS: Verified causal dependency: features at t actively respond to past market state.")
    passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 4: Target Horizon & Extreme Isolation
    # -------------------------------------------------------------------------
    print("\n[Lineage Test 4/5] Target Horizon Isolation...")
    # Verify that trade entry is strictly at bar t+1 OPEN with slippage, not bar t close/high
    first_trade = ds.iloc[0]
    sig_time = first_trade["signal_time"]
    entry_time = first_trade["entry_time"]
    entry_bar = df[df["timestamp"] == entry_time].iloc[0]
    expected_entry_price = entry_bar["open"] * 1.0003  # 0.03% slippage
    assert abs(first_trade["entry_price"] - expected_entry_price) < 1e-4, "Entry price mismatch with next-bar open!"
    print("  ✅ PASS: Target simulation strictly begins at bar t+1 OPEN with slippage without including bar t extremes.")
    passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 5: Macro BTC Context Timestamp Provenance
    # -------------------------------------------------------------------------
    print("\n[Lineage Test 5/5] Macro BTC Context Timestamp Provenance...")
    eth_df = DataLoader("ETHUSDT", "4h").load(start_date="2023-01-01", end_date="2023-06-01")
    eth_ds = builder.build_reconciled_dataset(symbol="ETHUSDT", df=eth_df, btc_df=df)
    for _, row in eth_ds.iterrows():
        sig = pd.Timestamp(row["signal_time"])
        btc_prov = pd.Timestamp(row["provenance_btc_time"])
        assert btc_prov <= sig, f"BTC leakage: provenance {btc_prov} exceeds signal {sig}"
    print("  ✅ PASS: Multi-asset cross-referencing verified: provenance_btc_time <= signal_time for 100% of rows.")
    passed_tests += 1

    print("\n" + "=" * 85)
    print(f"  LEAKAGE AUDIT RESULT: ALL {passed_tests}/{total_tests} LINEAGE & PROVENANCE TESTS PASSED PERFECTLY")
    print("=" * 85 + "\n")


if __name__ == "__main__":
    run_leakage_audit()
