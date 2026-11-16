import json
import os
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import pandas as pd
import requests

PROJECT_DIR = Path(__file__).parent.parent
DEPLOY_DIR = Path(__file__).parent
LOGS_DIR = DEPLOY_DIR / "logs"

PORT = 8501


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
                is_running = Path(f"/proc/{pid}").exists() if sys.platform != "darwin" else True
            except Exception:
                pass

        # Recent Telemetry
        recent_signals = []
        if telemetry_file.exists():
            try:
                with open(telemetry_file, "r") as f:
                    lines = [line.strip() for line in f if line.strip()]
                    for l in lines[-10:]:
                        recent_signals.append(json.loads(l))
            except Exception:
                pass

        # Real-time Binance Klines & Breakout Radar
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        radar = []
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
                    dist_pct = (close - upper) / upper * 100
                    radar.append({
                        "symbol": s,
                        "close": close,
                        "upper_channel": upper,
                        "dist_pct": round(dist_pct, 2)
                    })
        except Exception:
            pass

        mode = os.environ.get("BINANCE_MODE", "DRY_RUN")

        return {
            "mode": mode,
            "is_running": is_running,
            "pid": pid,
            "radar": radar,
            "portfolio": portfolio_data,
            "recent_signals": list(reversed(recent_signals))
        }

    def get_dashboard_html(self):
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Crypto-BE-AI | Quant Trading & Stage C Dashboard</title>
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
          <div class="w-3 h-3 rounded-full bg-emerald-400 animate-pulse"></div>
          <h1 class="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            Crypto-BE-AI <span class="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">STAGE C DUAL PAPER</span>
          </h1>
        </div>
        <p class="text-xs text-slate-400 mt-1">Donchian 55 Breakout Engine & Ridge L2 Negative Veto Filter (&theta; = +0.356R)</p>
      </div>
      <div class="flex items-center gap-4 mt-3 sm:mt-0">
        <span id="daemon-badge" class="px-3 py-1 text-xs font-semibold rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
          RUNNER: ACTIVE
        </span>
        <span id="mode-badge" class="px-3 py-1 text-xs font-bold rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/30">
          MODE: DRY_RUN
        </span>
        <span id="last-update" class="text-xs text-slate-400 mono">Connecting...</span>
      </div>
    </header>

    <!-- Key Metrics Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="bg-slate-900/70 border border-slate-800 rounded-xl p-5">
        <div class="text-xs text-slate-400 font-medium uppercase tracking-wider">Baseline Portfolio (No AI)</div>
        <div id="base-equity" class="text-2xl font-bold text-white mono mt-2">$10,000.00</div>
        <div class="flex justify-between items-center text-xs mt-2">
          <span id="base-pnl" class="text-slate-400 mono">PnL: $0.00</span>
          <span id="base-dd" class="text-rose-400 mono">MDD: 0.0%</span>
        </div>
      </div>

      <div class="bg-slate-900/70 border border-indigo-900/50 rounded-xl p-5 relative overflow-hidden">
        <div class="absolute top-0 right-0 w-24 h-24 bg-indigo-500/5 rounded-full blur-xl pointer-events-none"></div>
        <div class="text-xs text-indigo-400 font-medium uppercase tracking-wider">AI-Filtered Portfolio</div>
        <div id="ai-equity" class="text-2xl font-bold text-emerald-400 mono mt-2">$10,000.00</div>
        <div class="flex justify-between items-center text-xs mt-2">
          <span id="ai-pnl" class="text-emerald-400 mono">PnL: $0.00</span>
          <span id="ai-dd" class="text-rose-400 mono">MDD: 0.0%</span>
        </div>
      </div>

      <div class="bg-slate-900/70 border border-slate-800 rounded-xl p-5">
        <div class="text-xs text-slate-400 font-medium uppercase tracking-wider">Net AI Edge (Alpha)</div>
        <div id="net-edge" class="text-2xl font-bold text-indigo-400 mono mt-2">+$0.00</div>
        <div class="text-xs text-slate-400 mt-2">AI Equity - Baseline Equity</div>
      </div>

      <div class="bg-slate-900/70 border border-slate-800 rounded-xl p-5">
        <div class="text-xs text-slate-400 font-medium uppercase tracking-wider">Losses Avoided by Veto</div>
        <div id="avoided-loss" class="text-2xl font-bold text-emerald-400 mono mt-2">$0.00</div>
        <div class="text-xs text-slate-400 mt-2 flex justify-between">
          <span>Opp. Cost: <span id="opp-cost" class="mono text-amber-400">$0.00</span></span>
        </div>
      </div>
    </div>

    <!-- Charts & Market Radar Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Equity Curve Chart -->
      <div class="lg:col-span-2 bg-slate-900/70 border border-slate-800 rounded-xl p-5">
        <h2 class="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4 flex items-center justify-between">
          <span>Comparative Equity Curves ($10k Start)</span>
          <span class="text-xs text-slate-500 normal-case">Updated on candle close</span>
        </h2>
        <div class="h-64">
          <canvas id="equityChart"></canvas>
        </div>
      </div>

      <!-- Live Market Radar -->
      <div class="bg-slate-900/70 border border-slate-800 rounded-xl p-5">
        <h2 class="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
          Market Breakout Radar (4H)
        </h2>
        <div id="radar-list" class="space-y-3">
          <div class="text-xs text-slate-500">Scanning markets...</div>
        </div>
      </div>
    </div>

    <!-- Active Trades & Recent Signals Tables -->
    <div class="grid grid-cols-1 gap-6">
      <div class="bg-slate-900/70 border border-slate-800 rounded-xl p-5 overflow-x-auto">
        <h2 class="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
          Recent Signals & AI Decisions
        </h2>
        <table class="w-full text-left text-xs">
          <thead>
            <tr class="text-slate-400 border-b border-slate-800 pb-2">
              <th class="py-2">Timestamp</th>
              <th>Asset</th>
              <th>Entry Price</th>
              <th>Predicted R</th>
              <th>AI Decision</th>
              <th>Realized R</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="signals-table-body" class="divide-y divide-slate-800/60 mono">
            <tr><td colspan="7" class="py-4 text-center text-slate-500">No signals recorded yet. Status: FLAT / WAITING.</td></tr>
          </tbody>
        </table>
      </div>
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

    async function fetchDashboard() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();

        document.getElementById('last-update').innerText = new Date().toLocaleTimeString();
        document.getElementById('mode-badge').innerText = 'MODE: ' + data.mode;

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
          document.getElementById('avoided-loss').innerText = '$' + (c.avoided_losses_usd || 0).toFixed(2);
          document.getElementById('opp-cost').innerText = '$' + (c.opportunity_costs_usd || 0).toFixed(2);

          if (c.equity_history && c.equity_history.length > 0) {
            chartInstance.data.labels = c.equity_history.map(p => p.timestamp.split(' ')[1] || p.timestamp);
            chartInstance.data.datasets[0].data = c.equity_history.map(p => p.ai_filtered_equity);
            chartInstance.data.datasets[1].data = c.equity_history.map(p => p.baseline_equity);
            chartInstance.update();
          }
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

        // Render Signals
        if (data.recent_signals && data.recent_signals.length > 0) {
          const rows = data.recent_signals.map(s => `
            <tr class="hover:bg-slate-800/30">
              <td class="py-2 text-slate-400">${s.signal_timestamp || s.timestamp || 'N/A'}</td>
              <td class="font-bold text-white">${s.asset}</td>
              <td>$${(s.baseline_entry_price || s.baseline_entry || 0).toLocaleString()}</td>
              <td class="${(s.ai_predicted_r || 0) >= 0.356 ? 'text-emerald-400' : 'text-rose-400'}">${(s.ai_predicted_r || 0).toFixed(3)}R</td>
              <td>
                <span class="px-2 py-0.5 rounded text-[10px] font-bold ${s.ai_decision === 'PASS' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}">
                  ${s.ai_decision}
                </span>
              </td>
              <td>${s.eventual_realized_r !== null && s.eventual_realized_r !== undefined ? s.eventual_realized_r.toFixed(2) + 'R' : '<span class="text-slate-500">PENDING</span>'}</td>
              <td><span class="text-slate-400">${s.event_type || 'ACTIVE'}</span></td>
            </tr>
          `).join('');
          document.getElementById('signals-table-body').innerHTML = rows;
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
