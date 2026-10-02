import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from backtest.data.loader import DataLoader
from backtest.engine.backtester import Backtester
from backtest.strategies.donchian_breakout import DonchianBreakoutStrategy


def compute_metrics_for_subset(trades: list, initial_capital: float = 1000.0) -> dict:
    if not trades:
        return {"pnl": 0.0, "pnl_pct": 0.0, "pf": 0.0, "expectancy": 0.0, "trades": 0}

    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    net_pnl = gross_profit - gross_loss
    net_pnl_pct = (net_pnl / initial_capital) * 100

    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    expectancy = net_pnl / len(trades) if trades else 0.0

    return {
        "pnl": net_pnl,
        "pnl_pct": net_pnl_pct,
        "pf": profit_factor,
        "expectancy": expectancy,
        "trades": len(trades)
    }


def run_tail_robustness_report(
    assets: list = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
    start_date: str = "2025-01-01",
    end_date: str = "2026-10-02"
):
    print("=" * 115)
    print(f"  QUANT TAIL ROBUSTNESS REPORT: OUT-OF-SAMPLE ({start_date} -> {end_date})")
    print("  Evaluating sensitivity to tail winners: Full vs -Top1 vs -Top2 vs -Top5 vs -Top10%")
    print("  Strategy: Donchian 55 (Sys 2) | 4H | 1% Risk | 30% Max Exposure (FROZEN)")
    print("=" * 115)

    report_rows = []

    for symbol in assets:
        loader = DataLoader(symbol=symbol, interval="4h")
        try:
            df = loader.load(start_date=start_date, end_date=end_date, fill_missing=True)
        except Exception as e:
            print(f"Error loading {symbol}: {e}")
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
        trades = run_res["trades"]

        if not trades:
            continue

        # Sort trades strictly descending by Net PnL (Top winners first)
        sorted_trades = sorted(trades, key=lambda t: t.pnl, reverse=True)
        n = len(sorted_trades)

        # 1. Full Sample
        full_m = compute_metrics_for_subset(sorted_trades)

        # 2. Exclude Top 1
        ex_top1_trades = sorted_trades[1:] if n > 1 else []
        ex1_m = compute_metrics_for_subset(ex_top1_trades)

        # 3. Exclude Top 2
        ex_top2_trades = sorted_trades[2:] if n > 2 else []
        ex2_m = compute_metrics_for_subset(ex_top2_trades)

        # 4. Exclude Top 5
        ex_top5_trades = sorted_trades[5:] if n > 5 else []
        ex5_m = compute_metrics_for_subset(ex_top5_trades)

        # 5. Exclude Top 10%
        top_10pct_count = max(1, int(np.ceil(n * 0.10)))
        ex_top10pct_trades = sorted_trades[top_10pct_count:] if n > top_10pct_count else []
        ex_10pct_m = compute_metrics_for_subset(ex_top10pct_trades)

        report_rows.append({
            "Asset": symbol,
            "Trades": n,
            "Full PnL": f"${full_m['pnl']:+.2f}",
            "Full PF": f"{full_m['pf']:.2f}",
            "Full Exp": f"${full_m['expectancy']:+.2f}",
            "(-Top1) PF": f"{ex1_m['pf']:.2f}",
            "(-Top1) Exp": f"${ex1_m['expectancy']:+.2f}",
            "(-Top2) PF": f"{ex2_m['pf']:.2f}",
            "(-Top2) Exp": f"${ex2_m['expectancy']:+.2f}",
            "(-Top5) PF": f"{ex5_m['pf']:.2f}",
            "(-Top5) Exp": f"${ex5_m['expectancy']:+.2f}",
            "Top 10% Cut": f"{top_10pct_count} trades",
            "(-Top10%) PF": f"{ex_10pct_m['pf']:.2f}",
            "(-Top10%) Exp": f"${ex_10pct_m['expectancy']:+.2f}"
        })

    rep_df = pd.DataFrame(report_rows)
    print("\n" + rep_df.to_string(index=False))
    print("=" * 115 + "\n")
    return rep_df


if __name__ == "__main__":
    run_tail_robustness_report()
