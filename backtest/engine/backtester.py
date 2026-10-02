import pandas as pd
from typing import Dict, Any, Optional
from .portfolio import Portfolio
from .costs import TradingCosts
from .execution import ExecutionEngine
from ..strategies.base import BaseStrategy
from ..metrics.performance import PerformanceMetrics


class Backtester:
    """
    Bar-by-bar backtest runner.
    Ensures strict chronological processing and eliminates lookahead bias:
    1. At bar t: Check if active position hits SL/TP in bar t (using High/Low).
    2. If pending entry/exit order was generated at bar t-1 close, execute at bar t OPEN.
    3. Strategy inspects history up to bar t CLOSE, emits signal for bar t+1.
    4. Mark-to-market portfolio value at bar t CLOSE.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        initial_capital: float = 1000.0,
        risk_per_trade_pct: float = 0.01,
        max_exposure_pct: float = 0.30,
        max_daily_loss_pct: float = 0.03,
        fee_rate: float = 0.0005,
        slippage_rate: float = 0.0003
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.portfolio = Portfolio(
            initial_capital=initial_capital,
            risk_per_trade_pct=risk_per_trade_pct,
            max_exposure_pct=max_exposure_pct,
            max_daily_loss_pct=max_daily_loss_pct
        )
        self.costs = TradingCosts(fee_rate=fee_rate, slippage_rate=slippage_rate)
        self.execution = ExecutionEngine(portfolio=self.portfolio, costs=self.costs)

    def run(self, df: pd.DataFrame, warmup_bars: int = 100) -> Dict[str, Any]:
        """
        Executes backtest over provided DataFrame.
        """
        if len(df) <= warmup_bars:
            raise ValueError(f"Data length ({len(df)}) is too short for warmup period ({warmup_bars})")

        total_bars = len(df)
        pending_signal = None

        for i in range(warmup_bars, total_bars):
            current_bar = df.iloc[i]

            # 1. Execute any pending orders generated at previous bar's close (executed at current bar OPEN)
            if pending_signal is not None:
                if pending_signal.action == "BUY" and self.portfolio.position is None:
                    self.execution.execute_market_entry(
                        symbol="ASSET",
                        side="LONG",
                        bar=current_bar,
                        stop_loss=pending_signal.stop_loss,
                        take_profit=pending_signal.take_profit,
                        reason=pending_signal.reason
                    )
                elif pending_signal.action == "CLOSE" and self.portfolio.position is not None:
                    self.execution.execute_market_exit(
                        bar=current_bar,
                        reason=pending_signal.reason
                    )
                pending_signal = None

            # 2. Check intra-bar Stop Loss / Take Profit on current bar's High / Low
            if self.portfolio.position is not None:
                self.execution.check_in_bar_exits(current_bar)

            # 3. Strategy evaluates history strictly up to bar t close
            history_window = df.iloc[: i + 1]
            signal = self.strategy.on_bar(current_bar, history_window)

            # Update trailing stop on existing position if provided
            if self.portfolio.position is not None and signal.trailing_stop > 0:
                self.portfolio.update_trailing_stop(signal.trailing_stop)

            if signal.action in ["BUY", "CLOSE"]:
                pending_signal = signal

            # 4. Mark to market portfolio at bar close
            self.portfolio.mark_to_market(
                current_price=current_bar["close"],
                current_time=current_bar["timestamp"]
            )

        # Close any lingering open position at final bar close
        if self.portfolio.position is not None:
            last_bar = df.iloc[-1]
            self.execution.execute_market_exit(last_bar, reason="BACKTEST_END")
            self.portfolio.mark_to_market(last_bar["close"], last_bar["timestamp"])

        # Compute performance summary
        metrics = PerformanceMetrics.calculate(
            trades=self.portfolio.trades,
            equity_curve=self.portfolio.equity_curve,
            initial_capital=self.initial_capital,
            market_df=df
        )
        metrics["strategy_name"] = self.strategy.name
        metrics["bars_processed"] = total_bars - warmup_bars

        return {
            "metrics": metrics,
            "trades": self.portfolio.trades,
            "equity_curve": pd.DataFrame(self.portfolio.equity_curve)
        }
