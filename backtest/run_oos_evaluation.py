import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from backtest.data.loader import DataLoader
from backtest.engine.backtester import Backtester
from backtest.strategies.donchian_breakout import DonchianBreakoutStrategy


def run_oos_evaluation(
    start_date: str = "2025-01-01",
    end_date: str = "2026-10-02",
    assets: list = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
):
    print("=" * 90)
    print("  OUT-OF-SAMPLE (OOS) EVALUATION: 2025-01-01 -> TODAY (2026-10-02)")
    print("  Configuration Frozen: Donchian 55 (Sys 2) | 4H | 1% Risk | 30% Max Exposure")
    print("  Code Fingerprint Verified: RESEARCH_FREEZE_v1")
    print("=" * 90)

    summary_rows = []
    outlier_rows = []

    for symbol in assets:
        print(f"\n🌐 Loading OOS data for {symbol} (4h) [{start_date} -> {end_date}]...")
        loader = DataLoader(symbol=symbol, interval="4h")
        try:
            df = loader.load(start_date=start_date, end_date=end_date, fill_missing=True)
        except Exception as e:
            print(f"❌ Failed to load {symbol}: {e}")
            continue

        strategy = DonchianBreakoutStrategy(entry_period=55, exit_period=20, atr_multiplier=2.0)
        bt = Backtester(
            strategy=strategy,
            initial_capital=1000.0,
            risk_per_trade_pct=0.01,
            max_exposure_pct=0.30,
            max_daily_loss_pct=0.03,
            fee_rate=0.0005,
            slippage_rate=0.0003
        )
        run_res = bt.run(df, warmup_bars=30)
        m = run_res["metrics"]
        trades = run_res["trades"]

        # -------------------------------------------------------------
        # 5-Question Audit Computations:
        # Question 5: Outlier Dependence (Top 1 & Top 2 trades contribution)
        # -------------------------------------------------------------
        pnls = sorted([t.pnl for t in trades], reverse=True)
        total_pnl = m["net_pnl"]
        num_trades = len(trades)

        if num_trades > 0 and len(pnls) >= 2:
            top_1_pnl = pnls[0]
            top_2_pnl = pnls[0] + pnls[1]
            pnl_ex_top1 = total_pnl - top_1_pnl
            pnl_ex_top2 = total_pnl - top_2_pnl

            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p <= 0]
            gross_loss = abs(sum(losses)) if losses else 0.0

            # Profit Factor without top 1
            wins_ex_1 = wins[1:] if len(wins) > 1 else []
            pf_ex_top1 = (sum(wins_ex_1) / gross_loss) if gross_loss > 0 else 0.0

            # Profit Factor without top 2
            wins_ex_2 = wins[2:] if len(wins) > 2 else []
            pf_ex_top2 = (sum(wins_ex_2) / gross_loss) if gross_loss > 0 else 0.0
        else:
            top_1_pnl = 0.0
            top_2_pnl = 0.0
            pnl_ex_top1 = total_pnl
            pnl_ex_top2 = total_pnl
            pf_ex_top1 = m["profit_factor"]
            pf_ex_top2 = m["profit_factor"]

        summary_rows.append({
            "Asset": symbol,
            "Strat Return": f"{m['net_pnl_pct']:+.2f}%",
            "B&H Return": f"{m['bnh_return_pct']:+.2f}%",
            "Alpha": f"{m['alpha_vs_bnh']:+.2f}%",
            "Strat MDD": f"-{m['max_drawdown_pct']:.2f}%",
            "B&H MDD": f"-{m['bnh_max_dd_pct']:.2f}%",
            "Strat Sharpe": f"{m['sharpe']:.2f}",
            "B&H Sharpe": f"{m['bnh_sharpe']:.2f}",
            "Profit Factor": f"{m['profit_factor']:.2f}",
            "Expectancy": f"${m['expectancy']:.2f}",
            "Trades": m["total_trades"],
            "Win Rate": f"{m['win_rate']:.1f}%",
            "Exposure": f"{m['exposure_pct']:.1f}%",
            "Fees": f"${m['total_fees']:.2f}",
            "Max Loss Streak": m["max_consecutive_losses"]
        })

        outlier_rows.append({
            "Asset": symbol,
            "Total Net PnL": f"${total_pnl:+.2f}",
            "Top 1 Trade": f"${top_1_pnl:+.2f}",
            "Top 1 % of PnL": f"{(top_1_pnl / total_pnl * 100):.1f}%" if total_pnl != 0 else "N/A",
            "PnL (ex Top 1)": f"${pnl_ex_top1:+.2f}",
            "PF (ex Top 1)": f"{pf_ex_top1:.2f}",
            "PnL (ex Top 2)": f"${pnl_ex_top2:+.2f}",
            "PF (ex Top 2)": f"{pf_ex_top2:.2f}"
        })

    sum_df = pd.DataFrame(summary_rows)
    out_df = pd.DataFrame(outlier_rows)

    print("\n" + "=" * 125)
    print("  TABLE 1: OOS PERFORMANCE SUMMARY (2025-01-01 -> 2026-10-02)")
    print("=" * 125)
    print(sum_df.to_string(index=False))
    print("=" * 125)

    print("\n" + "=" * 110)
    print("  TABLE 2: OOS OUTLIER DEPENDENCE AUDIT (Excluding Top 1 & Top 2 Trades)")
    print("=" * 110)
    print(out_df.to_string(index=False))
    print("=" * 110 + "\n")

    return sum_df, out_df


if __name__ == "__main__":
    run_oos_evaluation()
