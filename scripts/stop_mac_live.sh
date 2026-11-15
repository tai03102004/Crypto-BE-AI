#!/usr/bin/env bash
# ==============================================================================
# CRYPTO-BE-AI: Stop Mac Local Runner Daemon
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROJECT_DIR/deploy_stage_a/logs/mac_daemon.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "🛑 Stopping Crypto-BE-AI daemon (PID: $PID)..."
        kill "$PID"
        rm "$PID_FILE"
        echo "✅ Daemon stopped cleanly."
    else
        echo "ℹ️ Process $PID is not running. Removing stale PID file."
        rm "$PID_FILE"
    fi
else
    echo "ℹ️ No running daemon PID file found."
fi
