# Experiment Record: Feature Information Test v1

## Metadata
- **Experiment ID**: `feature_information_test_v1`
- **Date**: 2026-10-02
- **Objective**: Test whether the frozen 14-feature snapshot contains predictive signal for `target_realized_r`.
- **Target**: `target_realized_r` (Realized R from frozen exit logic)
- **Partitions**: Dev (2022-2023, 128 trades) -> Val (2024, 65 trades)
- **Design**: 3 Fixed Complexity Levels:
  - Model 0: Null Model (Dev Prior Mean = +0.713R)
  - Model 1: Linear Hypothesis (Ridge Regression, $\alpha=200.0$)
  - Model 2: Nonlinear Hypothesis (Single Shallow Tree: `max_depth=2`, `min_samples_leaf=15`, no tuning)
- **Constraint**: OOS 2025-2026 100% locked.

---

## Results Summary

| Metric | Model 0: Null | Model 1: Ridge | Model 2: Shallow Tree |
| :--- | :---: | :---: | :---: |
| **MAE** | 2.5283R | 2.6549R | **2.4688R** (Lowest) |
| **RMSE** | 4.9402R | 4.9460R | **4.7899R** (Lowest) |
| **Pearson Correlation ($r$)** | 0.0000 | +0.0359 ($p=0.777$) | **+0.2974 ($p=0.016$)** |
| **Spearman Rank Corr ($\rho$)**| 0.0000 | -0.2138 ($p=0.087$) | **-0.0460 ($p=0.716$)** |
| **Top 20% Actual Mean R** | +1.148R | +2.694R | **+5.031R** |
| **Bottom 20% Actual Mean R** | +1.148R | +1.186R | **+1.218R** |
| **Spread (Top 20% - Bot 20%)** | 0.000R | +1.508R | **+3.813R** |

---

## Tree Architecture & Leaf Breakdown on Val 2024

```text
|--- btc_natr <= 1.12
|   |--- btc_ret_24h <= 1.61  --> Leaf Node #2: Dev Mean = +6.49R
|   |--- btc_ret_24h >  1.61  --> Leaf Node #3: Dev Mean = +0.41R
|--- btc_natr >  1.12
|   |--- breakout_volume_zscore <= 1.79 --> Leaf Node #5: Dev Mean = -0.73R
|   |--- breakout_volume_zscore >  1.79 --> Leaf Node #6: Dev Mean = +0.26R
```

On Val 2024:
- **Leaf Node #2** (Low BTC volatility + quiet BTC): 4 trades, **75.0% win rate, +6.718R actual mean, +$201.43 PnL**.
- **Leaf Node #3**: 10 trades, 50.0% win rate, **+3.746R actual mean, +$223.77 PnL**.
- **Leaf Node #5**: 28 trades, 46.4% win rate, +0.540R actual mean, +$143.00 PnL.
- **Leaf Node #6** (High BTC vol + high breakout volume): 23 trades, **17.4% win rate, -0.211R actual mean, -$41.72 PnL**.
