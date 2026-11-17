#!/usr/bin/env bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1
"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/test_telegram.py"
