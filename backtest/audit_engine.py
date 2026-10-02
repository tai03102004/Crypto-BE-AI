"""
Quantitative Backtest Engine Audit & Stress-Test Suite.
Audits the engine against:
1. Lookahead Bias (Strict t -> t+1 execution)
2. Gap Down Risk (Execution at Open on gap past SL, not magical SL price)
3. Double-touch Collision (Conservative SL priority over TP)
4. Notional Fee Accounting (Fee on volume, not PnL)
5. Daily Circuit Breaker (Halt on max daily loss)
6. Data Continuity & Missing Candles Audit
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backtest.engine.portfolio import Portfolio
from backtest.engine.costs import TradingCosts
from backtest.engine.execution import ExecutionEngine
from backtest.engine.backtester import Backtester
from backtest.strategies.base import BaseStrategy, Signal


def run_audit():
    print("=" * 60)
    print("  QUANT BACKTEST ENGINE: STRESS-TEST & INTEGRITY AUDIT")
    print("=" * 60)
    passed_tests = 0
    total_tests = 6

    # ---------------------------------------------------------
    # TEST 1: Lookahead Bias Verification
    # ---------------------------------------------------------
    print("\n[Audit 1/6] Lookahead Bias Check...")
    class SpyStrategy(BaseStrategy):
        def on_bar(self, current_bar, history_df):
            # Try to cheat: does history_df contain future rows?
            if len(history_df) > 0 and history_df.iloc[-1]["timestamp"] != current_bar["timestamp"]:
                raise AssertionError("LOOKAHEAD DETECTED: history contains future timestamps!")
            if current_bar["close"] == 100:
                return Signal(action="BUY", stop_loss=90, take_profit=120)
            return Signal(action="HOLD")

    dates = pd.date_range("2023-01-01", periods=10, freq="1h")
    # bar 0 to 4: price 90, bar 5: price 100, bar 6: open 105, close 110
    prices = [90, 90, 90, 90, 90, 100, 105, 110, 110, 110]
    df_lookahead = pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p + 2 for p in prices],
        "low": [p - 2 for p in prices],
        "close": prices,
        "volume": [1000] * 10
    })

    bt = Backtester(strategy=SpyStrategy(), initial_capital=1000, risk_per_trade_pct=0.01)
    res = bt.run(df_lookahead, warmup_bars=2)
    # The signal at bar 5 (close=100) must execute at bar 6 OPEN (105), not bar 5 close (100)!
    if len(bt.portfolio.trades) > 0 or bt.portfolio.position is not None:
        trade_entry_price = bt.portfolio.trades[0].entry_price if bt.portfolio.trades else bt.portfolio.position.entry_price
        # open is 105, with 0.03% slippage it is 105.0315
        assert trade_entry_price > 104.0, f"Expected entry at bar 6 open (~105), got {trade_entry_price}"
        print("  ✅ PASS: Signals at bar t strictly execute at bar t+1 OPEN with slippage. No lookahead leakage.")
        passed_tests += 1
    else:
        print("  ❌ FAIL: Trade was not executed as expected.")

    # ---------------------------------------------------------
    # TEST 2: Gap Down through Stop Loss
    # ---------------------------------------------------------
    print("\n[Audit 2/6] Gap Down Past Stop Loss...")
    # Position entered at 100 with SL at 95. Next bar opens at 80 (gap down).
    portfolio = Portfolio(initial_capital=1000, risk_per_trade_pct=0.02)
    costs = TradingCosts(fee_rate=0.0005, slippage_rate=0.0003)
    exec_engine = ExecutionEngine(portfolio, costs)

    # Open position
    bar_entry = pd.Series({"timestamp": pd.Timestamp("2023-01-01 00:00"), "open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0})
    exec_engine.execute_market_entry("TEST", "LONG", bar_entry, stop_loss=95.0, take_profit=115.0)

    # Next bar gaps down to 80 (well below 95 SL)
    gap_bar = pd.Series({"timestamp": pd.Timestamp("2023-01-01 01:00"), "open": 80.0, "high": 82.0, "low": 75.0, "close": 78.0})
    trade = exec_engine.check_in_bar_exits(gap_bar)

    assert trade is not None, "Trade should have exited on gap bar"
    # Exit price must be ~80 (slipped), NOT 95!
    assert trade.exit_price < 81.0, f"Gap down failed: filled at {trade.exit_price} instead of gap open ~80!"
    print(f"  ✅ PASS: Stop loss at $95 with gap open at $80 realistically filled at ${trade.exit_price:.2f} (no magic SL fills).")
    passed_tests += 1

    # ---------------------------------------------------------
    # TEST 3: Double-touch SL / TP Collision
    # ---------------------------------------------------------
    print("\n[Audit 3/6] Double-Touch SL/TP Collision in Single Candle...")
    portfolio = Portfolio(initial_capital=1000)
    exec_engine = ExecutionEngine(portfolio, costs)
    exec_engine.execute_market_entry("TEST", "LONG", bar_entry, stop_loss=90.0, take_profit=110.0)

    # Giant bar touching BOTH 85 (< SL 90) and 115 (> TP 110)
    giant_bar = pd.Series({"timestamp": pd.Timestamp("2023-01-01 02:00"), "open": 100.0, "high": 120.0, "low": 80.0, "close": 105.0})
    collision_trade = exec_engine.check_in_bar_exits(giant_bar)

    assert collision_trade.exit_reason == "STOP_LOSS", f"Expected conservative STOP_LOSS, got {collision_trade.exit_reason}"
    print(f"  ✅ PASS: High/Low touching both SL and TP handled conservatively: triggered {collision_trade.exit_reason}.")
    passed_tests += 1

    # ---------------------------------------------------------
    # TEST 4: Notional Fee Accounting
    # ---------------------------------------------------------
    print("\n[Audit 4/6] Notional Fee Accounting (Volume vs PnL)...")
    portfolio = Portfolio(initial_capital=1000)
    # Buy 2 units at $100 = $200 notional
    fee_rate = 0.001  # 0.1%
    portfolio.open_position("TEST", "LONG", entry_price=100.0, size=2.0, entry_time=pd.Timestamp.now(), stop_loss=90, take_profit=120, fee_rate=fee_rate)
    # Sell 2 units at $110 = $220 notional
    closed_trade = portfolio.close_position(exit_price=110.0, exit_time=pd.Timestamp.now(), fee_rate=fee_rate, exit_reason="TP")

    # Expected fees = (2 * 100 * 0.001) + (2 * 110 * 0.001) = 0.20 + 0.22 = 0.42 USD
    expected_fees = 0.42
    assert abs(closed_trade.fees - expected_fees) < 1e-4, f"Expected fee ${expected_fees}, got ${closed_trade.fees}"
    print(f"  ✅ PASS: Fees charged on Notional Trade Volume ($200 entry + $220 exit = ${closed_trade.fees:.2f} fees).")
    passed_tests += 1

    # ---------------------------------------------------------
    # TEST 5: Daily Circuit Breaker / Halt
    # ---------------------------------------------------------
    print("\n[Audit 5/6] Daily Circuit Breaker (3% Daily Drawdown Limit)...")
    portfolio = Portfolio(initial_capital=1000, max_daily_loss_pct=0.03)
    # Lose $40 on day 1 (4% > 3% limit)
    portfolio.open_position("TEST", "LONG", entry_price=100.0, size=1.0, entry_time=pd.Timestamp("2023-01-01 01:00"), stop_loss=90, take_profit=120, fee_rate=0)
    portfolio.close_position(exit_price=60.0, exit_time=pd.Timestamp("2023-01-01 02:00"), fee_rate=0, exit_reason="SL")
    portfolio.mark_to_market(60.0, pd.Timestamp("2023-01-01 02:00"))

    # Attempt to open a new position on the same day
    new_size = portfolio.calculate_position_size(entry_price=100.0, stop_loss=90.0, side="LONG")
    assert new_size == 0.0, f"Circuit breaker failed to halt trading: allowed size {new_size}"
    print("  ✅ PASS: Daily loss of 4% triggered circuit breaker. New position sizing halted to 0.")
    passed_tests += 1

    # ---------------------------------------------------------
    # TEST 6: Data Continuity & Missing Candles Audit
    # ---------------------------------------------------------
    print("\n[Audit 6/6] Binance Data Health & Continuity Audit (2023-01 -> 2023-04)...")
    from backtest.data.loader import DataLoader
    loader = DataLoader(symbol="BTCUSDT", interval="1h")
    clean_df = loader.load(start_date="2023-01-01", end_date="2023-04-01", fill_missing=True)
    time_diffs = clean_df["timestamp"].diff().dropna()
    expected_delta = pd.Timedelta(hours=1)
    gaps = time_diffs[time_diffs > expected_delta]

    assert len(gaps) == 0, f"Gaps remained after cleaning: {len(gaps)}"
    print(f"  ✅ PASS: DataLoader successfully detected Binance maintenance downtime and healed continuity ({len(clean_df):,} continuous bars).")
    passed_tests += 1

    print("\n" + "=" * 60)
    print(f"  AUDIT SUMMARY: {passed_tests}/{total_tests} TESTS PASSED PERFECTLY")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_audit()
