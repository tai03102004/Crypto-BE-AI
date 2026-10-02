import pandas as pd
from typing import Optional, Tuple
from .costs import TradingCosts
from .portfolio import Portfolio, TradeRecord


class ExecutionEngine:
    """
    Simulates realistic exchange order execution without lookahead bias:
    1. Signals evaluated at bar t close execute at bar t+1 OPEN.
    2. In-bar SL / TP checked against High / Low of bar t+1.
    3. Conservative SL priority: If both SL and TP could hit in the same bar,
       SL executes first to avoid optimistic survivorship bias.
    """

    def __init__(self, portfolio: Portfolio, costs: TradingCosts):
        self.portfolio = portfolio
        self.costs = costs

    def check_in_bar_exits(self, bar: pd.Series) -> Optional[TradeRecord]:
        """
        Evaluates active position against the current bar's High and Low.
        """
        pos = self.portfolio.position
        if pos is None:
            return None

        # LONG Position logic
        if pos.side == "LONG":
            hit_sl = bar["low"] <= pos.stop_loss
            hit_tp = bar["high"] >= pos.take_profit

            # Conservative tie-breaker: SL takes priority if both hit
            if hit_sl:
                # Gap Risk: if bar opens below SL, realistic execution is at Open (or worse), not at SL
                base_price = min(bar["open"], pos.stop_loss)
                exit_price, fee_rate = self.costs.calculate_exit_execution(base_price, "LONG")
                return self.portfolio.close_position(
                    exit_price=exit_price,
                    exit_time=bar["timestamp"],
                    fee_rate=fee_rate,
                    exit_reason="STOP_LOSS"
                )
            elif hit_tp:
                # Gap Up: if bar opens above TP, execution is at Open
                base_price = max(bar["open"], pos.take_profit)
                exit_price, fee_rate = self.costs.calculate_exit_execution(base_price, "LONG")
                return self.portfolio.close_position(
                    exit_price=exit_price,
                    exit_time=bar["timestamp"],
                    fee_rate=fee_rate,
                    exit_reason="TAKE_PROFIT"
                )

        # SHORT Position logic
        elif pos.side == "SHORT":
            hit_sl = bar["high"] >= pos.stop_loss
            hit_tp = bar["low"] <= pos.take_profit

            if hit_sl:
                # Gap Risk for short: if bar opens above SL, execution is at Open
                base_price = max(bar["open"], pos.stop_loss)
                exit_price, fee_rate = self.costs.calculate_exit_execution(base_price, "SHORT")
                return self.portfolio.close_position(
                    exit_price=exit_price,
                    exit_time=bar["timestamp"],
                    fee_rate=fee_rate,
                    exit_reason="STOP_LOSS"
                )
            elif hit_tp:
                # Gap Down for short: if bar opens below TP, execution is at Open
                base_price = min(bar["open"], pos.take_profit)
                exit_price, fee_rate = self.costs.calculate_exit_execution(base_price, "SHORT")
                return self.portfolio.close_position(
                    exit_price=exit_price,
                    exit_time=bar["timestamp"],
                    fee_rate=fee_rate,
                    exit_reason="TAKE_PROFIT"
                )

        return None

    def execute_market_entry(
        self,
        symbol: str,
        side: str,
        bar: pd.Series,
        stop_loss: float,
        take_profit: float,
        reason: str = ""
    ) -> bool:
        """
        Fills market order at bar's OPEN with slippage + fee.
        """
        open_price = bar["open"]
        exec_price, fee_rate = self.costs.calculate_entry_execution(open_price, side)

        size = self.portfolio.calculate_position_size(
            entry_price=exec_price,
            stop_loss=stop_loss,
            side=side
        )

        if size <= 0:
            return False

        return self.portfolio.open_position(
            symbol=symbol,
            side=side,
            entry_price=exec_price,
            size=size,
            entry_time=bar["timestamp"],
            stop_loss=stop_loss,
            take_profit=take_profit,
            fee_rate=fee_rate,
            reason=reason
        )

    def execute_market_exit(self, bar: pd.Series, reason: str = "SIGNAL_CLOSE") -> Optional[TradeRecord]:
        """
        Closes active position at bar's OPEN with slippage + fee.
        """
        pos = self.portfolio.position
        if pos is None:
            return None

        open_price = bar["open"]
        exec_price, fee_rate = self.costs.calculate_exit_execution(open_price, pos.side)
        return self.portfolio.close_position(
            exit_price=exec_price,
            exit_time=bar["timestamp"],
            fee_rate=fee_rate,
            exit_reason=reason
        )
