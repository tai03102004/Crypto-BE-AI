# Experiment Record: Tail-Potential Classifier (v3)

## Metadata
- **Experiment ID**: `tail_mfe_logistic_v3`
- **Date**: 2026-10-02
- **Objective**: Test whether features at breakout identify setups capable of developing into large excursions ($MFE \ge 2.0R$).
- **Model**: `LogisticRegression(penalty='l2', C=1.0)`
- **Scaler**: `StandardScaler` (Fit strictly on Dev 2022-2023)
- **Features**: 14 frozen numeric features
- **Target**: `target_mfe_r >= 2.0R` (Binary Excursion Potential)
- **Status**: **RESEARCH DIAGNOSTIC COMPLETED**

---

## Key Findings across Gates

### 1. Gate A — Predictive
- Dev Base Rate: `35.94%`, Val Base Rate: `44.62%`
- Dev ROC-AUC: `0.7423` -> Val ROC-AUC: `0.3851`
- Val PR-AUC: `0.3799` (below Val prior rate `0.4462`)
- Brier Skill Score on Val: `-0.2515` (inferior to climatology prior).

### 2. Gate C — Tail Discovery
- Linear log-odds still struggled to reliably separate 2024 runners from false breakouts:
  - Top 1 winner (`BTC_001`, MFE 33.26R): $\hat{p} = 0.4549$
  - Top 2 winner (`ETH_002`, MFE 28.80R): $\hat{p} = 0.5504$
  - Top 5 winner (`SOL_010`, MFE 9.48R): $\hat{p} = 0.0936$ (still severely underestimated by a linear model).
