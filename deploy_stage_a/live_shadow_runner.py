import sys
import os
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import requests

from shadow_engine import ShadowExecutionEngine
from feature_extractor import FeatureExtractor
from binance_executor import BinanceExecutor
from paper_portfolio import DualPaperPortfolio


def load_env_file():
    """Simple robust .env loader without third-party dependencies."""
    for env_path in [Path.cwd() / ".env", Path(__file__).parent / ".env", Path(__file__).parent.parent / ".env"]:
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and (k not in os.environ or (v and not os.environ[k])):
                            os.environ[k] = v


class LiveShadowRunner:
    """
    Stage A: Live Shadow Execution Runner (Standalone VPS Deployment Edition).
    Listens for new 4h closed candles, extracts 23 features with zero lookahead,
    evaluates against the frozen AI Veto Filter, and records audit telemetry logs.
    """

    BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

    def send_telegram_alert(self, message: str) -> bool:
        """Sends real-time HTML notification via Telegram Bot if credentials are configured."""
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            return False
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            res = requests.post(url, json=payload, timeout=10)
            return res.status_code == 200
        except Exception as e:
            print(f"⚠️ [Telegram Alert Warning] Could not send notification: {e}")
            return False


    def __init__(
        self,
        symbols: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
        interval: str = "4h",
        intervals: Optional[List[str]] = None,
        manifest_path: Optional[Path] = None,
        log_dir: Optional[Path] = None
    ):
        self.symbols = symbols
        self.interval = interval
        if intervals is not None:
            self.intervals = intervals
        elif interval != "4h":
            self.intervals = [interval]
        else:
            # Default to Multi-Timeframe: 15m, 1h, 4h
            self.intervals = ["15m", "1h", "4h"]
        if manifest_path is None:
            manifest_path = Path(__file__).parent / "models" / "model_manifest.json"

        self.engine = ShadowExecutionEngine(manifest_path=manifest_path)
        self.feature_extractor = FeatureExtractor(entry_period=55, exit_period=20, atr_multiplier=2.0)

        load_env_file()
        binance_mode = os.environ.get("BINANCE_MODE", "DRY_RUN")
        api_key = os.environ.get("BINANCE_API_KEY", "")
        api_secret = os.environ.get("BINANCE_API_SECRET", "")
        risk_pct = float(os.environ.get("RISK_PER_TRADE_PCT", "0.01"))
        max_order = float(os.environ.get("MAX_ORDER_USDT", "500.0"))

        self.executor = BinanceExecutor(
            api_key=api_key,
            api_secret=api_secret,
            mode=binance_mode,
            risk_per_trade_pct=risk_pct,
            max_order_usdt=max_order
        )

        if log_dir is None:
            log_dir = Path(__file__).parent / "logs"
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.jsonl_log = self.log_dir / "live_shadow_telemetry.jsonl"
        self.incident_log = self.log_dir / "infrastructure_incidents.jsonl"
        self.state_file = self.log_dir / "live_runner_state.json"
        self.processed_signals: set = set()
        self.active_trades: Dict[str, Dict[str, Any]] = {}

        self.paper_portfolio = DualPaperPortfolio(
            initial_capital=10000.0,
            risk_per_trade_pct=risk_pct,
            state_file=self.log_dir / "paper_portfolio_state.json"
        )

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

    def fetch_recent_klines(self, symbol: str, interval: Optional[str] = None, limit: int = 150) -> pd.DataFrame:
        """
        Fetches the most recent closed candles from Binance Public REST API.
        Excludes the active unclosed candle (last row).
        """
        iv = interval if interval is not None else self.interval
        params = {"symbol": symbol, "interval": iv, "limit": limit}
        try:
            resp = requests.get(self.BINANCE_KLINES_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"⚠️ [API Warning] Failed to fetch {symbol} ({iv}) klines: {e}")
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
        """Fetches recent candles for all tracked assets across all active intervals."""
        curr_prices = {}
        for iv in self.intervals:
            for sym in self.symbols:
                df = self.fetch_recent_klines(sym, interval=iv, limit=120)
                if not df.empty:
                    self.candle_cache[f"{sym}_{iv}"] = df
                    if sym not in self.candle_cache or iv == self.interval:
                        self.candle_cache[sym] = df
                    if sym not in curr_prices:
                        curr_prices[sym] = float(df['close'].iloc[-1])

        # Update mark-to-market valuations for Dual Paper Portfolio
        if curr_prices:
            self.paper_portfolio.update_mark_to_market(curr_prices)
            self.paper_portfolio.save_state()

    def check_active_trade_exits(self) -> List[Dict[str, Any]]:
        """
        Checks if any active trade has hit its Stop Loss or lower channel exit.
        Populates outcome_timestamp and realized metrics only upon exit.
        """
        exited_trades = []
        symbols_to_remove = []

        for trade_key, trade in list(self.active_trades.items()):
            symbol = trade.get("asset", trade_key.split("_")[0])
            tf = trade.get("timeframe", "4h")
            df = self.candle_cache.get(f"{symbol}_{tf}", self.candle_cache.get(symbol, None))
            if df is None or df.empty:
                continue

            latest_bar = df.iloc[-1]
            latest_time = str(latest_bar["timestamp"])
            entry_time = trade["entry_time"]

            if pd.to_datetime(latest_time, utc=True) <= pd.to_datetime(entry_time, utc=True):
                continue

            side = trade.get("side", "LONG")
            bar_low = float(latest_bar["low"])
            bar_high = float(latest_bar["high"])
            bar_close = float(latest_bar["close"])
            stop_loss = float(trade["stop_loss"])
            entry_p = float(trade["entry_price"])
            init_sl = float(trade.get("initial_stop_loss", trade["stop_loss"]))

            # Safeguard 3 (Option B): Breakeven Lock for 15M (move SL to entry when gain >= +1.0R)
            if tf == "15m" and not trade.get("breakeven_locked", False):
                if side == "LONG":
                    r_dist = entry_p - init_sl
                    if r_dist > 0 and bar_close >= entry_p + r_dist:
                        trade["stop_loss"] = entry_p
                        trade["breakeven_locked"] = True
                        stop_loss = entry_p
                        self._save_state()
                        be_msg = (
                            f"🛡️ <b>[BREAKEVEN LOCKED - 15M LONG]</b>\n\n"
                            f"• <b>Asset:</b> #{symbol} [15M LONG]\n"
                            f"• <b>Gain Reached:</b> <code>+1.0R</code> (Price: <code>${bar_close:,.2f}</code>)\n"
                            f"• <b>New Stop Loss:</b> <code>${entry_p:,.2f}</code> (Breakeven)\n"
                            f"<i>(Lệnh LONG 15M đã khóa hòa vốn thành công, loại bỏ rủi ro thua lỗ!)</i>"
                        )
                        self.send_telegram_alert(be_msg)
                        print(f"🛡️ [BREAKEVEN LOCKED] {symbol} [15M LONG]: Stop Loss moved to Entry ${entry_p:.2f}")
                else:  # SHORT
                    r_dist = init_sl - entry_p
                    if r_dist > 0 and bar_close <= entry_p - r_dist:
                        trade["stop_loss"] = entry_p
                        trade["breakeven_locked"] = True
                        stop_loss = entry_p
                        self._save_state()
                        be_msg = (
                            f"🛡️ <b>[BREAKEVEN LOCKED - 15M SHORT]</b>\n\n"
                            f"• <b>Asset:</b> #{symbol} [15M SHORT]\n"
                            f"• <b>Gain Reached:</b> <code>+1.0R</code> (Price: <code>${bar_close:,.2f}</code>)\n"
                            f"• <b>New Stop Loss:</b> <code>${entry_p:,.2f}</code> (Breakeven)\n"
                            f"<i>(Lệnh SHORT 15M đã khóa hòa vốn thành công, loại bỏ rủi ro thua lỗ!)</i>"
                        )
                        self.send_telegram_alert(be_msg)
                        print(f"🛡️ [BREAKEVEN LOCKED] {symbol} [15M SHORT]: Stop Loss moved to Entry ${entry_p:.2f}")

            exit_reason = None
            exit_price = None

            if side == "LONG":
                if len(df) >= 21:
                    prior_lows = df["low"].iloc[-21:-1]
                else:
                    prior_lows = df["low"].iloc[:-1]
                lower_channel_20 = float(prior_lows.min()) if not prior_lows.empty else float(latest_bar["low"])

                if bar_low <= stop_loss:
                    exit_reason = "STOP_LOSS"
                    exit_price = min(float(latest_bar["open"]), stop_loss)
                elif bar_close < lower_channel_20:
                    exit_reason = "LOWER_CHANNEL"
                    exit_price = bar_close
            else:  # SHORT
                if len(df) >= 21:
                    prior_highs = df["high"].iloc[-21:-1]
                else:
                    prior_highs = df["high"].iloc[:-1]
                upper_channel_20 = float(prior_highs.max()) if not prior_highs.empty else float(latest_bar["high"])

                if bar_high >= stop_loss:
                    exit_reason = "STOP_LOSS"
                    exit_price = max(float(latest_bar["open"]), stop_loss)
                elif bar_close > upper_channel_20:
                    exit_reason = "UPPER_CHANNEL"
                    exit_price = bar_close

            if exit_reason is not None and exit_price is not None:
                initial_risk = trade["initial_dollar_risk"]
                size = trade["size"]
                entry_price = trade["entry_price"]
                pnl = (exit_price - entry_price) * size if side == "LONG" else (entry_price - exit_price) * size
                realized_r = pnl / initial_risk if initial_risk > 0 else 0.0

                outcome_record = {
                    "event_type": "TRADE_OUTCOME",
                    "breakout_id": trade["breakout_id"],
                    "asset": symbol,
                    "side": side,
                    "timeframe": tf,
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

                if trade.get("ai_decision") == "PASS":
                    if side == "LONG":
                        exec_res = self.executor.place_market_sell(symbol, size)
                    else:
                        exec_res = self.executor.close_market_short(symbol, size)
                    outcome_record["sell_order_res"] = exec_res

                # Notify Dual Paper Portfolio
                self.paper_portfolio.on_position_exit(symbol, latest_time, exit_price, exit_reason)

                with open(self.jsonl_log, "a") as f:
                    f.write(json.dumps(outcome_record) + "\n")

                exited_trades.append(outcome_record)
                symbols_to_remove.append(trade_key)

                print(f"🔔 [TRADE OUTCOME RECORDED] {latest_time} | {symbol} [{tf.upper()}] exited via {exit_reason} at ${exit_price:.2f} (Realized R: {realized_r:+.2f}R)")

                outcome_msg = (
                    f"🔔 <b>[STAGE A TRADE OUTCOME RECORDED]</b>\n\n"
                    f"• <b>Asset:</b> #{symbol} (<code>{tf.upper()}</code>)\n"
                    f"• <b>Exit Time:</b> <code>{latest_time}</code>\n"
                    f"• <b>Reason:</b> <code>{exit_reason}</code> at <code>${exit_price:,.2f}</code>\n"
                    f"• <b>Realized R:</b> <code>{realized_r:+.2f}R</code>\n"
                    f"• <b>Baseline PnL:</b> <code>${pnl:+.2f}</code>\n"
                    f"• <b>Original AI Decision:</b> <b>{trade['ai_decision']}</b>\n"
                )
                if trade["ai_decision"] == "VETO":
                    if pnl < 0:
                        outcome_msg += f"• <b>Avoided Loss:</b> <code>${-pnl:.2f}</code> (Veto Successful!)\n"
                    else:
                        outcome_msg += f"• <b>Opportunity Cost:</b> <code>${pnl:.2f}</code>\n"
                self.send_telegram_alert(outcome_msg)

        for sym in symbols_to_remove:
            if sym in self.active_trades:
                del self.active_trades[sym]

        if symbols_to_remove:
            self._save_state()

        return exited_trades

    def scan_for_breakouts(self) -> List[Dict[str, Any]]:
        """
        Scans current bar across all assets and all active intervals for Donchian 55 triggers.
        """
        detections = []
        self.check_active_trade_exits()

        for iv in self.intervals:
            btc_df = self.candle_cache.get(f"BTCUSDT_{iv}", self.candle_cache.get("BTCUSDT", None))

            for symbol in self.symbols:
                df = self.candle_cache.get(f"{symbol}_{iv}", self.candle_cache.get(symbol, None))
                if df is None or len(df) < 60:
                    continue

                t_idx = len(df) - 1
                bar_t = df.iloc[t_idx]
                sig_time = str(bar_t["timestamp"])
                sig_key = f"{symbol}_{iv}_{sig_time}"
                trade_key = f"{symbol}_{iv}"

                if sig_key in self.processed_signals:
                    continue

                if trade_key in self.active_trades or symbol in self.active_trades:
                    continue

                prior_highs = df["high"].iloc[-56:-1]
                upper_channel = float(prior_highs.max())
                prior_lows = df["low"].iloc[-56:-1]
                lower_channel = float(prior_lows.min())
                close_t = float(bar_t["close"])

                # Check Long Breakout OR Short Breakdown
                trigger_side = None
                channel_level = None
                if close_t > upper_channel:
                    trigger_side = "LONG"
                    channel_level = upper_channel
                elif close_t < lower_channel:
                    trigger_side = "SHORT"
                    channel_level = lower_channel

                if trigger_side is not None:
                    sig_key = f"{symbol}_{iv}_{trigger_side}_{sig_time}"
                    if sig_key in self.processed_signals:
                        continue

                    self.processed_signals.add(sig_key)

                    features = self.feature_extractor.extract_features_at_t(
                        t_idx=t_idx,
                        df=df,
                        btc_df=btc_df if symbol != "BTCUSDT" else None,
                        direction=trigger_side
                    )

                    eval_res = self.engine.evaluate_candidate(
                        timestamp=sig_time,
                        asset=symbol,
                        breakout_id=sig_key,
                        features=features,
                        baseline_signal="BUY" if trigger_side == "LONG" else "SELL",
                        baseline_entry_price=close_t,
                        eventual_realized_r=None,
                        eventual_pnl=None,
                        outcome_timestamp=None
                    )
                    eval_res["timeframe"] = iv
                    eval_res["side"] = trigger_side

                    # Safeguard 1 (Option B): Stricter AI Threshold for 15M (R >= 1.0)
                    tf_threshold = 1.0 if iv == "15m" else self.engine.threshold
                    eval_res["tf_threshold"] = tf_threshold
                    if iv == "15m" and eval_res["ai_predicted_r"] < 1.0:
                        eval_res["ai_decision"] = "VETO"

                    with open(self.jsonl_log, "a") as f:
                        f.write(json.dumps(eval_res) + "\n")

                    atr_series = self.feature_extractor._compute_atr_series(df["high"], df["low"], df["close"], period=14)
                    atr_t = float(atr_series.iloc[-1])

                    # Safeguard 2 (Option B): Risk Halving for 15M (0.5% risk, max order cap $250)
                    max_cap = 250.0 if iv == "15m" else 500.0
                    risk_mult = 0.5 if iv == "15m" else 1.0
                    qty, dollar_risk, total_cost = self.executor.calculate_position_size(
                        symbol, close_t, atr_t, max_cap=max_cap, risk_mult=risk_mult
                    )

                    order_res = None
                    if eval_res["ai_decision"] == "PASS":
                        if trigger_side == "LONG":
                            order_res = self.executor.place_market_buy(symbol, qty)
                        else:
                            order_res = self.executor.place_market_short(symbol, qty)

                    sl_price = (close_t - dollar_risk) if trigger_side == "LONG" else (close_t + dollar_risk)
                    tp_2r = (close_t + 2.0 * dollar_risk) if trigger_side == "LONG" else (close_t - 2.0 * dollar_risk)
                    tp_3r = (close_t + 3.0 * dollar_risk) if trigger_side == "LONG" else (close_t - 3.0 * dollar_risk)

                    self.active_trades[trade_key] = {
                        "breakout_id": sig_key,
                        "asset": symbol,
                        "side": trigger_side,
                        "timeframe": iv,
                        "entry_time": sig_time,
                        "entry_price": close_t,
                        "stop_loss": sl_price,
                        "initial_stop_loss": sl_price,
                        "take_profit_2r": tp_2r,
                        "take_profit_3r": tp_3r,
                        "initial_dollar_risk": qty * dollar_risk,
                        "breakeven_locked": False,
                        "size": qty,
                        "ai_decision": eval_res["ai_decision"],
                        "order_res": order_res
                    }
                    self._save_state()

                    # Notify Dual Paper Portfolio
                    self.paper_portfolio.on_breakout_signal(
                        symbol=symbol,
                        timestamp=sig_time,
                        entry_price=close_t,
                        atr=atr_t,
                        ai_decision=eval_res["ai_decision"],
                        predicted_r=eval_res["ai_predicted_r"],
                        side=trigger_side
                    )

                    detections.append(eval_res)

                    side_icon = "🟢 LONG (BUY)" if trigger_side == "LONG" else "🔴 SHORT (SELL)"
                    status_icon = "🟢 PASS (TRADE)" if eval_res["ai_decision"] == "PASS" else "🔴 VETO (AVOID)"
                    print(f"\n🚨 [{trigger_side} SIGNAL DETECTED] [{iv.upper()}] {sig_time} | {symbol:<8}")
                    print(f"   • Close: ${close_t:.2f} | 55-Channel: ${channel_level:.2f}")
                    print(f"   • Ridge Predicted R: {eval_res['ai_predicted_r']:>+7.3f}R (Threshold: {tf_threshold:>+7.3f}R)")
                    print(f"   • Decision: {status_icon}")
                    print(f"   • Auto-Execution ({self.executor.mode}): {qty} {symbol} (~${total_cost:.2f})")

                    signal_msg = (
                        f"🚨 <b>[STAGE A SIGNAL DETECTED - {iv.upper()} {side_icon}]</b>\n\n"
                        f"• <b>Asset:</b> #{symbol}\n"
                        f"• <b>Direction:</b> <b>{side_icon}</b>\n"
                        f"• <b>Timeframe:</b> <code>{iv.upper()}</code>\n"
                        f"• <b>Candle Close:</b> <code>{sig_time}</code>\n"
                        f"• <b>Close Price:</b> <code>${close_t:,.2f}</code> (Channel: <code>${channel_level:,.2f}</code>)\n"
                        f"• <b>Stop Loss:</b> <code>${sl_price:,.2f}</code> | <b>TP (+2R):</b> <code>${tp_2r:,.2f}</code>\n"
                        f"• <b>Ridge Predicted R:</b> <code>{eval_res['ai_predicted_r']:>+7.3f}R</code>\n"
                        f"• <b>Threshold:</b> <code>{tf_threshold:>+7.3f}R</code> (Mode: {'Strict 15M R>=1.0' if iv == '15m' else 'Macro/Intraday'})\n"
                        f"• <b>AI Filter Decision:</b> <b>{status_icon}</b>\n"
                        f"• <b>Execution:</b> <code>{self.executor.mode}</code> (Size: <code>{qty} {symbol}</code> ~ <code>${total_cost:.2f}</code>)\n\n"
                        f"<i>(Bi-Directional Auto-Trading Active)</i>"
                    )
                    self.send_telegram_alert(signal_msg)

        return detections

        return detections


def run_live_daemon(poll_interval_seconds: int = 60):
    """
    Continuous Live Shadow Runner Daemon.
    Monitors 4h candle closes across BTC, ETH, SOL, BNB continuously.
    """
    runner = LiveShadowRunner()
    print("=" * 95)
    print("  LIVE SHADOW RUNNER DAEMON STARTED: MULTI-TIMEFRAME MODE")
    print(f"  Assets: {', '.join(runner.symbols)} | Timeframes: {', '.join(runner.intervals)}")
    print(f"  Polling Interval: Every {poll_interval_seconds}s for new closed candles")
    print("  Governance: Zero Model Interventions | Frozen Threshold = +0.356025R")
    print("=" * 95)

    last_candle_times: Dict[str, str] = {}

    while True:
        try:
            runner.update_data()

            # Check exits for any open positions
            exited_trades = runner.check_active_trade_exits()
            if exited_trades:
                print(f"   🔔 Auto-closed {len(exited_trades)} positions.")

            new_candle_detected = False

            for cache_key, df in runner.candle_cache.items():
                if df is not None and not df.empty:
                    latest_ts = str(df["timestamp"].iloc[-1])
                    if last_candle_times.get(cache_key) != latest_ts:
                        new_candle_detected = True
                        last_candle_times[cache_key] = latest_ts

            if new_candle_detected:
                print(f"\n⏰ [{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}] New closed candle detected. Scanning multi-timeframe markets...")
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

