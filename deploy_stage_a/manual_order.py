#!/usr/bin/env python3
"""
Manual Order Execution & Emergency Position Closer for Crypto-BE-AI.
Safely interacts with Binance (Testnet or Live) via BinanceExecutor,
updates live_runner_state.json, records trade outcome in telemetry,
and synchronizes DualPaperPortfolio state.
"""

import sys
import os
import time
import json
import argparse
from pathlib import Path

# Add deploy_stage_a to path
ROOT_DIR = Path(__file__).resolve().parent.parent
DEPLOY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOY_DIR))

from binance_executor import BinanceExecutor
from paper_portfolio import DualPaperPortfolio


def load_env():
    env_file = ROOT_DIR / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and (k not in os.environ or (v and not os.environ[k])):
                        os.environ[k] = v


def get_current_price(symbol: str) -> float:
    import urllib.request
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return float(data["price"])
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch real-time price: {e}")
        return 0.0


def send_telegram(msg: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            import requests
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
                timeout=5
            )
        except Exception:
            pass



def execute_sell(symbol: str, qty: float = None, reason: str = "MANUAL_CLOSE"):
    load_env()
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    mode = os.environ.get("BINANCE_MODE", "TESTNET")

    executor = BinanceExecutor(api_key=api_key, api_secret=api_secret, mode=mode)
    logs_dir = DEPLOY_DIR / "logs"
    runner_state_file = logs_dir / "live_runner_state.json"
    telemetry_file = logs_dir / "live_shadow_telemetry.jsonl"
    paper_state_file = logs_dir / "paper_portfolio_state.json"

    # Load active runner state
    active_trade = {}
    found_key = None
    runner_state = {"processed_signals": [], "active_trades": {}}
    if runner_state_file.exists():
        try:
            with open(runner_state_file, "r") as f:
                runner_state = json.load(f)
                trades = runner_state.get("active_trades", {})
                if symbol in trades:
                    found_key = symbol
                    active_trade = trades[symbol]
                else:
                    for k, v in trades.items():
                        if k == symbol or v.get("asset") == symbol:
                            found_key = k
                            active_trade = v
                            break
        except Exception as e:
            print(f"⚠️ Error reading runner state: {e}")

    # Determine quantity
    if qty is None or qty <= 0:
        if active_trade and "size" in active_trade:
            qty = float(active_trade["size"])
        else:
            print(f"❌ No active trade recorded for {symbol}, and no --qty specified.")
            return False

    is_short = (active_trade.get("side") == "SHORT")
    if is_short:
        print(f"🚀 Initiating COVER SHORT (BUY CLOSE) for {qty} {symbol} (Mode: {mode})...")
        res = executor.close_market_short(symbol, qty)
    else:
        print(f"🚀 Initiating MARKET SELL for {qty} {symbol} (Mode: {mode})...")
        res = executor.place_market_sell(symbol, qty)

    if res.get("status") not in ["FILLED", "SUCCESS"] and not res.get("is_dry_run"):
        print(f"❌ Order failed or rejected: {res}")
        return False

    # Extract fill price
    fills = res.get("fills", [])
    if fills:
        fill_price = float(fills[0].get("price", 0.0))
    else:
        fill_price = get_current_price(symbol)

    order_id = res.get("orderId", "MANUAL_CLOSE")
    action_label = "Covered Short" if is_short else "Sold"
    print(f"✅ [ORDER FILLED] {action_label} {qty} {symbol} at ${fill_price:.2f} | Order ID: {order_id}")

    # Calculate trade metrics
    entry_price = float(active_trade.get("entry_price", fill_price))
    initial_risk = float(active_trade.get("initial_dollar_risk", (entry_price * 0.02 * qty)))
    pnl = (entry_price - fill_price) * qty if is_short else (fill_price - entry_price) * qty
    realized_r = pnl / initial_risk if initial_risk > 0 else 0.0
    tf = active_trade.get("timeframe", "1h")

    print(f"📊 Trade Summary: Entry: ${entry_price:.2f} -> Exit: ${fill_price:.2f}")
    print(f"💰 Realized PnL: {'+' if pnl >= 0 else ''}${pnl:.2f} ({'+' if realized_r >= 0 else ''}{realized_r:.2f}R)")

    exit_time = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    # 1. Update live_runner_state.json
    if found_key and found_key in runner_state.get("active_trades", {}):
        del runner_state["active_trades"][found_key]
        with open(runner_state_file, "w") as f:
            json.dump(runner_state, f, indent=2)
        print(f"💾 Removed {found_key} from active trades in runner state.")

    # 2. Record trade outcome in live_shadow_telemetry.jsonl
    outcome_record = {
        "event_type": "TRADE_OUTCOME",
        "breakout_id": active_trade.get("breakout_id", f"MANUAL_{symbol}_{int(time.time())}"),
        "asset": symbol,
        "entry_time": active_trade.get("entry_time", exit_time),
        "outcome_timestamp": exit_time,
        "entry_price": entry_price,
        "exit_price": fill_price,
        "exit_reason": reason,
        "size": qty,
        "ai_decision": active_trade.get("ai_decision", "PASS"),
        "eventual_realized_r": realized_r,
        "baseline_counterfactual_pnl": pnl,
        "shadow_realized_pnl": pnl,
        "sell_order_id": order_id
    }
    with open(telemetry_file, "a") as f:
        f.write(json.dumps(outcome_record) + "\n")
    print(f"📝 Appended TRADE_OUTCOME to {telemetry_file.name}")

    # 3. Synchronize DualPaperPortfolio
    portfolio = DualPaperPortfolio(state_file=paper_state_file)
    portfolio.on_position_exit(symbol, exit_time, fill_price, reason)
    # Also ensure AI portfolio trade history includes this
    ai_hist = portfolio.ai_filtered.get("trade_history", [])
    ai_hist.append({
        "symbol": symbol,
        "entry_time": active_trade.get("entry_time", exit_time),
        "exit_time": exit_time,
        "entry_price": entry_price,
        "exit_price": fill_price,
        "size": qty,
        "exit_reason": reason,
        "pnl_usd": pnl,
        "realized_r": realized_r
    })
    portfolio.ai_filtered["realized_pnl"] += pnl
    portfolio.ai_filtered["equity"] += pnl
    portfolio.ai_filtered["cash"] += (qty * fill_price)
    portfolio.ai_filtered["total_trades"] += 1
    if pnl >= 0:
        portfolio.ai_filtered["winning_trades"] += 1
    else:
        portfolio.ai_filtered["losing_trades"] += 1
    portfolio.save_state()
    print("📈 DualPaperPortfolio state successfully synchronized.")

    # Send Telegram notification
    tele_msg = (
        f"🔔 <b>[BINANCE ORDER] MARKET SELL EXECUTED</b>\n\n"
        f"• <b>Asset:</b> #{symbol}\n"
        f"• <b>Quantity:</b> <code>{qty}</code>\n"
        f"• <b>Exit Price:</b> <code>${fill_price:,.2f}</code>\n"
        f"• <b>Realized PnL:</b> <code>{'+' if pnl >= 0 else ''}${pnl:.2f} ({'+' if realized_r >= 0 else ''}{realized_r:.2f}R)</code>\n"
        f"• <b>Reason:</b> <code>{reason}</code>\n"
        f"• <b>Order ID:</b> <code>{order_id}</code>\n"
    )
    send_telegram(tele_msg)

    return True


def execute_buy(symbol: str, qty: float = None, timeframe: str = "1h"):
    load_env()
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    mode = os.environ.get("BINANCE_MODE", "TESTNET")

    executor = BinanceExecutor(api_key=api_key, api_secret=api_secret, mode=mode)
    logs_dir = DEPLOY_DIR / "logs"
    runner_state_file = logs_dir / "live_runner_state.json"
    paper_state_file = logs_dir / "paper_portfolio_state.json"

    price = get_current_price(symbol)
    if price <= 0:
        print(f"❌ Failed to fetch current price for {symbol}")
        return False

    if qty is None or qty <= 0:
        # Default ~ $100 notional
        qty = executor.format_quantity(symbol, 100.0 / price)

    print(f"🚀 Initiating MARKET BUY for {qty} {symbol} [{timeframe.upper()}] at ~${price:.2f} (Mode: {mode})...")
    res = executor.place_market_buy(symbol, qty)

    if res.get("status") not in ["FILLED", "SUCCESS"] and not res.get("is_dry_run"):
        print(f"❌ Buy order failed or rejected: {res}")
        return False

    fills = res.get("fills", [])
    fill_price = float(fills[0].get("price", price)) if fills else price
    order_id = res.get("orderId", "MANUAL_BUY")
    entry_time = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    # Stop loss distance adjusts by timeframe (4% for 4h, 2% for 1h, 1% for 15m)
    sl_pct = 0.04 if timeframe == "4h" else (0.02 if timeframe == "1h" else 0.01)
    stop_loss = round(fill_price * (1.0 - sl_pct), 2)
    dollar_risk = (fill_price - stop_loss) * qty

    trade_key = f"{symbol}_{timeframe}"
    trade_info = {
        "breakout_id": f"MANUAL_{symbol}_{timeframe}_{int(time.time())}",
        "asset": symbol,
        "timeframe": timeframe,
        "entry_time": entry_time,
        "entry_price": fill_price,
        "stop_loss": stop_loss,
        "initial_dollar_risk": dollar_risk,
        "size": qty,
        "ai_decision": "PASS",
        "order_res": res
    }

    # Update runner state
    runner_state = {"processed_signals": [], "active_trades": {}}
    if runner_state_file.exists():
        try:
            with open(runner_state_file, "r") as f:
                runner_state = json.load(f)
        except Exception:
            pass

    runner_state.setdefault("active_trades", {})[trade_key] = trade_info
    with open(runner_state_file, "w") as f:
        json.dump(runner_state, f, indent=2)

    # Update paper portfolio
    portfolio = DualPaperPortfolio(state_file=paper_state_file)
    portfolio.on_breakout_signal(
        symbol=symbol,
        timestamp=entry_time,
        entry_price=fill_price,
        atr=(fill_price * 0.02),
        ai_decision="PASS",
        predicted_r=0.50
    )
    portfolio.save_state()

    print(f"✅ [SUCCESS] Bought {qty} {symbol} at ${fill_price:.2f} | Order ID: {order_id}")

    # Send Telegram notification
    tele_msg = (
        f"🛒 <b>[BINANCE ORDER] MARKET BUY EXECUTED</b>\n\n"
        f"• <b>Asset:</b> #{symbol}\n"
        f"• <b>Quantity:</b> <code>{qty}</code>\n"
        f"• <b>Entry Price:</b> <code>${fill_price:,.2f}</code>\n"
        f"• <b>Stop Loss:</b> <code>${stop_loss:,.2f}</code>\n"
        f"• <b>Order ID:</b> <code>{order_id}</code>\n"
    )
    send_telegram(tele_msg)

    return True


def execute_short(symbol: str, qty: float = None, timeframe: str = "1h"):
    load_env()
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    mode = os.environ.get("BINANCE_MODE", "TESTNET")

    executor = BinanceExecutor(api_key=api_key, api_secret=api_secret, mode=mode)
    logs_dir = DEPLOY_DIR / "logs"
    runner_state_file = logs_dir / "live_runner_state.json"
    paper_state_file = logs_dir / "paper_portfolio_state.json"

    price = get_current_price(symbol)
    if price <= 0:
        print(f"❌ Failed to fetch current price for {symbol}")
        return False

    if qty is None or qty <= 0:
        qty = executor.format_quantity(symbol, 100.0 / price)

    print(f"🚀 Initiating MARKET SHORT for {qty} {symbol} [{timeframe.upper()}] at ~${price:.2f} (Mode: {mode})...")
    res = executor.place_market_short(symbol, qty)

    if res.get("status") not in ["FILLED", "SUCCESS"] and not res.get("is_dry_run"):
        print(f"❌ Short order failed or rejected: {res}")
        return False

    fills = res.get("fills", [])
    fill_price = float(fills[0].get("price", price)) if fills else price
    order_id = res.get("orderId", "MANUAL_SHORT")
    entry_time = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    sl_pct = 0.04 if timeframe == "4h" else (0.02 if timeframe == "1h" else 0.01)
    stop_loss = round(fill_price * (1.0 + sl_pct), 2)
    dollar_risk = (stop_loss - fill_price) * qty

    trade_key = f"{symbol}_{timeframe}"
    trade_info = {
        "breakout_id": f"MANUAL_SHORT_{symbol}_{timeframe}_{int(time.time())}",
        "asset": symbol,
        "side": "SHORT",
        "timeframe": timeframe,
        "entry_time": entry_time,
        "entry_price": fill_price,
        "stop_loss": stop_loss,
        "initial_stop_loss": stop_loss,
        "take_profit_2r": round(fill_price * (1.0 - 2.0 * sl_pct), 2),
        "take_profit_3r": round(fill_price * (1.0 - 3.0 * sl_pct), 2),
        "initial_dollar_risk": dollar_risk,
        "breakeven_locked": False,
        "size": qty,
        "ai_decision": "PASS",
        "order_res": res
    }

    runner_state = {"processed_signals": [], "active_trades": {}}
    if runner_state_file.exists():
        try:
            with open(runner_state_file, "r") as f:
                runner_state = json.load(f)
        except Exception:
            pass

    runner_state.setdefault("active_trades", {})[trade_key] = trade_info
    with open(runner_state_file, "w") as f:
        json.dump(runner_state, f, indent=2)

    portfolio = DualPaperPortfolio(state_file=paper_state_file)
    portfolio.on_breakout_signal(
        symbol=symbol,
        timestamp=entry_time,
        entry_price=fill_price,
        atr=(fill_price * 0.02),
        ai_decision="PASS",
        predicted_r=0.50,
        side="SHORT"
    )
    portfolio.save_state()

    print(f"✅ [SUCCESS] Opened SHORT on {qty} {symbol} at ${fill_price:.2f} | Order ID: {order_id}")

    tele_msg = (
        f"🔴 <b>[BINANCE ORDER] MARKET SHORT EXECUTED</b>\n\n"
        f"• <b>Asset:</b> #{symbol} [SHORT]\n"
        f"• <b>Timeframe:</b> <code>{timeframe.upper()}</code>\n"
        f"• <b>Quantity:</b> <code>{qty}</code>\n"
        f"• <b>Entry Price:</b> <code>${fill_price:,.2f}</code>\n"
        f"• <b>Stop Loss:</b> <code>${stop_loss:,.2f}</code>\n"
        f"• <b>Take Profit (2R):</b> <code>${round(fill_price * (1.0 - 2.0 * sl_pct), 2):,.2f}</code>\n"
        f"• <b>Order ID:</b> <code>{order_id}</code>\n"
    )
    send_telegram(tele_msg)

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual Order Executor for Crypto-BE-AI")
    parser.add_argument("action", choices=["buy", "sell", "short"], help="Action: buy, sell, or short")
    parser.add_argument("symbol", type=str, help="Trading pair, e.g., ETHUSDT")
    parser.add_argument("--qty", type=float, default=None, help="Quantity to trade")
    parser.add_argument("--timeframe", type=str, default="1h", help="Timeframe (15m, 1h, 4h)")
    parser.add_argument("--reason", type=str, default="MANUAL_CLOSE", help="Exit reason")

    args = parser.parse_args()
    sym = args.symbol.upper()

    if args.action == "sell":
        execute_sell(sym, args.qty, args.reason)
    elif args.action == "buy":
        execute_buy(sym, args.qty, timeframe=args.timeframe)
    elif args.action == "short":
        execute_short(sym, args.qty, timeframe=args.timeframe)
