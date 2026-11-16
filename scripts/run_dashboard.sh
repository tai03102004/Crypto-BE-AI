#!/usr/bin/env bash
# ==============================================================================
# CRYPTO-BE-AI: Launch Local Web Dashboard (Stage C)
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROJECT_DIR/deploy_stage_a/logs/dashboard.pid"
LOG_FILE="$PROJECT_DIR/deploy_stage_a/logs/dashboard.log"

mkdir -p "$PROJECT_DIR/deploy_stage_a/logs"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️ Dashboard is already running (PID: $PID)."
        echo "🌐 Open browser: http://localhost:8501"
        exit 0
    else
        rm "$PID_FILE"
    fi
fi

nohup "$PROJECT_DIR/.venv/bin/python" -u "$PROJECT_DIR/deploy_stage_a/dashboard_server.py" > "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

echo "✅ Web Dashboard started successfully (PID: $NEW_PID)!"
echo "🌐 Open in your browser: http://localhost:8501"
