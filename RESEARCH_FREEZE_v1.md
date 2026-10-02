# RESEARCH_FREEZE_v1: Baseline Configuration Lock

**Timestamp:** 2026-10-02T14:55:00+07:00  
**Status:** FROZEN — NO FURTHER PARAMETER TUNING ALLOWED  
**Purpose:** Pre-OOS Freeze before evaluating Out-of-Sample (2025-01-01 to Present).

---

## 1. Strategy Specification: Donchian 55 (System 2)

- **Strategy Class:** `DonchianBreakoutStrategy`
- **File:** `backtest/strategies/donchian_breakout.py`
- **Code SHA256 Fingerprint:** `ed741dec7659be21fa756d11f7ae5b4bb797f1f92e3a89e925b6a7156b9e7100`

### Parameters
| Parameter | Value | Description |
| :--- | :--- | :--- |
| `timeframe` | `4h` | 4-Hour Kline Bar Interval |
| `entry_period` | `55` | Bars lookback for upper channel breakout: `max(high[t-55:t-1])` |
| `exit_period` | `20` | Bars lookback for lower channel breakdown: `min(low[t-20:t-1])` |
| `atr_period` | `14` | Normalized True Range period |
| `atr_multiplier`| `2.0` | Initial Stop Loss distance = `Entry Price - (2.0 * ATR)` |

### Execution Rules
- **Entry Trigger:** Close of bar $t$ > 55-bar Upper Channel.
- **Execution Timing:** Filled strictly at Open of bar $t+1$ (No lookahead leakage).
- **In-Bar Exit 1:** In-bar Low hits Stop Loss (realistic gap modeling: if Open < SL, fills at Open or worse).
- **In-Bar Exit 2:** Bar $t$ Close < 20-bar Lower Channel.
- **Tie-Breaker:** Stop Loss takes conservative priority if both SL and TP could trigger in the same bar.

---

## 2. Risk & Accounting Parameters

- **Portfolio Engine:** `backtest/engine/portfolio.py` (SHA256: `af8a05c6b6fe36c6...1162c215`)
- **Execution Engine:** `backtest/engine/execution.py` (SHA256: `85ed5824b718cae7...80dd700d`)
- **Costs Model:** `backtest/engine/costs.py` (SHA256: `6c9d37004c45a4d2...c2700d62`)

| Parameter | Value | Invariant Rule |
| :--- | :--- | :--- |
| `initial_capital` | `$1,000.00` | Standardized initial cash |
| `risk_per_trade_pct` | `0.01` (1.0%) | Fixed fractional dollar risk: `Capital * 0.01` |
| `position_sizing` | Derived | `Size = Dollar Risk / (Entry - SL)`, strictly inversely proportional to distance |
| `max_exposure_pct` | `0.30` (30.0%) | Max notional position cap: `<= 30%` of portfolio equity |
| `max_daily_loss_pct`| `0.03` (3.0%) | Daily circuit breaker: Halts new trades if day equity drops `>= 3%` |
| `fee_rate` | `0.0005` (0.05%) | Charged on full notional value on entry AND exit |
| `slippage_rate` | `0.0003` (0.03%) | Two-way slippage applied at entry (adverse) and exit (adverse) |

---

## 3. Dataset Registry & Partitioning

- **Data Source:** Binance Public REST API (Audited for gap downtime with volume=0 forward-fill)
- **Target Assets:** `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`
- **Partitions:**
  - **Development (In-Sample):** `2022-01-01` -> `2024-01-01`
  - **Validation:** `2024-01-01` -> `2025-01-01`
  - **Out-Of-Sample (Holdout):** `2025-01-01` -> `2026-10-02` (TODAY)

---

## 4. OOS Acceptance Criteria (5-Question Gate)

Before accepting results or proceeding to AI Filter A/B, the OOS evaluation must answer:
1. Is **Profit Factor > 1.0**?
2. Is **Expectancy per Trade > $0.00**?
3. Is **Max Drawdown (MDD)** within the historical bound (`< 12%`)?
4. Is performance consistent across assets (not just 1 coin carrying all)?
5. Is the return distributed across multiple trades or dependent entirely on 1-2 windfall outliers?
