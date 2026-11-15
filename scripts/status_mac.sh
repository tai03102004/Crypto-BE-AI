#!/usr/bin/env bash
# ==============================================================================
# CRYPTO-BE-AI: Check Mac Runner Status & Recent Activity
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROJECT_DIR/deploy_stage_a/logs/mac_daemon.pid"
LOG_FILE="$PROJECT_DIR/deploy_stage_a/logs/mac_daemon.log"
STATE_FILE="$PROJECT_DIR/deploy_stage_a/logs/live_runner_state.json"

echo "=============================================================================="
echo "  CRYPTO-BE-AI AUTO-TRADING RUNNER STATUS (macOS)"
echo "=============================================================================="

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "🟢 Status: RUNNING (PID: $PID)"
    else
        echo "🔴 Status: STOPPED (Stale PID file found)"
    fi
else
    echo "⚪ Status: NOT RUNNING"
fi

if [ -f "$STATE_FILE" ]; then
    echo ""
    echo "📊 Active Trades & State:"
    cat "$STATE_FILE"
fi

if [ -f "$LOG_FILE" ]; then
    echo ""
    echo "📜 Recent 15 Log Lines:"
    echo "------------------------------------------------------------------------------"
    tail -n 15 "$LOG_FILE"
    echo "------------------------------------------------------------------------------"
fi
