import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import requests

from shadow_engine import ShadowExecutionEngine
from feature_extractor import FeatureExtractor


class LiveShadowRunner:
    """
    Stage A: Live Shadow Execution Runner (Standalone VPS Deployment Edition).
    Listens for new 4h closed candles, extracts 23 features with zero lookahead,
    evaluates against the frozen AI Veto Filter, and records audit telemetry logs.
    """

    BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

    def __init__(
        self,
        symbols: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
        interval: str = "4h",
        manifest_path: Optional[Path] = None,
        log_dir: Optional[Path] = None
    ):
        self.symbols = symbols
        self.interval = interval
        if manifest_path is None:
            manifest_path = Path(__file__).parent / "models" / "model_manifest.json"

        self.engine = ShadowExecutionEngine(manifest_path=manifest_path)
        self.feature_extractor = FeatureExtractor(entry_period=55, exit_period=20, atr_multiplier=2.0)

        if log_dir is None:
            log_dir = Path(__file__).parent / "logs"
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.jsonl_log = self.log_dir / "live_shadow_telemetry.jsonl"
        self.incident_log = self.log_dir / "infrastructure_incidents.jsonl"
        self.state_file = self.log_dir / "live_runner_state.json"
        self.processed_signals: set = set()
        self.active_trades: Dict[str, Dict[str, Any]] = {}

        self._load_state()

        # Cache of recent candles: {symbol: DataFrame}
        self.candle_cache: Dict[str, pd.DataFrame] = {}

    def log_incident(
        self,
        incident_type: str,
        description: str,
        signal_id: Optional[str] = None,
        affects_validity: bool = False,
        resolution: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Formally logs an infrastructure or data lineage incident.
        Maintains an unalterable audit trail for Stage A evaluation.
        """
        from datetime import datetime, timezone
        incident_entry = {
            "incident_id": f"INC_{int(datetime.now(timezone.utc).timestamp()*1000)}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "incident_type": incident_type,
            "signal_id": signal_id,
            "affects_validity": affects_validity,
            "description": description,
            "resolution": resolution
        }
        with open(self.incident_log, "a") as f:
            f.write(json.dumps(incident_entry) + "\n")
        print(f"⚠️ [INCIDENT LOGGED] {incident_type} (Affects Validity: {affects_validity}): {description}")
        return incident_entry

    def _load_state(self):
        """Loads persistent state to prevent duplicate executions across restarts."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    self.processed_signals = set(state.get("processed_signals", []))
                    self.active_trades = state.get("active_trades", {})
            except Exception as e:
                print(f"⚠️ [State Warning] Could not load state: {e}")

    def _save_state(self):
        """Saves persistent state to disk."""
        state = {
            "processed_signals": list(self.processed_signals),
            "active_trades": self.active_trades
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def fetch_recent_klines(self, symbol: str, limit: int = 150) -> pd.DataFrame:
        """
        Fetches the most recent closed candles from Binance Public REST API.
        Excludes the active unclosed candle (last row).
        """
        params = {"symbol": symbol, "interval": self.interval, "limit": limit}
        try:
            resp = requests.get(self.BINANCE_KLINES_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"⚠️ [API Warning] Failed to fetch {symbol} klines: {e}")
            return pd.DataFrame()

        rows = []
        for kline in data[:-1]:
            rows.append({
                "timestamp": pd.to_datetime(kline[0], unit="ms"),
                "open": float(kline[1]),
                "high": float(kline[2]),
                "low": float(kline[3]),
                "close": float(kline[4]),
                "volume": float(kline[5])
            })

        df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
        return df

    def update_data(self):
        """Fetches recent candles for all tracked assets."""
        for sym in self.symbols:
            df = self.fetch_recent_klines(sym, limit=120)
            if not df.empty:
                self.candle_cache[sym] = df

    def check_active_trade_exits(self) -> List[Dict[str, Any]]:
        """
        Checks if any active trade has hit its Stop Loss or lower channel exit.
        Populates outcome_timestamp and realized metrics only upon exit.
        """
        exited_trades = []
        symbols_to_remove = []

        for symbol, trade in self.active_trades.items():
            df = self.candle_cache.get(symbol, None)
            if df is None or df.empty:
                continue

            latest_bar = df.iloc[-1]
            latest_time = str(latest_bar["timestamp"])
            entry_time = trade["entry_time"]

            if pd.to_datetime(latest_time) <= pd.to_datetime(entry_time):
                continue

            if len(df) >= 21:
                prior_lows = df["low"].iloc[-21:-1]
            else:
                prior_lows = df["low"].iloc[:-1]

            lower_channel_20 = float(prior_lows.min()) if not prior_lows.empty else float(latest_bar["low"])

            bar_low = float(latest_bar["low"])
            bar_close = float(latest_bar["close"])
            stop_loss = float(trade["stop_loss"])

            exit_reason = None
            exit_price = None

            if bar_low <= stop_loss:
                exit_reason = "STOP_LOSS"
                exit_price = min(float(latest_bar["open"]), stop_loss)
            elif bar_close < lower_channel_20:
                exit_reason = "LOWER_CHANNEL"
                exit_price = bar_close

            if exit_reason is not None and exit_price is not None:
                initial_risk = trade["initial_dollar_risk"]
                size = trade["size"]
                entry_price = trade["entry_price"]
                pnl = (exit_price - entry_price) * size
                realized_r = pnl / initial_risk if initial_risk > 0 else 0.0

                outcome_record = {
                    "event_type": "TRADE_OUTCOME",
                    "breakout_id": trade["breakout_id"],
                    "asset": symbol,
                    "entry_time": entry_time,
                    "outcome_timestamp": latest_time,
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "ai_decision": trade["ai_decision"],
                    "eventual_realized_r": realized_r,
                    "baseline_counterfactual_pnl": pnl,
                    "shadow_realized_pnl": 0.0 if trade["ai_decision"] == "VETO" else pnl,
                    "avoided_loss": -pnl if (trade["ai_decision"] == "VETO" and pnl < 0) else 0.0,
                    "opportunity_cost": pnl if (trade["ai_decision"] == "VETO" and pnl > 0) else 0.0
                }

                with open(self.jsonl_log, "a") as f:
                    f.write(json.dumps(outcome_record) + "\n")

                exited_trades.append(outcome_record)
                symbols_to_remove.append(symbol)

                print(f"🔔 [TRADE OUTCOME RECORDED] {latest_time} | {symbol} exited via {exit_reason} at ${exit_price:.2f} (Realized R: {realized_r:+.2f}R)")

        for sym in symbols_to_remove:
            del self.active_trades[sym]

        if symbols_to_remove:
            self._save_state()

        return exited_trades

    def scan_for_breakouts(self) -> List[Dict[str, Any]]:
        """
        Scans current bar t across all assets for Donchian 55 breakout triggers.
        """
        btc_df = self.candle_cache.get("BTCUSDT", None)
        detections = []

        self.check_active_trade_exits()

        for symbol in self.symbols:
            df = self.candle_cache.get(symbol, None)
            if df is None or len(df) < 60:
                continue

            t_idx = len(df) - 1
            bar_t = df.iloc[t_idx]
            sig_time = str(bar_t["timestamp"])
            sig_key = f"{symbol}_{sig_time}"

            if sig_key in self.processed_signals:
                continue

            if symbol in self.active_trades:
                continue

            prior_highs = df["high"].iloc[-56:-1]
            upper_channel = float(prior_highs.max())
            close_t = float(bar_t["close"])

            if close_t > upper_channel:
                self.processed_signals.add(sig_key)

                features = self.feature_extractor.extract_features_at_t(
                    t_idx=t_idx,
                    df=df,
                    btc_df=btc_df if symbol != "BTCUSDT" else None
                )

                eval_res = self.engine.evaluate_candidate(
                    timestamp=sig_time,
                    asset=symbol,
                    breakout_id=sig_key,
                    features=features,
                    baseline_signal="BUY",
                    baseline_entry_price=close_t,
                    eventual_realized_r=None,
                    eventual_pnl=None,
                    outcome_timestamp=None
                )

                with open(self.jsonl_log, "a") as f:
                    f.write(json.dumps(eval_res) + "\n")

                atr_series = self.feature_extractor._compute_atr_series(df["high"], df["low"], df["close"], period=14)
                atr_t = float(atr_series.iloc[-1])
                dollar_risk = 2.0 * atr_t
                size = (1000.0 * 0.01) / dollar_risk if dollar_risk > 0 else 0.0

                self.active_trades[symbol] = {
                    "breakout_id": sig_key,
                    "asset": symbol,
                    "entry_time": sig_time,
                    "entry_price": close_t,
                    "stop_loss": close_t - dollar_risk,
                    "initial_dollar_risk": size * dollar_risk,
                    "size": size,
                    "ai_decision": eval_res["ai_decision"]
                }
                self._save_state()

                detections.append(eval_res)

                status_icon = "🟢 PASS (TRADE)" if eval_res["ai_decision"] == "PASS" else "🔴 VETO (AVOID)"
                print(f"\n🚨 [BREAKOUT SIGNAL DETECTED] {sig_time} | {symbol:<8}")
                print(f"   • Close: ${close_t:.2f} > Upper Channel: ${upper_channel:.2f}")
                print(f"   • Ridge Predicted R: {eval_res['ai_predicted_r']:>+7.3f}R (Threshold: {self.engine.threshold:>+7.3f}R)")
                print(f"   • Decision: {status_icon}")

        return detections


def run_live_daemon(poll_interval_seconds: int = 60):
    """
    Continuous Live Shadow Runner Daemon.
    Monitors 4h candle closes across BTC, ETH, SOL, BNB continuously.
    """
    print("=" * 95)
    print("  LIVE SHADOW RUNNER DAEMON STARTED: STAGE A OBSERVATION MODE")
    print(f"  Assets: BTCUSDT | ETHUSDT | SOLUSDT | BNBUSDT | Timeframe: 4h")
    print(f"  Polling Interval: Every {poll_interval_seconds}s for new closed candles")
    print("  Governance: Zero Model Interventions | Frozen Threshold = +0.356025R")
    print("=" * 95)

    runner = LiveShadowRunner()
    last_candle_times: Dict[str, str] = {}

    while True:
        try:
            runner.update_data()
            new_candle_detected = False

            for sym in runner.symbols:
                df = runner.candle_cache.get(sym, None)
                if df is not None and not df.empty:
                    latest_ts = str(df["timestamp"].iloc[-1])
                    if last_candle_times.get(sym) != latest_ts:
                        new_candle_detected = True
                        last_candle_times[sym] = latest_ts

            if new_candle_detected:
                print(f"\n⏰ [{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}] New 4h closed candle detected. Scanning markets...")
                detections = runner.scan_for_breakouts()
                if not detections:
                    print("   ℹ️ No new breakouts triggered on this candle. Status: FLAT / WAITING.")

            time.sleep(poll_interval_seconds)

        except KeyboardInterrupt:
            print("\n🛑 Live Shadow Runner Daemon stopped by user.")
            break
        except Exception as e:
            runner.log_incident(
                incident_type="DAEMON_LOOP_ERROR",
                description=str(e),
                affects_validity=False,
                resolution="Retrying on next iteration"
            )
            time.sleep(poll_interval_seconds)


def run_single_iteration():
    """
    Single observation cycle for Cron / GitHub Actions:
    1. Fetches latest closed 4h candles from Binance REST.
    2. Checks & updates exits for active positions.
    3. Scans for new 4h breakouts & scores via frozen Ridge filter.
    4. Persists state and logs to telemetry.
    """
    print("=" * 95)
    print("  STAGE A LIVE SHADOW RUNNER: SINGLE CYCLE (GITHUB ACTIONS / CRON)")
    print(f"  Timestamp: {pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("  Governance: Zero Interventions | Model & Scaler Frozen | Threshold = +0.356025R")
    print("=" * 95)

    runner = LiveShadowRunner()
    runner.update_data()

    print("\n[1] Closed Candle Scan:")
    for sym in runner.symbols:
        df = runner.candle_cache.get(sym, None)
        if df is not None and not df.empty:
            print(f"  • {sym:<8}: Latest closed candle {df['timestamp'].iloc[-1]} (Close: ${df['close'].iloc[-1]:.2f})")
        else:
            print(f"  • {sym:<8}: ⚠️ Unable to fetch candle")

    print("\n[2] Breakout Detection & Position Tracking:")
    detections = runner.scan_for_breakouts()
    if not detections:
        print("  ℹ️ No new breakouts triggered on this candle. Status: FLAT / WAITING.")
    else:
        print(f"  🚨 Detected {len(detections)} breakout signals!")

    print("\n[3] Cycle Complete. State & Telemetry persisted cleanly.")
    return detections


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_single_iteration()
    elif len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        run_live_daemon(poll_interval_seconds=60)
    else:
        # If no arguments provided, default to --once for safety in CLI/cron
        run_single_iteration()

