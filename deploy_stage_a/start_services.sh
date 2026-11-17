#!/usr/bin/env bash
set -e

echo "🔍 Verifying frozen model artifacts..."
python verify_artifacts.py

echo "🌐 Starting Web Dashboard Server on port 8501..."
python -u dashboard_server.py &

echo "🚀 Starting Crypto-BE-AI Live Runner Daemon..."
exec python -u live_shadow_runner.py
