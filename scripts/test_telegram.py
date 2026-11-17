#!/usr/bin/env python3
"""
Telegram Notification Tester for Crypto-BE-AI.
Sends a test alert to your Telegram to verify bot integration.
"""

import os
import sys
import requests
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEPLOY_DIR = ROOT_DIR / "deploy_stage_a"
sys.path.insert(0, str(DEPLOY_DIR))

from live_shadow_runner import load_env_file

def test_telegram():
    load_env_file()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    print("=" * 60)
    print("  CRYPTO-BE-AI TELEGRAM ALERT TEST")
    print("=" * 60)

    if not token or not chat_id:
        print("❌ Telegram credentials missing in .env file!")
        print("   Please configure:")
        print("   TELEGRAM_BOT_TOKEN=<your_bot_token_from_BotFather>")
        print("   TELEGRAM_CHAT_ID=<your_user_id_from_userinfobot>")
        print("=" * 60)
        return False

    print(f"📡 Testing Telegram Bot Token: {token[:10]}... | Chat ID: {chat_id}")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    msg = (
        "🚀 <b>[CRYPTO-BE-AI] TELEGRAM ALERT TEST SUCCESSFUL</b>\n\n"
        "🟢 <b>Status:</b> Connected & Verified\n"
        "⚡ <b>Engine:</b> Donchian 55 + Frozen Ridge L2 AI\n"
        "🔔 You will now receive real-time notifications whenever:\n"
        "  • A 4H breakout signal triggers\n"
        "  • An AI decision (PASS / VETO) is made\n"
        "  • A trade is executed or closed on Binance\n"
    )

    try:
        res = requests.post(url, json={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }, timeout=10)
        data = res.json()
        if res.status_code == 200 and data.get("ok"):
            print("✅ Telegram alert sent successfully! Check your Telegram app.")
            print("=" * 60)
            return True
        else:
            print(f"❌ Telegram API returned error: {data}")
            print("=" * 60)
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_telegram()
    sys.exit(0 if success else 1)
