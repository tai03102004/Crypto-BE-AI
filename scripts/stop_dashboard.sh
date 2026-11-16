#!/usr/bin/env bash
# ==============================================================================
# CRYPTO-BE-AI: Stop Local Web Dashboard
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROJECT_DIR/deploy_stage_a/logs/dashboard.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "🛑 Stopping Dashboard server (PID: $PID)..."
        kill "$PID"
        rm "$PID_FILE"
        echo "✅ Dashboard stopped."
    else
        rm "$PID_FILE"
    fi
fi
