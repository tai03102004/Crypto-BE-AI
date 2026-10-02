"""
Engine Audit 2.0: Comprehensive Property & Invariant Test Suite.
Verifies 16 mathematical invariants across Execution, Accounting, and Risk.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from backtest.engine.portfolio import Portfolio, Position
from backtest.engine.costs import TradingCosts
from backtest.engine.execution import ExecutionEngine
from backtest.engine.backtester import Backtester
from backtest.strategies.base import BaseStrategy, Signal


def run_audit_v2():
    print("=" * 75)
    print("  QUANT ENGINE AUDIT 2.0: 16 PROPERTY & INVARIANT TESTS")
    print("=" * 75)
    passed = 0
    total = 16

    # -------------------------------------------------------------------------
    # 1. Next-Bar Execution Invariant
    # -------------------------------------------------------------------------
    class SignalAtBarFive(BaseStrategy):
        def on_bar(self, bar, hist):
            if bar["timestamp"] == pd.Timestamp("2023-01-01 05:00"):
                return Signal(action="BUY", stop_loss=90.0, take_profit=120.0)
            return Signal(action="HOLD")

    dates = pd.date_range("2023-01-01", periods=10, freq="1h")
    prices = [100.0] * 10
    prices[6] = 108.0  # Bar 6 opens at 108
    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices, "high": [p + 1 for p in prices],
        "low": [p - 1 for p in prices], "close": prices, "volume": [1000] * 10
    })
    bt = Backtester(strategy=SignalAtBarFive(), initial_capital=1000)
    bt.run(df, warmup_bars=2)
    entry_t = bt.portfolio.trades[0].entry_time if bt.portfolio.trades else bt.portfolio.position.entry_time
    assert entry_t == pd.Timestamp("2023-01-01 06:00"), f"Expected entry at 06:00, got {entry_t}"
    print("[01/16] ✅ Next-Bar Execution: Signal at bar t (05:00) strictly filled at bar t+1 OPEN (06:00).")
    passed += 1

    # -------------------------------------------------------------------------
    # 2. Strict Timeline Isolation (No Future Data Leakage)
    # -------------------------------------------------------------------------
    class HistoryLeakDetector(BaseStrategy):
        def on_bar(self, bar, hist):
            if hist.iloc[-1]["timestamp"] > bar["timestamp"]:
                raise AssertionError("Future data detected in history window!")
            return Signal(action="HOLD")

    bt = Backtester(strategy=HistoryLeakDetector(), initial_capital=1000)
    bt.run(df, warmup_bars=2)
    print("[02/16] ✅ History Isolation: Strategy history window strictly bounded by current bar t close.")
    passed += 1

    # -------------------------------------------------------------------------
    # 3. Gap Down through Stop Loss (Long)
    # -------------------------------------------------------------------------
    costs = TradingCosts(fee_rate=0.0005, slippage_rate=0.0003)
    p = Portfolio(initial_capital=1000)
    exec_eng = ExecutionEngine(p, costs)
    bar_entry = pd.Series({"timestamp": pd.Timestamp("2023-01-01 00:00"), "open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0})
    exec_eng.execute_market_entry("ASSET", "LONG", bar_entry, stop_loss=95.0, take_profit=120.0)

    # Gap down to 80 on next bar
    gap_bar = pd.Series({"timestamp": pd.Timestamp("2023-01-01 01:00"), "open": 80.0, "high": 81.0, "low": 78.0, "close": 79.0})
    trade = exec_eng.check_in_bar_exits(gap_bar)
    assert trade.exit_price < 80.0, f"Gap down Long failed: filled at {trade.exit_price}"
    print(f"[03/16] ✅ Gap Down Past SL (Long): SL=$95 with Gap Open=$80 filled realistically at ${trade.exit_price:.2f}.")
    passed += 1

    # -------------------------------------------------------------------------
    # 4. Gap Up through Take Profit (Long)
    # -------------------------------------------------------------------------
    p = Portfolio(initial_capital=1000)
    exec_eng = ExecutionEngine(p, costs)
    exec_eng.execute_market_entry("ASSET", "LONG", bar_entry, stop_loss=90.0, take_profit=110.0)
    gap_up_bar = pd.Series({"timestamp": pd.Timestamp("2023-01-01 01:00"), "open": 125.0, "high": 128.0, "low": 124.0, "close": 127.0})
    trade_tp = exec_eng.check_in_bar_exits(gap_up_bar)
    assert trade_tp.exit_price > 124.0, f"Gap up TP failed: filled at {trade_tp.exit_price}"
    print(f"[04/16] ✅ Gap Up Past TP (Long): TP=$110 with Gap Open=$125 filled at gap price ${trade_tp.exit_price:.2f}.")
    passed += 1

    # -------------------------------------------------------------------------
    # 5. Gap Up through Stop Loss (Short)
    # -------------------------------------------------------------------------
    p = Portfolio(initial_capital=1000)
    exec_eng = ExecutionEngine(p, costs)
    exec_eng.execute_market_entry("ASSET", "SHORT", bar_entry, stop_loss=105.0, take_profit=80.0)
    gap_short_sl = pd.Series({"timestamp": pd.Timestamp("2023-01-01 01:00"), "open": 118.0, "high": 120.0, "low": 116.0, "close": 119.0})
    trade_short = exec_eng.check_in_bar_exits(gap_short_sl)
    assert trade_short.exit_price > 118.0, f"Gap up Short SL failed: filled at {trade_short.exit_price}"
    print(f"[05/16] ✅ Gap Past SL (Short): SL=$105 with Gap Open=$118 filled at gap price ${trade_short.exit_price:.2f}.")
    passed += 1

    # -------------------------------------------------------------------------
    # 6. Same-Bar SL + TP Collision Invariant (Conservative Priority)
    # -------------------------------------------------------------------------
    p = Portfolio(initial_capital=1000)
    exec_eng = ExecutionEngine(p, costs)
    exec_eng.execute_market_entry("ASSET", "LONG", bar_entry, stop_loss=92.0, take_profit=108.0)
    wild_bar = pd.Series({"timestamp": pd.Timestamp("2023-01-01 01:00"), "open": 100.0, "high": 115.0, "low": 85.0, "close": 102.0})
    col_trade = exec_eng.check_in_bar_exits(wild_bar)
    assert col_trade.exit_reason == "STOP_LOSS", f"Collision failed: expected STOP_LOSS, got {col_trade.exit_reason}"
    print("[06/16] ✅ Collision Invariant: High >= TP and Low <= SL in single candle triggers conservative STOP_LOSS.")
    passed += 1

    # -------------------------------------------------------------------------
    # 7. Notional Fee Accounting
    # -------------------------------------------------------------------------
    p = Portfolio(initial_capital=1000)
    p.open_position("TEST", "LONG", entry_price=50.0, size=4.0, entry_time=pd.Timestamp.now(), stop_loss=40, take_profit=70, fee_rate=0.001)
    # Entry notional = 200, fee = 0.20
    tr = p.close_position(exit_price=60.0, exit_time=pd.Timestamp.now(), fee_rate=0.001, exit_reason="TP")
    # Exit notional = 240, fee = 0.24, total fees = 0.44
    assert abs(tr.fees - 0.44) < 1e-5, f"Expected fee $0.44, got {tr.fees}"
    print(f"[07/16] ✅ Notional Fee Invariant: Fees charged strictly on traded notional (${tr.fees:.2f}).")
    passed += 1

    # -------------------------------------------------------------------------
    # 8. Two-Way Slippage Invariant
    # -------------------------------------------------------------------------
    tc = TradingCosts(fee_rate=0, slippage_rate=0.001)
    buy_exec, _ = tc.calculate_entry_execution(100.0, "BUY")
    sell_exec, _ = tc.calculate_entry_execution(100.0, "SELL")
    assert buy_exec > 100.0 and sell_exec < 100.0
    exit_long, _ = tc.calculate_exit_execution(100.0, "LONG")
    exit_short, _ = tc.calculate_exit_execution(100.0, "SHORT")
    assert exit_long < 100.0 and exit_short > 100.0
    print("[08/16] ✅ Two-Way Slippage Invariant: Entry & Exit slippage penalize trader in both directions.")
    passed += 1

    # -------------------------------------------------------------------------
    # 9. Realized PnL vs Cash Conservation
    # -------------------------------------------------------------------------
    p = Portfolio(initial_capital=1000)
    start_cash = p.cash
    p.open_position("TEST", "LONG", entry_price=100.0, size=2.0, entry_time=pd.Timestamp.now(), stop_loss=90, take_profit=110, fee_rate=0.0005)
    tr = p.close_position(exit_price=105.0, exit_time=pd.Timestamp.now(), fee_rate=0.0005, exit_reason="TP")
    cash_delta = p.cash - start_cash
    assert abs(cash_delta - tr.pnl) < 1e-5, f"Cash delta {cash_delta} != trade pnl {tr.pnl}"
    print(f"[09/16] ✅ Cash Conservation: Post-trade cash delta strictly equals Net PnL (${cash_delta:+.2f}).")
    passed += 1

    # -------------------------------------------------------------------------
    # 10. Unrealized PnL & Mark-to-Market Equity
    # -------------------------------------------------------------------------
    p = Portfolio(initial_capital=1000)
    p.open_position("TEST", "LONG", entry_price=100.0, size=2.0, entry_time=pd.Timestamp.now(), stop_loss=90, take_profit=120, fee_rate=0)
    # Cash was 1000 - 200 = 800. Mark at price 110: Equity = 800 + (2 * 110) = 1020
    p.mark_to_market(current_price=110.0, current_time=pd.Timestamp.now())
    assert abs(p.equity - 1020.0) < 1e-5, f"Expected equity 1020, got {p.equity}"
    print(f"[10/16] ✅ Mark-to-Market Invariant: Equity with open position strictly matches cash + asset value ($1,020.00).")
    passed += 1

    # -------------------------------------------------------------------------
    # 11. Zero Friction Reference Benchmark
    # -------------------------------------------------------------------------
    p_zero = Portfolio(initial_capital=1000)
    p_zero.open_position("TEST", "LONG", entry_price=100.0, size=3.0, entry_time=pd.Timestamp.now(), stop_loss=90, take_profit=130, fee_rate=0)
    tr_zero = p_zero.close_position(exit_price=120.0, exit_time=pd.Timestamp.now(), fee_rate=0, exit_reason="TP")
    assert tr_zero.pnl == 3.0 * (120.0 - 100.0), f"Frictionless PnL mismatch: {tr_zero.pnl}"
    print("[11/16] ✅ Zero-Friction Test: Fee=0 and Slip=0 exactly matches analytical size * (exit - entry).")
    passed += 1

    # -------------------------------------------------------------------------
    # 12. Zero Signal Invariance
    # -------------------------------------------------------------------------
    class IdleStrategy(BaseStrategy):
        def on_bar(self, bar, hist):
            return Signal(action="HOLD")

    idle_df = pd.DataFrame({
        "timestamp": pd.date_range("2023-01-01", periods=100, freq="1h"),
        "open": np.random.uniform(90, 110, 100),
        "high": np.random.uniform(110, 120, 100),
        "low": np.random.uniform(80, 90, 100),
        "close": np.random.uniform(90, 110, 100),
        "volume": [1000] * 100
    })
    bt_idle = Backtester(strategy=IdleStrategy(), initial_capital=1000)
    res_idle = bt_idle.run(idle_df, warmup_bars=10)
    assert res_idle["metrics"]["final_equity"] == 1000.0 and res_idle["metrics"]["net_pnl"] == 0.0
    print("[12/16] ✅ Zero-Signal Invariance: 0 trades yields strictly 0.00% variance and exact capital preservation.")
    passed += 1

    # -------------------------------------------------------------------------
    # 13. Sizing Property: Inverse Stop-Distance Relationship
    # -------------------------------------------------------------------------
    p = Portfolio(initial_capital=1000, risk_per_trade_pct=0.01, max_exposure_pct=0.50)
    # Stop distance = $5 (entry 100, SL 95) -> Risk $10 / 5 = 2 units
    size_narrow = p.calculate_position_size(entry_price=100.0, stop_loss=95.0, side="LONG")
    # Stop distance = $10 (entry 100, SL 90) -> Risk $10 / 10 = 1 unit
    size_wide = p.calculate_position_size(entry_price=100.0, stop_loss=90.0, side="LONG")
    assert abs(size_narrow - 2.0 * size_wide) < 1e-4, f"Sizing property failed: {size_narrow} vs {size_wide}"
    print(f"[13/16] ✅ Sizing Invariant: Doubling stop distance exactly halves position size ({size_narrow:.2f} -> {size_wide:.2f} units).")
    passed += 1

    # -------------------------------------------------------------------------
    # 14. 1% Risk Invariant on Stop Loss Fill
    # -------------------------------------------------------------------------
    p_risk = Portfolio(initial_capital=1000, risk_per_trade_pct=0.01)
    sz = p_risk.calculate_position_size(entry_price=100.0, stop_loss=95.0, side="LONG")
    p_risk.open_position("TEST", "LONG", entry_price=100.0, size=sz, entry_time=pd.Timestamp.now(), stop_loss=95.0, take_profit=110.0, fee_rate=0.0)
    loss_tr = p_risk.close_position(exit_price=95.0, exit_time=pd.Timestamp.now(), fee_rate=0.0, exit_reason="STOP_LOSS")
    assert abs(loss_tr.pnl - (-10.0)) < 1e-4, f"Loss at SL {loss_tr.pnl} does not equal exactly 1% ($10)"
    print(f"[14/16] ✅ 1% Risk Budget Invariant: Hitting Stop Loss loses precisely ${abs(loss_tr.pnl):.2f} (1.00% of $1,000 equity).")
    passed += 1

    # -------------------------------------------------------------------------
    # 15. Max Exposure Cap
    # -------------------------------------------------------------------------
    p_cap = Portfolio(initial_capital=1000, risk_per_trade_pct=0.05, max_exposure_pct=0.25)
    # Tiny stop distance $0.01 -> unlimited size without cap. Cap = 0.25 * 1000 / 100 = 2.5 units
    size_capped = p_cap.calculate_position_size(entry_price=100.0, stop_loss=99.99, side="LONG")
    assert abs(size_capped - 2.5) < 1e-4, f"Max exposure cap failed: size={size_capped}"
    print(f"[15/16] ✅ Exposure Invariant: Tiny stop distance safely clamped to max exposure limit (2.5 units = $250 / 25%).")
    passed += 1

    # -------------------------------------------------------------------------
    # 16. Circuit Breaker Halt Invariant
    # -------------------------------------------------------------------------
    p_halt = Portfolio(initial_capital=1000, max_daily_loss_pct=0.03)
    p_halt.update_daily_circuit_breaker(pd.Timestamp("2023-01-01 00:00"))
    p_halt.equity = 960.0  # 4% loss
    p_halt.update_daily_circuit_breaker(pd.Timestamp("2023-01-01 04:00"))
    assert p_halt.trading_halted_today is True
    post_halt_size = p_halt.calculate_position_size(entry_price=100, stop_loss=90, side="LONG")
    assert post_halt_size == 0.0, f"Circuit breaker allowed size {post_halt_size}"
    print("[16/16] ✅ Circuit Breaker Halt: 4% daily drawdown clamps subsequent position sizing strictly to 0.")
    passed += 1

    print("\n" + "=" * 75)
    print(f"  AUDIT 2.0 RESULT: ALL {passed}/{total} INVARIANT TESTS PASSED")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_audit_v2()
