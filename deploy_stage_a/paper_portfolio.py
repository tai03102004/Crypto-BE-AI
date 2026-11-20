import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd


class DualPaperPortfolio:
    """
    Stage C: Dual Paper Portfolio Engine.
    Simultaneously tracks two independent paper portfolios on the exact same live signal feed:
      1. Portfolio Baseline: Takes EVERY Donchian 55 breakout (no AI filter).
      2. Portfolio AI-Filtered: Only executes trades where Ridge Predicted R >= +0.356025R.

    Calculates real-time NAV, cash balance, unrealized PnL, realized PnL,
    max drawdown, avoided losses, and net economic edge (alpha).
    """

    def __init__(
        self,
        initial_capital: float = 10000.0,
        risk_per_trade_pct: float = 0.01,
        state_file: Optional[Path] = None
    ):
        self.initial_capital = initial_capital
        self.risk_per_trade_pct = risk_per_trade_pct

        if state_file is None:
            state_file = Path(__file__).parent / "logs" / "paper_portfolio_state.json"
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Baseline Portfolio State
        self.baseline = {
            "initial_capital": initial_capital,
            "cash": initial_capital,
            "equity": initial_capital,
            "realized_pnl": 0.0,
            "peak_equity": initial_capital,
            "max_drawdown_pct": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "active_positions": {},   # symbol -> {entry_time, entry_price, size, stop_loss, risk_usd}
            "trade_history": []
        }

        # AI-Filtered Portfolio State
        self.ai_filtered = {
            "initial_capital": initial_capital,
            "cash": initial_capital,
            "equity": initial_capital,
            "realized_pnl": 0.0,
            "peak_equity": initial_capital,
            "max_drawdown_pct": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "active_positions": {},   # symbol -> {entry_time, entry_price, size, stop_loss, risk_usd}
            "trade_history": []
        }

        # Comparative Analytics
        self.comparative_metrics = {
            "avoided_losses_usd": 0.0,      # Money saved by vetoing losers
            "opportunity_costs_usd": 0.0,   # Profits missed by vetoing winners
            "net_ai_edge_usd": 0.0,         # AI Portfolio Equity - Baseline Equity
            "equity_history": []            # List of {timestamp, baseline_equity, ai_equity}
        }

        self._load_state()

    def _load_state(self):
        """Loads state from disk if exists."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    self.baseline = data.get("baseline", self.baseline)
                    self.ai_filtered = data.get("ai_filtered", self.ai_filtered)
                    self.comparative_metrics = data.get("comparative_metrics", self.comparative_metrics)
            except Exception as e:
                print(f"⚠️ [Paper Portfolio] Load state warning: {e}")

    def save_state(self):
        """Persists state to disk."""
        data = {
            "updated_at": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M:%S UTC"),
            "baseline": self.baseline,
            "ai_filtered": self.ai_filtered,
            "comparative_metrics": self.comparative_metrics
        }
        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)

    def on_breakout_signal(
        self,
        symbol: str,
        timestamp: str,
        entry_price: float,
        atr: float,
        ai_decision: str,
        predicted_r: float,
        side: str = "LONG"
    ):
        """
        Processes a newly detected Donchian 55 trigger across both portfolios (supports LONG & SHORT).
        """
        dollar_risk_unit = 2.0 * atr if atr > 0 else entry_price * 0.03
        sl_price = (entry_price - dollar_risk_unit) if side == "LONG" else (entry_price + dollar_risk_unit)

        # 1. Process Baseline Portfolio (Always takes trade)
        if symbol not in self.baseline["active_positions"]:
            risk_budget = self.baseline["equity"] * self.risk_per_trade_pct
            size = risk_budget / dollar_risk_unit if dollar_risk_unit > 0 else 0.0
            cost = size * entry_price

            if self.baseline["cash"] >= cost * 0.2:  # basic margin check
                self.baseline["cash"] -= cost
                self.baseline["active_positions"][symbol] = {
                    "symbol": symbol,
                    "side": side,
                    "entry_time": timestamp,
                    "entry_price": entry_price,
                    "size": size,
                    "stop_loss": sl_price,
                    "dollar_risk": risk_budget,
                    "ai_decision": ai_decision,
                    "predicted_r": predicted_r
                }

        # 2. Process AI-Filtered Portfolio (Only takes trade if PASS)
        if ai_decision == "PASS":
            if symbol not in self.ai_filtered["active_positions"]:
                risk_budget = self.ai_filtered["equity"] * self.risk_per_trade_pct
                size = risk_budget / dollar_risk_unit if dollar_risk_unit > 0 else 0.0
                cost = size * entry_price

                if self.ai_filtered["cash"] >= cost * 0.2:
                    self.ai_filtered["cash"] -= cost
                    self.ai_filtered["active_positions"][symbol] = {
                        "symbol": symbol,
                        "side": side,
                        "entry_time": timestamp,
                        "entry_price": entry_price,
                        "size": size,
                        "stop_loss": sl_price,
                        "dollar_risk": risk_budget,
                        "ai_decision": ai_decision,
                        "predicted_r": predicted_r
                    }

        self.save_state()

    def on_position_exit(
        self,
        symbol: str,
        exit_time: str,
        exit_price: float,
        exit_reason: str
    ):
        """
        Handles trade exit (Stop loss or channel trailing stop) across portfolios.
        """
        # 1. Exit from Baseline
        if symbol in self.baseline["active_positions"]:
            pos = self.baseline["active_positions"].pop(symbol)
            is_short = (pos.get("side") == "SHORT")
            pnl = (pos["entry_price"] - exit_price) * pos["size"] if is_short else (exit_price - pos["entry_price"]) * pos["size"]
            self.baseline["cash"] += (pos["size"] * pos["entry_price"]) + pnl
            self.baseline["realized_pnl"] += pnl
            self.baseline["total_trades"] += 1
            if pnl > 0:
                self.baseline["winning_trades"] += 1
            else:
                self.baseline["losing_trades"] += 1

            trade_record = {
                **pos,
                "exit_time": exit_time,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "realized_pnl": pnl,
                "realized_r": pnl / pos["dollar_risk"] if pos["dollar_risk"] > 0 else 0.0
            }
            self.baseline["trade_history"].append(trade_record)

            # Check if this was vetoed by AI to compute avoided loss / opportunity cost
            if pos["ai_decision"] == "VETO":
                if pnl < 0:
                    self.comparative_metrics["avoided_losses_usd"] += abs(pnl)
                else:
                    self.comparative_metrics["opportunity_costs_usd"] += pnl

        # 2. Exit from AI-Filtered
        if symbol in self.ai_filtered["active_positions"]:
            pos = self.ai_filtered["active_positions"].pop(symbol)
            is_short = (pos.get("side") == "SHORT")
            pnl = (pos["entry_price"] - exit_price) * pos["size"] if is_short else (exit_price - pos["entry_price"]) * pos["size"]
            self.ai_filtered["cash"] += (pos["size"] * pos["entry_price"]) + pnl
            self.ai_filtered["realized_pnl"] += pnl
            self.ai_filtered["total_trades"] += 1
            if pnl > 0:
                self.ai_filtered["winning_trades"] += 1
            else:
                self.ai_filtered["losing_trades"] += 1

            trade_record = {
                **pos,
                "exit_time": exit_time,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "realized_pnl": pnl,
                "realized_r": pnl / pos["dollar_risk"] if pos["dollar_risk"] > 0 else 0.0
            }
            self.ai_filtered["trade_history"].append(trade_record)

        self.update_mark_to_market({})
        self.save_state()

    def update_mark_to_market(self, current_prices: Dict[str, float]):
        """
        Updates current equity, unrealized PnL, peak equity, and drawdown for both LONG & SHORT.
        """
        # Baseline Equity
        baseline_positions_val = 0.0
        for sym, pos in self.baseline["active_positions"].items():
            curr_p = current_prices.get(sym, pos["entry_price"])
            cost = pos["size"] * pos["entry_price"]
            is_short = (pos.get("side") == "SHORT")
            unrealized = (pos["entry_price"] - curr_p) * pos["size"] if is_short else (curr_p - pos["entry_price"]) * pos["size"]
            baseline_positions_val += cost + unrealized

        self.baseline["equity"] = self.baseline["cash"] + baseline_positions_val
        if self.baseline["equity"] > self.baseline["peak_equity"]:
            self.baseline["peak_equity"] = self.baseline["equity"]
        dd_base = (self.baseline["peak_equity"] - self.baseline["equity"]) / self.baseline["peak_equity"] * 100
        self.baseline["max_drawdown_pct"] = max(self.baseline["max_drawdown_pct"], dd_base)

        # AI-Filtered Equity
        ai_positions_val = 0.0
        for sym, pos in self.ai_filtered["active_positions"].items():
            curr_p = current_prices.get(sym, pos["entry_price"])
            cost = pos["size"] * pos["entry_price"]
            is_short = (pos.get("side") == "SHORT")
            unrealized = (pos["entry_price"] - curr_p) * pos["size"] if is_short else (curr_p - pos["entry_price"]) * pos["size"]
            ai_positions_val += cost + unrealized

        self.ai_filtered["equity"] = self.ai_filtered["cash"] + ai_positions_val
        if self.ai_filtered["equity"] > self.ai_filtered["peak_equity"]:
            self.ai_filtered["peak_equity"] = self.ai_filtered["equity"]
        dd_ai = (self.ai_filtered["peak_equity"] - self.ai_filtered["equity"]) / self.ai_filtered["peak_equity"] * 100
        self.ai_filtered["max_drawdown_pct"] = max(self.ai_filtered["max_drawdown_pct"], dd_ai)

        # Net Edge
        self.comparative_metrics["net_ai_edge_usd"] = self.ai_filtered["equity"] - self.baseline["equity"]

        now_str = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M:%S")
        self.comparative_metrics["equity_history"].append({
            "timestamp": now_str,
            "baseline_equity": round(self.baseline["equity"], 2),
            "ai_filtered_equity": round(self.ai_filtered["equity"], 2)
        })
        # Keep last 200 points
        if len(self.comparative_metrics["equity_history"]) > 200:
            self.comparative_metrics["equity_history"] = self.comparative_metrics["equity_history"][-200:]
