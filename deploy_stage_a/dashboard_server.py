#!/usr/bin/env python3
"""
Zero-dependency Real-time Web Dashboard Server for Crypto-BE-AI.
Visualizes Stage A & Stage C (Dual Paper Portfolio, Live Shadow Runner,
Binance Testnet / Live Execution, Active Trades, and Market Breakout Radar).
Serves at http://localhost:8501
"""

import os
import sys
import json
import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DEPLOY_DIR = Path(__file__).resolve().parent
LOGS_DIR = DEPLOY_DIR / "logs"
PORT = 8501

sys.path.insert(0, str(DEPLOY_DIR))


def load_env_file():
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


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            data = self.get_dashboard_data()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        elif self.path == "/" or self.path.startswith("/?"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = self.get_dashboard_html()
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/order":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode("utf-8"))
                action = body.get("action", "").lower()
                symbol = body.get("symbol", "").upper()
                qty = body.get("qty", None)
                if qty is not None:
                    qty = float(qty)

                from manual_order import execute_buy, execute_sell

                if action == "buy":
                    success = execute_buy(symbol, qty)
                    res = {"success": success, "message": f"Executed BUY for {symbol}"}
                elif action == "sell":
                    success = execute_sell(symbol, qty, reason="DASHBOARD_MANUAL_CLOSE")
                    res = {"success": success, "message": f"Executed SELL for {symbol}"}
                else:
                    res = {"success": False, "message": f"Unknown action: {action}"}

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def get_dashboard_data(self):
        state_file = LOGS_DIR / "paper_portfolio_state.json"
        runner_state_file = LOGS_DIR / "live_runner_state.json"
        telemetry_file = LOGS_DIR / "live_shadow_telemetry.jsonl"
        pid_file = LOGS_DIR / "mac_daemon.pid"

        portfolio_data = {}
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    portfolio_data = json.load(f)
            except Exception:
                pass

        # Runner Status
        is_running = False
        pid = None
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                # Check process existence
                is_running = (os.system(f"kill -0 {pid} 2>/dev/null") == 0)
            except Exception:
                pass

        # Active Trades from runner state
        active_trades = {}
        if runner_state_file.exists():
            try:
                with open(runner_state_file, "r") as f:
                    rdata = json.load(f)
                    active_trades = rdata.get("active_trades", {})
            except Exception:
                pass

        # Telemetry & Trade History
        recent_signals = []
        closed_trades = []
        if telemetry_file.exists():
            try:
                with open(telemetry_file, "r") as f:
                    lines = [line.strip() for line in f if line.strip()]
                    for l in lines:
                        obj = json.loads(l)
                        if obj.get("event_type") == "TRADE_OUTCOME":
                            closed_trades.append(obj)
                        else:
                            recent_signals.append(obj)
            except Exception:
                pass

        # Real-time Binance Klines & Breakout Radar
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        radar = []
        current_prices = {}
        try:
            for s in symbols:
                res = requests.get(
                    "https://api.binance.com/api/v3/klines",
                    params={"symbol": s, "interval": "4h", "limit": 60},
                    timeout=3
                ).json()
                if isinstance(res, list) and len(res) >= 56:
                    highs = [float(k[2]) for k in res[-56:-1]]
                    upper = max(highs)
                    close = float(res[-1][4])
                    current_prices[s] = close
                    dist_pct = (close - upper) / upper * 100
                    radar.append({
                        "symbol": s,
                        "close": close,
                        "upper_channel": upper,
                        "dist_pct": round(dist_pct, 2)
                    })
        except Exception:
            pass

        # Enhance Active Trades with live prices & unrealized PnL
        enhanced_active_trades = []
        for sym, t in active_trades.items():
            curr_p = current_prices.get(sym, float(t.get("entry_price", 0)))
            entry_p = float(t.get("entry_price", curr_p))
            sz = float(t.get("size", 0))
            unreal_pnl = (curr_p - entry_p) * sz
            init_risk = float(t.get("initial_dollar_risk", 1.0))
            unreal_r = unreal_pnl / init_risk if init_risk > 0 else 0.0
            enhanced_active_trades.append({
                "symbol": sym,
                "entry_time": t.get("entry_time"),
                "entry_price": entry_p,
                "current_price": curr_p,
                "size": sz,
                "stop_loss": float(t.get("stop_loss", 0)),
                "unrealized_pnl_usd": round(unreal_pnl, 2),
                "unrealized_r": round(unreal_r, 2),
                "ai_decision": t.get("ai_decision", "PASS")
            })

        load_env_file()
        mode = os.environ.get("BINANCE_MODE", "TESTNET")
        api_key_set = bool(os.environ.get("BINANCE_API_KEY"))

        # Real Binance Account Balance
        binance_balance_usdt = 0.0
        try:
            from binance_executor import BinanceExecutor
            ex = BinanceExecutor(
                api_key=os.environ.get("BINANCE_API_KEY"),
                api_secret=os.environ.get("BINANCE_API_SECRET"),
                mode=mode
            )
            binance_balance_usdt = round(ex.get_usdt_balance(), 2)
        except Exception:
            pass

        return {
            "mode": mode,
            "api_key_set": api_key_set,
            "is_running": is_running,
            "pid": pid,
            "binance_balance_usdt": binance_balance_usdt,
            "radar": radar,
            "active_trades": enhanced_active_trades,
            "closed_trades": list(reversed(closed_trades)),
            "portfolio": portfolio_data,
            "recent_signals": list(reversed(recent_signals[-15:]))
        }

    def get_dashboard_html(self):
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Crypto-BE-AI | Quant Trading & Live Stage C Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #e2e8f0; }
    .mono { font-family: 'JetBrains Mono', monospace; }
  </style>
</head>
<body class="p-6">
  <div class="max-w-7xl mx-auto space-y-6">

    <!-- Top Navigation -->
    <header class="flex flex-wrap justify-between items-center bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-2xl backdrop-blur">
      <div>
        <div class="flex items-center space-x-3">
          <div class="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></div>
          <h1 class="text-xl font-bold tracking-tight text-white">CRYPTO-BE-AI</h1>
          <span class="bg-indigo-500/20 text-indigo-400 text-xs px-2.5 py-0.5 rounded-full font-semibold border border-indigo-500/30">STAGE C LIVE</span>
          <span id="mode-badge" class="bg-amber-500/20 text-amber-400 text-xs px-2.5 py-0.5 rounded-full font-semibold border border-amber-500/30 mono">MODE: TESTNET</span>
        </div>
        <p class="text-xs text-slate-400 mt-1">Dual Paper Portfolio & Binance Testnet Execution Engine</p>
      </div>
      <div class="flex items-center space-x-4 mt-3 sm:mt-0 text-xs mono">
        <div class="bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
          <span class="text-slate-400">DAEMON:</span>
          <span id="daemon-status" class="font-bold text-emerald-400 ml-1">CHECKING...</span>
        </div>
        <div class="bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
          <span class="text-slate-400">BINANCE USDT:</span>
          <span id="binance-usdt" class="font-bold text-amber-400 ml-1">$0.00</span>
        </div>
        <div class="bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
          <span class="text-slate-400">UPDATED:</span>
          <span id="last-update" class="text-slate-300 ml-1">--:--:--</span>
        </div>
      </div>
    </header>

    <!-- Interactive Execution Bar -->
    <div class="bg-slate-900/90 border border-indigo-900/40 rounded-xl p-4 shadow-xl flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center space-x-2">
        <span class="text-xs font-bold text-indigo-400 uppercase tracking-wider">⚡ Test Execution Hub:</span>
        <span class="text-xs text-slate-400">Quickly place or close Binance Testnet orders to verify end-to-end flow</span>
      </div>
      <div class="flex items-center space-x-3">
        <button onclick="triggerOrder('buy', 'ETHUSDT')" class="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold py-1.5 px-3.5 rounded-lg transition shadow-md flex items-center space-x-1.5">
          <span>🛒 Buy Test ETH (~$90)</span>
        </button>
        <button onclick="triggerOrder('buy', 'SOLUSDT')" class="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold py-1.5 px-3.5 rounded-lg transition shadow-md flex items-center space-x-1.5">
          <span>🛒 Buy Test SOL (~$80)</span>
        </button>
      </div>
    </div>

    <!-- Portfolio Comparison Cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      
      <!-- Baseline Portfolio Card -->
      <div class="bg-slate-900/70 border border-slate-800 rounded-xl p-5 relative overflow-hidden shadow-lg">
        <div class="text-xs uppercase font-semibold text-slate-400 tracking-wider">Portfolio 1: Baseline (No AI)</div>
        <div class="text-2xl font-bold text-white mono mt-2" id="base-equity">$10,000.00</div>
        <div class="flex justify-between items-center mt-3 text-xs mono">
          <span class="text-slate-400" id="base-pnl">PnL: $0.00</span>
          <span class="text-slate-400" id="base-dd">MDD: 0.0%</span>
        </div>
        <div class="text-[11px] text-slate-500 mt-2">Takes every Donchian 55 breakout blindly</div>
      </div>

      <!-- AI-Filtered Portfolio Card -->
      <div class="bg-slate-900/70 border border-emerald-900/40 rounded-xl p-5 relative overflow-hidden shadow-lg shadow-emerald-950/20">
        <div class="text-xs uppercase font-semibold text-emerald-400 tracking-wider">Portfolio 2: AI-Filtered (Locked Ridge)</div>
        <div class="text-2xl font-bold text-emerald-300 mono mt-2" id="ai-equity">$10,000.00</div>
        <div class="flex justify-between items-center mt-3 text-xs mono">
          <span class="text-emerald-400 font-semibold" id="ai-pnl">PnL: $0.00</span>
          <span class="text-slate-400" id="ai-dd">MDD: 0.0%</span>
        </div>
        <div class="text-[11px] text-slate-500 mt-2">Only executes if Ridge Pred R &ge; +0.356R</div>
      </div>

      <!-- Comparative Alpha Metrics -->
      <div class="bg-slate-900/70 border border-indigo-900/40 rounded-xl p-5 shadow-lg">
        <div class="text-xs uppercase font-semibold text-indigo-400 tracking-wider">Net AI Edge (Alpha)</div>
        <div class="text-2xl font-bold text-indigo-300 mono mt-2" id="net-edge">+$0.00</div>
        <div class="flex justify-between items-center mt-3 text-xs mono">
          <span class="text-emerald-400" id="avoided-loss">Avoided Loss: $0.00</span>
          <span class="text-rose-400" id="opp-cost">Opp Cost: $0.00</span>
        </div>
        <div class="text-[11px] text-slate-500 mt-2">Empirical excess return of AI gating</div>
      </div>

    </div>

    <!-- Active Positions Section -->
    <div class="bg-slate-900/80 border border-amber-900/30 rounded-xl p-5 shadow-lg">
      <div class="flex justify-between items-center mb-4">
        <div class="flex items-center space-x-2">
          <span class="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse"></span>
          <h2 class="text-sm font-semibold text-white uppercase tracking-wider">🎯 Active Open Positions</h2>
        </div>
        <span class="text-xs text-slate-500 mono" id="active-count">0 Open Positions</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead>
            <tr class="text-slate-400 border-b border-slate-800 pb-2">
              <th class="py-2">Asset</th>
              <th>Entry Time</th>
              <th>Entry Price</th>
              <th>Current Price</th>
              <th>Size</th>
              <th>Stop Loss</th>
              <th>Unrealized PnL</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="active-trades-table-body" class="divide-y divide-slate-800/60 mono">
            <tr><td colspan="8" class="py-4 text-center text-slate-500">No active positions open. Status: 100% FLAT in Cash.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Chart & Radar Section -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Equity Curve Chart -->
      <div class="lg:col-span-2 bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-lg">
        <h2 class="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4 flex justify-between">
          <span>Comparative Equity Curves ($10k Start)</span>
          <span class="text-xs text-slate-500 normal-case">Real-time MTM</span>
        </h2>
        <div class="h-64">
          <canvas id="equityChart"></canvas>
        </div>
      </div>

      <!-- Live Market Radar -->
      <div class="bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-lg">
        <h2 class="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
          Market Breakout Radar (4H)
        </h2>
        <div id="radar-list" class="space-y-3">
          <div class="text-xs text-slate-500">Scanning markets...</div>
        </div>
      </div>
    </div>

    <!-- Closed Trades History -->
    <div class="bg-slate-900/70 border border-slate-800 rounded-xl p-5 overflow-x-auto shadow-lg">
      <h2 class="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4 flex items-center justify-between">
        <span>📜 Closed Trades History (Realized PnL)</span>
        <span class="text-xs text-slate-500" id="closed-count">0 Closed</span>
      </h2>
      <table class="w-full text-left text-xs">
        <thead>
          <tr class="text-slate-400 border-b border-slate-800 pb-2">
            <th class="py-2">Outcome Time</th>
            <th>Asset</th>
            <th>Size</th>
            <th>Entry Price</th>
            <th>Exit Price</th>
            <th>Realized PnL ($)</th>
            <th>Realized R</th>
            <th>Exit Reason</th>
            <th>Binance Order ID</th>
          </tr>
        </thead>
        <tbody id="closed-trades-table-body" class="divide-y divide-slate-800/60 mono">
          <tr><td colspan="9" class="py-4 text-center text-slate-500">No completed trades yet.</td></tr>
        </tbody>
      </table>
    </div>

  </div>

  <script>
    let chartInstance = null;

    function initChart() {
      const ctx = document.getElementById('equityChart').getContext('2d');
      chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'AI-Filtered Portfolio',
              data: [],
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              borderWidth: 2,
              tension: 0.1,
              fill: true
            },
            {
              label: 'Baseline (No AI)',
              data: [],
              borderColor: '#64748b',
              borderDash: [5, 5],
              borderWidth: 1.5,
              tension: 0.1,
              fill: false
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { grid: { color: 'rgba(51, 65, 85, 0.2)' }, ticks: { color: '#64748b', font: { size: 10 } } },
            y: { grid: { color: 'rgba(51, 65, 85, 0.2)' }, ticks: { color: '#64748b', font: { size: 10 } } }
          },
          plugins: {
            legend: { labels: { color: '#94a3b8', font: { size: 11 } } }
          }
        }
      });
    }

    async function triggerOrder(action, symbol) {
      const confirmMsg = action === 'buy' ? 
        `Confirm placing MARKET BUY for ${symbol} on Binance Testnet?` : 
        `Confirm closing position for ${symbol} on Binance Testnet?`;
      if (!confirm(confirmMsg)) return;

      try {
        const res = await fetch('/api/order', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: action, symbol: symbol })
        });
        const data = await res.json();
        alert(data.message || (data.success ? 'Success!' : 'Failed: ' + data.error));
        fetchDashboard();
      } catch (err) {
        alert('Order error: ' + err);
      }
    }

    async function fetchDashboard() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();

        document.getElementById('last-update').innerText = new Date().toLocaleTimeString();
        document.getElementById('mode-badge').innerText = 'MODE: ' + data.mode;
        
        const dStatus = document.getElementById('daemon-status');
        if (data.is_running) {
          dStatus.innerText = 'ONLINE (PID ' + data.pid + ')';
          dStatus.className = 'font-bold text-emerald-400 ml-1';
        } else {
          dStatus.innerText = 'OFFLINE';
          dStatus.className = 'font-bold text-rose-400 ml-1';
        }

        document.getElementById('binance-usdt').innerText = '$' + data.binance_balance_usdt.toLocaleString(undefined, {minimumFractionDigits: 2});

        // Portfolio Stats
        if (data.portfolio && data.portfolio.baseline) {
          const b = data.portfolio.baseline;
          const a = data.portfolio.ai_filtered;
          const c = data.portfolio.comparative_metrics || {};

          document.getElementById('base-equity').innerText = '$' + b.equity.toLocaleString(undefined, {minimumFractionDigits: 2});
          document.getElementById('base-pnl').innerText = 'PnL: ' + (b.realized_pnl >= 0 ? '+' : '') + '$' + b.realized_pnl.toFixed(2);
          document.getElementById('base-dd').innerText = 'MDD: ' + b.max_drawdown_pct.toFixed(1) + '%';

          document.getElementById('ai-equity').innerText = '$' + a.equity.toLocaleString(undefined, {minimumFractionDigits: 2});
          document.getElementById('ai-pnl').innerText = 'PnL: ' + (a.realized_pnl >= 0 ? '+' : '') + '$' + a.realized_pnl.toFixed(2);
          document.getElementById('ai-dd').innerText = 'MDD: ' + a.max_drawdown_pct.toFixed(1) + '%';

          const netEdge = (c.net_ai_edge_usd || (a.equity - b.equity));
          document.getElementById('net-edge').innerText = (netEdge >= 0 ? '+' : '') + '$' + netEdge.toFixed(2);
          document.getElementById('avoided-loss').innerText = 'Avoided Loss: $' + (c.avoided_losses_usd || 0).toFixed(2);
          document.getElementById('opp-cost').innerText = 'Opp Cost: $' + (c.opportunity_costs_usd || 0).toFixed(2);

          if (c.equity_history && c.equity_history.length > 0) {
            chartInstance.data.labels = c.equity_history.map(p => p.timestamp.split(' ')[1] || p.timestamp);
            chartInstance.data.datasets[0].data = c.equity_history.map(p => p.ai_filtered_equity);
            chartInstance.data.datasets[1].data = c.equity_history.map(p => p.baseline_equity);
            chartInstance.update();
          }
        }

        // Active Trades
        const activeContainer = document.getElementById('active-trades-table-body');
        document.getElementById('active-count').innerText = `${data.active_trades ? data.active_trades.length : 0} Open Positions`;
        if (data.active_trades && data.active_trades.length > 0) {
          activeContainer.innerHTML = data.active_trades.map(t => `
            <tr class="hover:bg-slate-800/30">
              <td class="py-2.5 font-bold text-amber-300">#${t.symbol}</td>
              <td class="text-slate-400">${t.entry_time || 'N/A'}</td>
              <td>$${t.entry_price.toLocaleString()}</td>
              <td class="font-semibold text-white">$${t.current_price.toLocaleString()}</td>
              <td>${t.size}</td>
              <td class="text-rose-400">$${t.stop_loss.toLocaleString()}</td>
              <td class="${t.unrealized_pnl_usd >= 0 ? 'text-emerald-400' : 'text-rose-400'} font-bold">
                ${t.unrealized_pnl_usd >= 0 ? '+' : ''}$${t.unrealized_pnl_usd.toFixed(2)} (${t.unrealized_r >= 0 ? '+' : ''}${t.unrealized_r.toFixed(2)}R)
              </td>
              <td>
                <button onclick="triggerOrder('sell', '${t.symbol}')" class="bg-rose-600 hover:bg-rose-500 text-white font-bold px-2.5 py-1 rounded text-[11px] transition shadow">
                  🛑 Close / Sell
                </button>
              </td>
            </tr>
          `).join('');
        } else {
          activeContainer.innerHTML = `<tr><td colspan="8" class="py-4 text-center text-slate-500">No active positions open. Status: 100% FLAT in Cash.</td></tr>`;
        }

        // Render Radar
        if (data.radar && data.radar.length > 0) {
          const radarHtml = data.radar.map(r => `
            <div class="bg-slate-800/40 border border-slate-800 rounded-lg p-3">
              <div class="flex justify-between items-center text-xs">
                <span class="font-bold text-white mono">#${r.symbol}</span>
                <span class="text-slate-400 mono">$${r.close.toLocaleString()}</span>
              </div>
              <div class="flex justify-between items-center text-xs mt-2 text-slate-400">
                <span>55-High: $${r.upper_channel.toLocaleString()}</span>
                <span class="font-semibold ${r.dist_pct >= 0 ? 'text-emerald-400' : 'text-slate-400'} mono">
                  ${r.dist_pct > 0 ? '+' : ''}${r.dist_pct}%
                </span>
              </div>
              <div class="w-full bg-slate-700/40 rounded-full h-1.5 mt-2 overflow-hidden">
                <div class="bg-indigo-500 h-1.5 rounded-full" style="width: ${Math.max(5, 100 + r.dist_pct * 3)}%"></div>
              </div>
            </div>
          `).join('');
          document.getElementById('radar-list').innerHTML = radarHtml;
        }

        // Render Closed Trades History
        const closedContainer = document.getElementById('closed-trades-table-body');
        document.getElementById('closed-count').innerText = `${data.closed_trades ? data.closed_trades.length : 0} Closed`;
        if (data.closed_trades && data.closed_trades.length > 0) {
          closedContainer.innerHTML = data.closed_trades.map(c => `
            <tr class="hover:bg-slate-800/30">
              <td class="py-2 text-slate-400">${c.outcome_timestamp || 'N/A'}</td>
              <td class="font-bold text-white">#${c.asset}</td>
              <td>${c.size || 0.05}</td>
              <td>$${(c.entry_price || 0).toLocaleString()}</td>
              <td class="text-emerald-400 font-semibold">$${(c.exit_price || 0).toLocaleString()}</td>
              <td class="${(c.shadow_realized_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'} font-bold">
                ${(c.shadow_realized_pnl || 0) >= 0 ? '+' : ''}$${(c.shadow_realized_pnl || 0).toFixed(2)}
              </td>
              <td class="${(c.eventual_realized_r || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
                ${(c.eventual_realized_r || 0) >= 0 ? '+' : ''}${(c.eventual_realized_r || 0).toFixed(2)}R
              </td>
              <td><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">${c.exit_reason || 'CLOSE'}</span></td>
              <td class="text-slate-400 font-mono text-[11px]">${c.sell_order_id || 'N/A'}</td>
            </tr>
          `).join('');
        } else {
          closedContainer.innerHTML = `<tr><td colspan="9" class="py-4 text-center text-slate-500">No completed trades yet.</td></tr>`;
        }

      } catch (err) {
        console.error('Fetch error:', err);
      }
    }

    window.addEventListener('DOMContentLoaded', () => {
      initChart();
      fetchDashboard();
      setInterval(fetchDashboard, 3000);
    });
  </script>
</body>
</html>
"""


def run_server():
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print("=" * 80)
    print(f"🚀 CRYPTO-BE-AI WEB DASHBOARD STARTED")
    print(f"🌐 Access Dashboard in your browser: http://localhost:{PORT}")
    print(f"📊 Auto-refresh: Every 3 seconds")
    print("=" * 80)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Dashboard server stopped.")
        server.server_close()


if __name__ == "__main__":
    run_server()
