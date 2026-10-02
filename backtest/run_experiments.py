import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
from backtest.data.loader import DataLoader
from backtest.engine.backtester import Backtester
from backtest.strategies.donchian_breakout import DonchianBreakoutStrategy, DonchianATRTrailingStrategy


def run_experiment_matrix(
    symbol: str = "BTCUSDT",
    timeframes: list = ["1h", "4h", "1d"],
    phases: dict = {
        "Dev (2022-2023)": ("2022-01-01", "2024-01-01"),
        "Val (2024)": ("2024-01-01", "2025-01-01")
    }
):
    print("=" * 80)
    print(f"  QUANT BREAKOUT HYPOTHESIS TESTING MATRIX: {symbol}")
    print("=" * 80)

    strategies = {
        "Donchian 20 (Sys 1)": lambda: DonchianBreakoutStrategy(entry_period=20, exit_period=10, atr_multiplier=2.0),
        "Donchian 55 (Sys 2)": lambda: DonchianBreakoutStrategy(entry_period=55, exit_period=20, atr_multiplier=2.0),
        "Donchian ATR Trail": lambda: DonchianATRTrailingStrategy(entry_period=20, atr_multiplier=2.0, trail_multiplier=2.5)
    }

    results = []

    for phase_name, (start_dt, end_dt) in phases.items():
        print(f"\n⏳ Processing Phase: {phase_name} [{start_dt} -> {end_dt}]...")

        for tf in timeframes:
            loader = DataLoader(symbol=symbol, interval=tf)
            df = loader.load(start_date=start_dt, end_date=end_dt, fill_missing=True)

            for strat_label, strat_factory in strategies.items():
                strategy = strat_factory()
                bt = Backtester(
                    strategy=strategy,
                    initial_capital=1000.0,
                    risk_per_trade_pct=0.01,
                    max_exposure_pct=0.30,
                    max_daily_loss_pct=0.03,
                    fee_rate=0.0005,
                    slippage_rate=0.0003
                )
                warmup = 30 if tf in ["4h", "1d"] else 60
                run_res = bt.run(df, warmup_bars=min(warmup, len(df) // 4))
                m = run_res["metrics"]

                results.append({
                    "Phase": phase_name,
                    "TF": tf,
                    "Strategy": strat_label,
                    "Strat Return": f"{m['net_pnl_pct']:+.2f}%",
                    "B&H Return": f"{m['bnh_return_pct']:+.2f}%",
                    "Alpha": f"{m['alpha_vs_bnh']:+.2f}%",
                    "MDD": f"-{m['max_drawdown_pct']:.2f}%",
                    "Sharpe": f"{m['sharpe']:.2f}",
                    "Profit Factor": f"{m['profit_factor']:.2f}",
                    "Expectancy": f"${m['expectancy']:.2f}",
                    "Trades": m['total_trades'],
                    "Win Rate": f"{m['win_rate']:.1f}%",
                    "Exposure": f"{m['exposure_pct']:.1f}%",
                    "Fees": f"${m['total_fees']:.2f}",
                    "Max Consec Loss": m['max_consecutive_losses']
                })

    res_df = pd.DataFrame(results)
    print("\n" + "=" * 120)
    print("  EXPERIMENT MATRIX RESULTS SUMMARY")
    print("=" * 120)
    print(res_df.to_string(index=False))
    print("=" * 120 + "\n")
    return res_df


if __name__ == "__main__":
    run_experiment_matrix()
