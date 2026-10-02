# Experiment Record: Expected-R Ridge Regression (v2)

## Metadata
- **Experiment ID**: `expected_r_ridge_v2`
- **Date**: 2026-10-02
- **Objective**: Direct estimation of $E[\text{Realized } R \mid X]$ to evaluate economic ranking of breakout opportunities.
- **Model**: `Ridge(alpha=200.0)` (Alpha chosen strictly via 5-fold CV on Dev 2022-2023)
- **Scaler**: `StandardScaler` (Fit strictly on Dev 2022-2023)
- **Features**: 14 frozen numeric features
- **Target**: `target_realized_r` (Continuous, unbounded realized R from frozen exit logic)
- **Status**: **RESEARCH DIAGNOSTIC COMPLETED**

---

## Key Findings across Gates

### 1. Gate A — Predictive
- Dev MAE: `2.2766R`, Val MAE: `2.6549R`
- Dev RMSE: `4.5504R`, Val RMSE: `4.9460R`
- Pearson Correlation on Val: `+0.0359` ($p = 0.777$, linear alignment near zero).
- Spearman Rank Correlation on Val: `-0.2138` ($p = 0.087$, ranking alignment flat/slightly negative).
- Top Decile Mean Actual R: `+3.895R` vs Bottom Decile Mean Actual R: `+1.001R` (Decile Spread = `+2.894R`).

### 2. Gate B — Economic Ranking
- Quintile Breakdown on Val:
  - Q1 (Lowest E[R], mean -0.087R): 13 trades, Mean Actual R = `+1.186R`, PnL = `+$169.30`
  - Q2 (mean +0.613R): 13 trades, Mean Actual R = `-0.319R`, PnL = `-$43.78`
  - Q3 (mean +0.879R): 13 trades, Mean Actual R = `+2.632R`, PnL = `+$250.15`
  - Q4 (mean +1.098R): 13 trades, Mean Actual R = `-0.456R`, PnL = `-$70.92`
  - Q5 (Highest E[R], mean +1.353R): 13 trades, Mean Actual R = `+2.694R`, PnL = `+$221.72`
- Non-monotonicity: Linear regression on 14 features suffers from high variance and cannot produce a strictly monotonic bucket ordering out-of-sample.
- Control vs Treatment:
  - Control (No filter): 65 trades, Net PnL = `+$526.48`, Mean R = `+1.148R`, PF = `2.33`
  - Cutoff $\hat{R} \ge 0.0$: 61 trades, Net PnL = `+$442.67`, Mean R = `+1.091R`, PF = `2.15`
  - Cutoff $\hat{R} \ge \text{Dev Mean}$ (+0.713R): 41 trades, Net PnL = `+$379.70`, Mean R = `+1.494R`, PF = `2.33`

### 3. Gate C — Tail Protection (Critical Finding)
- **Major Improvement over Logistic Binary**:
  - Expected-R model preserved **6 out of the top 7 tail winners (85.7%)** at $\hat{R} \ge 0.0$.
  - Top 1 (`BTC_001`, +27.29R), Top 2 (`ETH_002`, +23.42R), Top 3 (`BNB_001`, +11.44R), Top 4 (`BTC_014`, +6.58R), Top 5 (`SOL_010`, +6.15R), Top 6 (`ETH_006`, +6.08R) were ALL retained!
  - In particular, `BNB_001` (+11.44R) and `SOL_010` (+6.15R)—which were destroyed by binary logistic classification—were preserved because the regression model gave them positive expected payoffs ($\hat{R} = +1.21R$ and $+0.90R$).
- Retained R: `+66.53R`, Rejected R: only `+8.07R` (lost only trade #7 `SOL_016` +4.81R).
