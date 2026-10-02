from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd


@dataclass
class Position:
    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    size: float  # Quantity of asset
    entry_time: pd.Timestamp
    stop_loss: float
    take_profit: float
    cost_basis: float  # Value in USD at entry
    fees_paid: float = 0.0
    trailing_stop: Optional[float] = None
    reason: str = ""


@dataclass
class TradeRecord:
    symbol: str
    side: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    size: float
    pnl: float  # Net PnL in USD after fees & slippage
    pnl_pct: float  # Return on position value
    fees: float
    exit_reason: str  # "STOP_LOSS", "TAKE_PROFIT", "SIGNAL_REVERSAL", "KILL_SWITCH"


class Portfolio:
    """
    Deterministic Risk Management & Portfolio Accounting.
    Implements:
    - Fixed fractional risk per trade (e.g. 1% of current equity)
    - Position sizing derived from stop loss distance: Size = Risk$ / (Entry - SL)
    - Hard exposure limits (Max position size as % of portfolio)
    - Max daily loss limit (Circuit breaker)
    - Kill switch capability
    """

    def __init__(
        self,
        initial_capital: float = 1000.0,
        risk_per_trade_pct: float = 0.01,  # 1% equity risk
        max_exposure_pct: float = 0.30,    # Max 30% portfolio in a single position
        max_daily_loss_pct: float = 0.03,  # 3% daily circuit breaker
        allow_short: bool = False           # Spot (False) or Futures (True)
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.equity = initial_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_exposure_pct = max_exposure_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.allow_short = allow_short

        self.position: Optional[Position] = None
        self.trades: List[TradeRecord] = []
        self.equity_curve: List[Dict[str, Any]] = []

        # Daily loss tracking
        self.current_day: Optional[str] = None
        self.day_start_equity = initial_capital
        self.trading_halted_today = False

    def update_daily_circuit_breaker(self, current_time: pd.Timestamp):
        day_str = current_time.strftime("%Y-%m-%d")
        if self.current_day is None:
            self.current_day = day_str
            self.day_start_equity = self.initial_capital
            self.trading_halted_today = False
        elif self.current_day != day_str:
            self.current_day = day_str
            self.day_start_equity = self.equity
            self.trading_halted_today = False

        if self.day_start_equity > 0:
            daily_drawdown = (self.equity - self.day_start_equity) / self.day_start_equity
            if daily_drawdown <= -self.max_daily_loss_pct:
                self.trading_halted_today = True

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        side: str
    ) -> float:
        """
        Determines position size via Fixed Fractional Risk:
        Risk $ = Equity * risk_per_trade_pct
        Risk Per Unit = |entry_price - stop_loss|
        Size = Risk $ / Risk Per Unit, capped by max_exposure_pct
        """
        if self.trading_halted_today:
            return 0.0

        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0:
            return 0.0

        dollar_risk = self.equity * self.risk_per_trade_pct
        calculated_size = dollar_risk / sl_distance

        # Hard exposure cap (e.g. max 30% of total portfolio in one position)
        max_position_value = self.equity * self.max_exposure_pct
        max_allowed_size = max_position_value / entry_price

        final_size = min(calculated_size, max_allowed_size)

        # Ensure cash is sufficient (no leverage assumption)
        required_capital = final_size * entry_price
        if required_capital > self.cash:
            final_size = self.cash / entry_price

        return final_size

    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        size: float,
        entry_time: pd.Timestamp,
        stop_loss: float,
        take_profit: float,
        fee_rate: float,
        reason: str = ""
    ) -> bool:
        if self.position is not None:
            return False  # Already in position

        if size <= 0:
            return False

        cost_basis = size * entry_price
        fee = cost_basis * fee_rate
        total_cost = cost_basis + fee

        if total_cost > self.cash:
            return False

        self.cash -= total_cost
        self.position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            size=size,
            entry_time=entry_time,
            stop_loss=stop_loss,
            take_profit=take_profit,
            cost_basis=cost_basis,
            fees_paid=fee,
            reason=reason
        )
        return True

    def update_trailing_stop(self, new_stop: float) -> bool:
        """
        Ratchets trailing stop higher for LONG (or lower for SHORT).
        Never loosens/relaxes risk downward.
        """
        if self.position is None:
            return False

        if self.position.side == "LONG":
            if new_stop > self.position.stop_loss:
                self.position.stop_loss = new_stop
                self.position.trailing_stop = new_stop
                return True
        elif self.position.side == "SHORT":
            if new_stop < self.position.stop_loss:
                self.position.stop_loss = new_stop
                self.position.trailing_stop = new_stop
                return True
        return False

    def close_position(
        self,
        exit_price: float,
        exit_time: pd.Timestamp,
        fee_rate: float,
        exit_reason: str
    ) -> Optional[TradeRecord]:
        if self.position is None:
            return None

        pos = self.position
        exit_value = pos.size * exit_price
        exit_fee = exit_value * fee_rate

        if pos.side == "LONG":
            gross_pnl = exit_value - pos.cost_basis
        else:
            gross_pnl = pos.cost_basis - exit_value

        total_fees = pos.fees_paid + exit_fee
        net_pnl = gross_pnl - total_fees
        pnl_pct = net_pnl / pos.cost_basis if pos.cost_basis > 0 else 0.0

        self.cash += (exit_value - exit_fee)
        self.equity = self.cash

        record = TradeRecord(
            symbol=pos.symbol,
            side=pos.side,
            entry_time=pos.entry_time,
            exit_time=exit_time,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            size=pos.size,
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            fees=total_fees,
            exit_reason=exit_reason
        )

        self.trades.append(record)
        self.position = None
        return record

    def mark_to_market(self, current_price: float, current_time: pd.Timestamp):
        """Updates portfolio valuation on each candle bar."""
        if self.position is not None:
            unrealized = (
                (current_price - self.position.entry_price) * self.position.size
                if self.position.side == "LONG"
                else (self.position.entry_price - current_price) * self.position.size
            )
            self.equity = self.cash + (self.position.size * current_price)
        else:
            self.equity = self.cash

        self.update_daily_circuit_breaker(current_time)

        self.equity_curve.append({
            "timestamp": current_time,
            "equity": self.equity,
            "cash": self.cash,
            "in_position": self.position is not None
        })
