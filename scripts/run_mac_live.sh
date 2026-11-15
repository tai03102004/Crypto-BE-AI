#!/usr/bin/env bash
# ==============================================================================
# CRYPTO-BE-AI: Mac Local Live Runner Launcher (Auto-Trading Daemon)
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

LOG_FILE="$PROJECT_DIR/deploy_stage_a/logs/mac_daemon.log"
PID_FILE="$PROJECT_DIR/deploy_stage_a/logs/mac_daemon.pid"

mkdir -p "$PROJECT_DIR/deploy_stage_a/logs"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️ Runner daemon is already running (PID: $PID)."
        echo "   To view logs: tail -f $LOG_FILE"
        echo "   To stop: ./scripts/stop_mac_live.sh"
        exit 0
    else
        rm "$PID_FILE"
    fi
fi

echo "🚀 Starting Crypto-BE-AI Auto-Trading Runner on macOS..."
nohup "$PROJECT_DIR/.venv/bin/python" -u "$PROJECT_DIR/deploy_stage_a/live_shadow_runner.py" --daemon > "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

echo "✅ Daemon started successfully (PID: $NEW_PID)."
echo "📁 Logging to: $LOG_FILE"
echo "🔍 View live activity: tail -f $LOG_FILE"
