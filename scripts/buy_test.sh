#!/usr/bin/env bash
# ==============================================================================
# CRYPTO-BE-AI: Buy Test Order on Binance Testnet
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

SYMBOL="${1:-ETHUSDT}"
QTY="${2:-}"

if [ -n "$QTY" ]; then
    "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/deploy_stage_a/manual_order.py" buy "$SYMBOL" --qty "$QTY"
else
    "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/deploy_stage_a/manual_order.py" buy "$SYMBOL"
fi
