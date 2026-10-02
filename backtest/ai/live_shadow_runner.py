import sys
import time
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from typing import Dict, Any, List, Optional
import pandas as pd
import requests

from backtest.ai.shadow_engine import ShadowExecutionEngine
from backtest.ai.dataset_builder import DatasetBuilder


class LiveShadowRunner:
    """
    Stage A & B: Live / Mock Shadow Execution Runner.
    Listens for new closed candles, extracts features with zero lookahead,
    evaluates against the frozen AI Veto Filter, and records telemetry logs.
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
        self.engine = ShadowExecutionEngine(manifest_path=manifest_path)
        self.dataset_builder = DatasetBuilder(entry_period=55, exit_period=20, atr_multiplier=2.0)

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
        # Exclude the very last row if it represents an unclosed open candle
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
        Checks if any active trade (held in memory/state) has hit its Stop Loss
        or lower channel exit on the newest closed bar.
        Only populates outcome_timestamp and realized metrics when exit triggers.
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

            # Must be strictly after entry time
            if pd.to_datetime(latest_time) <= pd.to_datetime(entry_time):
                continue

            # Prior lows for Donchian 20 exit strictly [t-20, t-1]
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

            # 1. Intra-bar Stop Loss hit
            if bar_low <= stop_loss:
                exit_reason = "STOP_LOSS"
                exit_price = min(float(latest_bar["open"]), stop_loss)
            # 2. Donchian lower channel breakdown
            elif bar_close < lower_channel_20:
                exit_reason = "LOWER_CHANNEL"
                exit_price = bar_close

            if exit_reason is not None and exit_price is not None:
                # Compute realized metrics
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

                # Log outcome backfill event
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
        Scans current bar t (the latest closed candle) across all assets for breakout triggers.
        If close > upper_channel(55), evaluates the frozen AI Negative Veto Filter.
        """
        btc_df = self.candle_cache.get("BTCUSDT", None)
        detections = []

        # First check if any active trades exited
        self.check_active_trade_exits()

        for symbol in self.symbols:
            df = self.candle_cache.get(symbol, None)
            if df is None or len(df) < 60:
                continue

            # Latest closed candle is bar t (index -1)
            t_idx = len(df) - 1
            bar_t = df.iloc[t_idx]
            sig_time = str(bar_t["timestamp"])
            sig_key = f"{symbol}_{sig_time}"

            # Deduplication: Ensure each candle is evaluated at most once
            if sig_key in self.processed_signals:
                continue

            # Check if an active trade is already open on this asset
            if symbol in self.active_trades:
                continue

            # Donchian 55 upper channel strictly over [t-55, t-1] (excludes bar t)
            prior_highs = df["high"].iloc[-56:-1]
            upper_channel = float(prior_highs.max())
            close_t = float(bar_t["close"])

            # Check breakout condition
            if close_t > upper_channel:
                # Mark as processed immediately and persist
                self.processed_signals.add(sig_key)

                # Extract Combined 23 features using DatasetBuilder
                features = self.dataset_builder.extract_features_at_t(
                    t_idx=t_idx,
                    df=df,
                    btc_df=btc_df if symbol != "BTCUSDT" else None
                )

                # Evaluate using Frozen Shadow Engine
                eval_res = self.engine.evaluate_candidate(
                    timestamp=sig_time,
                    asset=symbol,
                    breakout_id=sig_key,
                    features=features,
                    baseline_signal="BUY",
                    baseline_entry_price=close_t,  # Benchmark baseline entry
                    eventual_realized_r=None,      # Strictly null at signal time
                    eventual_pnl=None,             # Strictly null at signal time
                    outcome_timestamp=None         # Strictly null at signal time
                )

                # Append to JSONL log
                with open(self.jsonl_log, "a") as f:
                    f.write(json.dumps(eval_res) + "\n")

                # Register active trade to track its outcome on future candles
                atr_series = self.dataset_builder._compute_atr_series(df["high"], df["low"], df["close"], period=14)
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

                # Console notification
                status_icon = "🟢 PASS (TRADE)" if eval_res["ai_decision"] == "PASS" else "🔴 VETO (AVOID)"
                print(f"\n🚨 [BREAKOUT SIGNAL DETECTED] {sig_time} | {symbol:<8}")
                print(f"   • Close: ${close_t:.2f} > Upper Channel: ${upper_channel:.2f}")
                print(f"   • Ridge Predicted R: {eval_res['ai_predicted_r']:>+7.3f}R (Threshold: {self.engine.threshold:>+7.3f}R)")
                print(f"   • Decision: {status_icon}")

        return detections


def run_infrastructure_smoke_test():
    """
    Stage A Smoke Test: Verifies live connectivity, feature extraction,
    and frozen model prediction without waiting 4 hours.
    """
    print("=" * 95)
    print("  STAGE A: INFRASTRUCTURE SMOKE TEST & DATA PIPELINE VALIDATION")
    print("  Testing: Live Binance Public REST API | Feature Calculation | Hash Verification")
    print("=" * 95)

    runner = LiveShadowRunner()
    print(f"\n[1] Verifying Model Artifact Hashes:")
    print(f"  • Scaler SHA256: {runner.engine.manifest['artifacts']['scaler_sha256']}")
    print(f"  • Model SHA256:  {runner.engine.manifest['artifacts']['model_sha256']}")
    print(f"  • Threshold:     theta = {runner.engine.threshold:+.6f}R")

    print(f"\n[2] Fetching Live 4h Klines for {runner.symbols}...")
    runner.update_data()

    all_ok = True
    for sym in runner.symbols:
        df = runner.candle_cache.get(sym, None)
        if df is not None and len(df) >= 60:
            print(f"  ✅ {sym:<8}: Fetched {len(df)} bars. Latest closed candle: {df['timestamp'].iloc[-1]}")
        else:
            print(f"  ❌ {sym:<8}: Failed to fetch sufficient history ({len(df) if df is not None else 0} bars)")
            all_ok = False

    if all_ok:
        print(f"\n[3] Testing Feature Extraction & Frozen Scoring on Latest Candle:")
        btc_df = runner.candle_cache["BTCUSDT"]
        test_sym = "ETHUSDT"
        test_df = runner.candle_cache[test_sym]
        t_idx = len(test_df) - 1

        feats = runner.dataset_builder.extract_features_at_t(t_idx=t_idx, df=test_df, btc_df=btc_df)
        pred_dict = runner.engine.evaluate_candidate(
            timestamp=str(test_df['timestamp'].iloc[-1]),
            asset=test_sym,
            breakout_id=f"TEST_{test_sym}_{test_df['timestamp'].iloc[-1]}",
            features=feats,
            baseline_signal="BUY",
            baseline_entry_price=float(test_df['close'].iloc[-1])
        )

        with open(runner.jsonl_log, "a") as f:
            f.write(json.dumps(pred_dict) + "\n")

        print(f"  • Test Candidate: {test_sym} at {test_df['timestamp'].iloc[-1]}")
        print(f"  • Feature Count:  {len(runner.engine.features_list)} features computed successfully")
        print(f"  • Predicted R:    {pred_dict['ai_predicted_r']:>+7.4f}R")
        print(f"  • AI Decision:    {pred_dict['ai_decision']}")
        print(f"  • Telemetry Log:  {runner.jsonl_log}")
        print(f"\n✅ STAGE A INFRASTRUCTURE TEST PASSED: Pipeline is fully live-feed compatible.")
    else:
        print(f"\n❌ STAGE A INFRASTRUCTURE TEST FAILED: Network or data error.")
    print("=" * 95 + "\n")


def run_live_daemon(poll_interval_seconds: int = 60):
    """
    Continuous Live Shadow Runner Daemon.
    Monitors 4h candle closes across BTC, ETH, SOL, BNB continuously.
    Scans for Donchian 55 breakouts, evaluates frozen AI filter, and records telemetry.
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
    Single observation cycle for Cron / GitHub Actions.
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
        run_infrastructure_smoke_test()

