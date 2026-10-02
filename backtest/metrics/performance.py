import numpy as np
import pandas as pd
from typing import List, Dict, Any
from ..engine.portfolio import TradeRecord


class PerformanceMetrics:
    """
    Computes rigorous quantitative metrics on closed trades and equity curve.
    """

    @staticmethod
    def calculate(
        trades: List[TradeRecord],
        equity_curve: List[Dict[str, Any]],
        initial_capital: float,
        annualization_factor: float = 365 * 24,  # for 1-hour candles
        market_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        if not equity_curve:
            return {}

        eq_df = pd.DataFrame(equity_curve)
        eq_df["timestamp"] = pd.to_datetime(eq_df["timestamp"])
        final_equity = eq_df["equity"].iloc[-1]
        net_pnl = final_equity - initial_capital
        net_pnl_pct = (net_pnl / initial_capital) * 100

        # Buy & Hold Benchmark
        bnh_metrics = {
            "bnh_return_pct": 0.0,
            "bnh_max_dd_pct": 0.0,
            "bnh_sharpe": 0.0,
            "alpha_vs_bnh": 0.0
        }
        if market_df is not None and len(market_df) > 1:
            first_open = market_df["open"].iloc[0]
            last_close = market_df["close"].iloc[-1]
            bnh_ret = ((last_close - first_open) / first_open) * 100

            # B&H Max Drawdown
            bnh_peak = market_df["close"].cummax()
            bnh_dd = (market_df["close"] - bnh_peak) / bnh_peak
            bnh_max_dd = abs(bnh_dd.min()) * 100

            # B&H Sharpe
            m_daily = market_df.set_index("timestamp")["close"].resample("1D").last().pct_change().dropna()
            if len(m_daily) > 5 and m_daily.std() > 0:
                rf_daily = 0.04 / 365
                bnh_sharpe = ((m_daily - rf_daily).mean() / m_daily.std()) * np.sqrt(365)
            else:
                bnh_sharpe = 0.0

            bnh_metrics["bnh_return_pct"] = bnh_ret
            bnh_metrics["bnh_max_dd_pct"] = bnh_max_dd
            bnh_metrics["bnh_sharpe"] = bnh_sharpe
            bnh_metrics["alpha_vs_bnh"] = net_pnl_pct - bnh_ret

        # Exposure (% of time spent in position)
        exposure_pct = (eq_df["in_position"].mean()) * 100 if "in_position" in eq_df.columns else 0.0

        # Equity returns
        eq_df["returns"] = eq_df["equity"].pct_change().fillna(0.0)
        daily_returns = eq_df.set_index("timestamp")["equity"].resample("1D").last().pct_change().dropna()

        # Sharpe & Sortino (annualized using daily returns if available, else bar returns)
        if len(daily_returns) > 5 and daily_returns.std() > 0:
            ann_factor = 365
            rf_daily = 0.04 / 365  # 4% risk-free rate assumption
            excess_daily = daily_returns - rf_daily
            sharpe = (excess_daily.mean() / daily_returns.std()) * np.sqrt(ann_factor)

            downside = daily_returns[daily_returns < 0]
            downside_std = downside.std() if len(downside) > 0 and downside.std() > 0 else 1e-6
            sortino = (excess_daily.mean() / downside_std) * np.sqrt(ann_factor)
        else:
            sharpe = 0.0
            sortino = 0.0

        # Trade statistics
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "initial_capital": initial_capital,
                "final_equity": final_equity,
                "net_pnl": net_pnl,
                "net_pnl_pct": net_pnl_pct,
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "sharpe": 0.0,
                "sortino": 0.0,
                "max_drawdown_pct": 0.0,
                "max_consecutive_losses": 0,
                "exposure_pct": exposure_pct,
                "total_fees": 0.0,
                **bnh_metrics
            }

        pnls = [t.pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades) * 100

        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        avg_win = (gross_profit / win_count) if win_count > 0 else 0.0
        avg_loss = (gross_loss / loss_count) if loss_count > 0 else 0.0
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

        expectancy = (gross_profit - gross_loss) / total_trades
        expectancy_pct = (expectancy / initial_capital) * 100

        total_fees = sum(t.fees for t in trades)

        # Max consecutive losses
        max_consec_losses = 0
        current_consec = 0
        for p in pnls:
            if p <= 0:
                current_consec += 1
                if current_consec > max_consec_losses:
                    max_consec_losses = current_consec
            else:
                current_consec = 0

        # Max Drawdown from equity curve
        eq_series = eq_df["equity"]
        peak = eq_series.cummax()
        drawdown = (eq_series - peak) / peak
        max_dd_pct = abs(drawdown.min()) * 100

        return {
            "initial_capital": initial_capital,
            "final_equity": final_equity,
            "net_pnl": net_pnl,
            "net_pnl_pct": net_pnl_pct,
            "total_trades": total_trades,
            "win_trades": win_count,
            "loss_trades": loss_count,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "payoff_ratio": payoff_ratio,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
            "expectancy_pct": expectancy_pct,
            "sharpe": sharpe,
            "sortino": sortino,
            "max_drawdown_pct": max_dd_pct,
            "max_consecutive_losses": max_consec_losses,
            "exposure_pct": exposure_pct,
            "total_fees": total_fees,
            **bnh_metrics
        }

