# Experiment Record: Feature Information Test v2 (Sequence vs Snapshot)

## Metadata
- **Experiment ID**: `feature_information_test_v2`
- **Date**: 2026-10-02
- **Objective**: Test whether pre-breakout temporal history (Sequence Representation v2) provides incremental predictive information absent from single-bar snapshot.
- **Target**: `target_realized_r`
- **Partitions**: Dev (2022-2023, 128 trades) -> Val (2024, 65 trades)
- **Representations Tested**:
  - Rep 1: Snapshot 14 (Baseline single-bar features)
  - Rep 2: Sequence 9 (Pre-breakout history: compression, runup, resistance touches, volume slope)
  - Rep 3: Combined 23 (Snapshot 14 + Sequence 9)
- **Models Tested**: 3 fixed complexity levels (Null Model -> Ridge Regression -> Single Shallow Tree depth=2)
- **Constraint**: OOS 2025-2026 strictly locked.

---

## Comparative Results Matrix on Val 2024

| Metric / Dimension | Rep 1: Snapshot 14 | Rep 2: Sequence 9 | Rep 3: Combined 23 |
| :--- | :---: | :---: | :---: |
| **Ridge Optimal Alpha (Dev CV)** | 500.0 | 500.0 | 500.0 |
| **Ridge Pearson $r$** | +0.0582 ($p=0.645$) | **+0.2469 ($p=0.047$)** | +0.1829 ($p=0.145$) |
| **Ridge Spearman $\rho$** | -0.2219 ($p=0.076$) | **-0.0532 ($p=0.674$)** | -0.1857 ($p=0.139$) |
| **Ridge Top 20% Mean R** | +2.584R | **+3.641R** | +3.883R |
| **Ridge Bot 20% Mean R** | +1.133R | **+0.333R** | +0.496R |
| **Ridge Mean Spread (Top - Bot)** | +1.451R | **+3.308R** | +3.387R |
| **Ridge Top vs Bot Total PnL** | +$206.2 vs +$162.2 | **+$309.5 vs -$19.9** | +$338.9 vs +$67.9 |
| **Ridge Top 20% w/o Top 1 Outlier**| +0.847R | **+1.670R** | +1.932R |
| **Shallow Tree Pearson $r$** | +0.2974 ($p=0.016$) | +0.1325 ($p=0.293$) | **+0.4050 ($p=0.001$)** |
| **Shallow Tree Spearman $\rho$** | -0.0460 ($p=0.716$) | -0.0014 ($p=0.991$) | -0.0432 ($p=0.732$) |
| **Shallow Tree Top 20% Mean R** | +5.031R | +1.523R | **+4.069R** |
| **Shallow Tree Bot 20% Mean R** | +1.218R | -0.411R | +1.218R |
| **Shallow Tree Spread (Top - Bot)**| +3.813R | +1.933R | **+2.851R** |
| **Shallow Tree Top vs Bot PnL** | +$433.9 vs +$156.0 | +$125.2 vs -$59.2 | **+$366.7 vs +$156.0** |
| **Shallow Tree Top w/o Top 1 Outlier**| +3.176R | -0.303R | **+2.134R** |

---

## Tree Architecture Evolution on Dev

### Sequence 9 Tree:
```text
|--- pre_breakout_runup_5b <= 0.37%  --> Value: +3.30R (Fresh base breakout)
|--- pre_breakout_runup_5b >  0.37%
|   |--- compression_duration_bars <= 12.5 --> Value: -0.32R (Exhausted / short base)
|   |--- compression_duration_bars >  12.5 --> Value: +1.61R (Extended consolidation)
```

### Combined 23 Tree:
```text
|--- btc_natr <= 1.12
|   |--- compression_duration_bars <= 6.00 --> Value: +0.39R
|   |--- compression_duration_bars >  6.00 --> Value: +6.92R (Macro quiet + Long compression)
|--- btc_natr >  1.12
|   |--- breakout_volume_zscore <= 1.79    --> Value: -0.73R
|   |--- breakout_volume_zscore >  1.79    --> Value: +0.26R
```
