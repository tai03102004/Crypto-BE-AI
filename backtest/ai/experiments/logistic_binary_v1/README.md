# Experiment Record: Logistic Binary v1 (Negative Control)

## Metadata
- **Experiment ID**: `logistic_binary_v1`
- **Date**: 2026-10-02
- **Model**: `LogisticRegression(penalty='l2', C=1.0)`
- **Scaler**: `StandardScaler` (Fit strictly on Dev 2022-2023)
- **Features**: 14 frozen numeric features
- **Target**: `target_realized_r > 0` (Binary Win/Loss)
- **Status**: **REJECTED (Negative Control Baseline)**

---

## Formal Rejection Rationale
> **"Binary Logistic Regression v1 is rejected as an entry filter, not because binary classification is universally unsuitable, but because the `R > 0` objective failed to rank 2024 opportunities robustly and materially damaged the strategy's positive tail."**

Specific grounds for rejection:
1. **Predictive Instability (Gate A Fail)**:
   - Dev ROC-AUC: `0.7503` -> Val ROC-AUC: `0.3900` (inverted probability ranking).
   - Val PR-AUC: `0.3358` (inferior to natural Val base rate `0.3846`).
   - Brier Skill Score: `-0.2781` (inferior to naive historical climatology prior).
   - Probability Quintile Q1 (lowest predicted win prob, 5-12%) had the highest actual win rate (61.5%) and generated +$110.22 PnL.
2. **Tail Destruction (Gate C Fail)**:
   - At basic base rate cutoff ($p \ge 0.297$), filter rejected 3 of the top 7 tail winners (`BNBUSDT_001` +11.44R, `SOLUSDT_010` +6.15R, `ETHUSDT_006` +6.08R), throwing away **+23.08R** of realized profit.
   - At high conviction cutoff ($p \ge 0.500$), filter rejected 6 of the top 7 tail winners, throwing away **+54.20R**.
3. **Economic Degradation (Gate B Fail)**:
   - Baseline Control: Net PnL = **+$526.48** (65 trades, Expectancy = +1.148R).
   - Treatment ($p \ge 0.297$): Net PnL = **+$363.57** (26 trades, lost $162.91 in dollar profit).
   - Treatment ($p \ge 0.500$): Net PnL = **+$107.06** (12 trades, lost $419.42 in dollar profit).

---

## Role in Research Pipeline
This experiment is permanently preserved as a **calibrated negative control**. Any future model (Expected-R regression, tail classification, or tree models) must demonstrably outperform this baseline on economic ranking, Brier skill, and tail retention before being considered for production consideration.
