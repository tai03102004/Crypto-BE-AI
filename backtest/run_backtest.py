import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from backtest.data.loader import DataLoader
from backtest.engine.backtester import Backtester
from backtest.strategies.ema_cross import EMACrossoverStrategy
from backtest.strategies.rsi_bb import RSIBollingerStrategy
from backtest.strategies.regime_trend import RegimeFilteredTrendStrategy


def format_currency(val: float) -> str:
    return f"${val:,.2f}"


def format_pct(val: float) -> str:
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}%"


def print_report(symbol: str, interval: str, regime_name: str, metrics: dict):
    print("\n" + "=" * 50)
    print(f"  QUANT BACKTEST REPORT: {symbol} [{interval.upper()}] - {regime_name.upper()}")
    print("=" * 50)
    print(f" Strategy            : {metrics.get('strategy_name', 'N/A')}")
    print(f" Bars Evaluated      : {metrics.get('bars_processed', 0):,}")
    print("-" * 50)
    print(f" Initial Capital     : {format_currency(metrics['initial_capital'])}")
    print(f" Final Equity        : {format_currency(metrics['final_equity'])}")
    print(f" Strategy Net PnL    : {format_currency(metrics['net_pnl'])} ({format_pct(metrics['net_pnl_pct'])}) | MDD: -{metrics['max_drawdown_pct']:.2f}%")
    print(f" Buy & Hold Return   : {format_pct(metrics.get('bnh_return_pct', 0.0))} | MDD: -{metrics.get('bnh_max_dd_pct', 0.0):.2f}%")
    print(f" Alpha vs Buy & Hold : {format_pct(metrics.get('alpha_vs_bnh', 0.0))}")
    print("-" * 50)
    print(f" Total Trades        : {metrics['total_trades']}")
    print(f" Win Rate            : {metrics['win_rate']:.2f}% ({metrics.get('win_trades', 0)} wins / {metrics.get('loss_trades', 0)} losses)")
    print(f" Profit Factor       : {metrics['profit_factor']:.2f}")
    print(f" Payoff Ratio (W/L)  : {metrics['payoff_ratio']:.2f}")
    print(f" Avg Win / Avg Loss  : {format_currency(metrics['avg_win'])} / {format_currency(metrics['avg_loss'])}")
    print(f" Expectancy / Trade  : {format_currency(metrics['expectancy'])} ({format_pct(metrics['expectancy_pct'])})")
    print("-" * 50)
    print(f" Sharpe Ratio (Ann.) : {metrics['sharpe']:.2f} (B&H Sharpe: {metrics.get('bnh_sharpe', 0.0):.2f})")
    print(f" Sortino Ratio       : {metrics['sortino']:.2f}")
    print(f" Max Drawdown (MDD)  : -{metrics['max_drawdown_pct']:.2f}%")
    print(f" Max Consec. Losses  : {metrics['max_consecutive_losses']}")
    print(f" Market Exposure     : {metrics['exposure_pct']:.2f}%")
    print(f" Total Fees & Slip.  : {format_currency(metrics['total_fees'])}")
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Deterministic Quantitative Backtest Engine")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Pair symbol (e.g. BTCUSDT, ETHUSDT)")
    parser.add_argument("--interval", type=str, default="1h", help="Kline interval (e.g. 15m, 1h, 4h)")
    parser.add_argument("--start", type=str, default="2023-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default="2024-01-01", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--strategy",
        type=str,
        default="ema_cross",
        choices=["ema_cross", "rsi_bb", "regime_trend", "donchian_20", "donchian_55", "donchian_atr"],
        help="Strategy name"
    )
    parser.add_argument("--capital", type=float, default=1000.0, help="Initial capital in USD")
    parser.add_argument("--risk", type=float, default=0.01, help="Fixed fractional risk per trade (0.01 = 1 percent)")
    parser.add_argument("--split", type=str, default="all", choices=["all", "train", "val", "oos"], help="Regime split to evaluate")
    args = parser.parse_args()

    print(f"🚀 Initializing Backtest for {args.symbol} {args.interval}...")
    loader = DataLoader(symbol=args.symbol, interval=args.interval)
    loader.load(start_date=args.start, end_date=args.end)

    if args.split == "all":
        eval_df = loader.df
    else:
        splits = loader.split_regimes(train_end="2024-01-01", val_end="2025-01-01")
        eval_df = splits[args.split]

    # Instantiate chosen strategy
    if args.strategy == "ema_cross":
        strategy = EMACrossoverStrategy(fast_period=20, slow_period=50, trend_period=200, risk_reward=2.0)
    elif args.strategy == "rsi_bb":
        strategy = RSIBollingerStrategy(bb_period=20, rsi_period=14, rsi_oversold=30.0, risk_reward=2.0)
    elif args.strategy == "regime_trend":
        strategy = RegimeFilteredTrendStrategy(fast_period=20, slow_period=50, macro_period=200, adx_threshold=20.0, volume_multiplier=1.2, risk_reward=2.5)
    elif args.strategy == "donchian_20":
        from backtest.strategies.donchian_breakout import DonchianBreakoutStrategy
        strategy = DonchianBreakoutStrategy(entry_period=20, exit_period=10, atr_multiplier=2.0)
    elif args.strategy == "donchian_55":
        from backtest.strategies.donchian_breakout import DonchianBreakoutStrategy
        strategy = DonchianBreakoutStrategy(entry_period=55, exit_period=20, atr_multiplier=2.0)
    elif args.strategy == "donchian_atr":
        from backtest.strategies.donchian_breakout import DonchianATRTrailingStrategy
        strategy = DonchianATRTrailingStrategy(entry_period=20, atr_multiplier=2.0, trail_multiplier=2.5)
    else:
        raise ValueError(f"Unknown strategy: {args.strategy}")

    backtester = Backtester(
        strategy=strategy,
        initial_capital=args.capital,
        risk_per_trade_pct=args.risk,
        max_exposure_pct=0.30,
        max_daily_loss_pct=0.03,
        fee_rate=0.0005,
        slippage_rate=0.0003
    )

    result = backtester.run(eval_df)
    print_report(
        symbol=args.symbol,
        interval=args.interval,
        regime_name=f"{args.split} ({args.start} -> {args.end})",
        metrics=result["metrics"]
    )


if __name__ == "__main__":
    main()
