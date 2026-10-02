import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
from backtest.data.loader import DataLoader
from backtest.engine.backtester import Backtester
from backtest.strategies.donchian_breakout import DonchianBreakoutStrategy, DonchianATRTrailingStrategy


def run_cross_asset_test():
    print("=" * 80)
    print("  CROSS-ASSET ROBUSTNESS TEST (FROZEN PARAMETERS: 4H | RISK 1%)")
    print("  Assets: BTCUSDT | ETHUSDT | SOLUSDT | BNBUSDT")
    print("  Development: 2022-01-01 -> 2024-01-01")
    print("  Validation : 2024-01-01 -> 2025-01-01")
    print("  Out-of-Sample (2025-2026): [STRICTLY LOCKED]")
    print("=" * 80)

    assets = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    phases = {
        "Dev (2022-2023)": ("2022-01-01", "2024-01-01"),
        "Val (2024)": ("2024-01-01", "2025-01-01")
    }

    # FROZEN PARAMETERS: No tuning per asset!
    strategies = {
        "Donchian 55 (Sys 2)": lambda: DonchianBreakoutStrategy(entry_period=55, exit_period=20, atr_multiplier=2.0),
        "Donchian ATR Trail": lambda: DonchianATRTrailingStrategy(entry_period=20, atr_multiplier=2.0, trail_multiplier=2.5)
    }

    results = []

    for phase_name, (start_dt, end_dt) in phases.items():
        print(f"\n⏳ Processing Phase: {phase_name} [{start_dt} -> {end_dt}]...")

        for symbol in assets:
            print(f"  Fetching & auditing {symbol} (4h)...")
            loader = DataLoader(symbol=symbol, interval="4h")
            try:
                df = loader.load(start_date=start_dt, end_date=end_dt, fill_missing=True)
            except Exception as e:
                print(f"  ❌ Error loading {symbol}: {e}")
                continue

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
                run_res = bt.run(df, warmup_bars=30)
                m = run_res["metrics"]

                results.append({
                    "Phase": phase_name,
                    "Asset": symbol,
                    "Strategy": strat_label,
                    "Strat Ret": f"{m['net_pnl_pct']:+.2f}%",
                    "B&H Ret": f"{m['bnh_return_pct']:+.2f}%",
                    "Alpha": f"{m['alpha_vs_bnh']:+.2f}%",
                    "Strat MDD": f"-{m['max_drawdown_pct']:.2f}%",
                    "B&H MDD": f"-{m['bnh_max_dd_pct']:.2f}%",
                    "Strat Sharpe": f"{m['sharpe']:.2f}",
                    "B&H Sharpe": f"{m['bnh_sharpe']:.2f}",
                    "Profit Factor": f"{m['profit_factor']:.2f}",
                    "Expectancy": f"${m['expectancy']:.2f}",
                    "Trades": m['total_trades'],
                    "Win Rate": f"{m['win_rate']:.1f}%",
                    "Exposure": f"{m['exposure_pct']:.1f}%",
                    "Fees": f"${m['total_fees']:.2f}",
                    "Max Losing Streak": m['max_consecutive_losses']
                })

    res_df = pd.DataFrame(results)
    print("\n" + "=" * 135)
    print("  CROSS-ASSET ROBUSTNESS RESULTS (METHODOLOGY: IDENTICAL METHODOLOGY FOR STRAT & B&H SHARPE)")
    print("=" * 135)
    print(res_df.to_string(index=False))
    print("=" * 135 + "\n")
    return res_df


if __name__ == "__main__":
    run_cross_asset_test()
