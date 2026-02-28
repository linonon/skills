#!/usr/bin/env python3
"""Push due cards via Telegram Bot API directly. No AI agent needed."""

import json
import sys
import urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta
from db import init_db, get_due_cards

CHAT_ID = "2078364301"
CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
QUIET_START = 0   # 00:00
QUIET_END = 6     # 06:00
TZ = timezone(timedelta(hours=8))


def get_bot_token():
    cfg = json.loads(CONFIG_PATH.read_text())
    return cfg["channels"]["telegram"]["botToken"]


def send_telegram(token: str, chat_id: str, text: str, buttons=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    if buttons:
        payload["reply_markup"] = json.dumps({"inline_keyboard": buttons})

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def schedule_next():
    """Schedule next push via openclaw cron CLI."""
    import subprocess
    import os
    
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, scripts_dir)
    from schedule import next_push_time

    # Check remaining due cards
    remaining = get_due_cards(limit=1)
    has_due = len(remaining) > 0

    # Find nearest due card if none due now
    nearest = None
    if not has_due:
        from db import get_conn
        conn = get_conn()
        row = conn.execute(
            "SELECT next_review FROM reviews ORDER BY next_review ASC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            nearest = row[0]

    sched = next_push_time(has_due, nearest)
    fire_at_raw = sched.get("fire_at")
    if not fire_at_raw:
        return

    # Truncate to seconds for openclaw CLI compatibility
    fire_at = fire_at_raw.split(".")[0]
    if "+" not in fire_at and "Z" not in fire_at:
        fire_at += "+00:00"

    # Remove old spaced-recall-next jobs first
    try:
        result = subprocess.run(
            ["openclaw", "cron", "list", "--json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            jobs = json.loads(result.stdout)
            for job in jobs:
                if job.get("name") == "spaced-recall-next":
                    subprocess.run(
                        ["openclaw", "cron", "rm", job["id"]],
                        capture_output=True, timeout=10
                    )
    except Exception:
        pass

    # Add new one-shot cron
    r = subprocess.run([
        "openclaw", "cron", "add",
        "--name", "spaced-recall-next",
        "--at", fire_at,
        "--session", "isolated",
        "--message", 'Run: cd ~/.openclaw/workspace/skills/spaced-recall && python3 scripts/push.py. Output the result only.',
        "--delete-after-run",
        "--no-deliver",
        "--model", "sonnet",
        "--thinking", "off",
    ], capture_output=True, text=True, timeout=15)
    if r.returncode == 0:
        print(f"Next push scheduled at {fire_at} (reason: {sched.get('reason')})")
    else:
        print(f"Cron add failed: {r.stderr}")


def main():
    init_db()
    now = datetime.now(TZ)

    # Quiet hours check
    if QUIET_START <= now.hour < QUIET_END:
        print("Quiet hours, skipping push")
        # Don't auto-schedule; next push will be triggered after user answers
        return

    cards = get_due_cards(limit=3)
    if not cards:
        print("No due cards")
        # Don't auto-schedule; next push will be triggered after user answers
        return

    token = get_bot_token()

    for card in cards:
        text = f"📝 *複習時間！*\n\n🗂 *{card['deck']}*\n\n*Q: {card['front']}*"
        buttons = [
            [
                {"text": "✅ 記得", "callback_data": f"/sr ans {card['id']} 4"},
                {"text": "🤔 勉強", "callback_data": f"/sr ans {card['id']} 3"},
                {"text": "❌ 忘了", "callback_data": f"/sr ans {card['id']} 1"},
            ],
            [{"text": "💡 看答案", "callback_data": f"/sr show {card['id']}"}],
        ]
        result = send_telegram(token, CHAT_ID, text, buttons)
        if result.get("ok"):
            print(f"Pushed: {card['id']} ({card['front'][:30]})")
        else:
            print(f"Failed: {result}")

    # Don't auto-schedule next push; it will be triggered after user answers


if __name__ == "__main__":
    if "--schedule-only" in sys.argv:
        init_db()
        schedule_next()
        print("Scheduled next push")
    else:
        main()
