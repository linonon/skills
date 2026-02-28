#!/usr/bin/env python3
"""Add transaction(s) to SQLite and append to Beancount."""

import sqlite3
import argparse
import json
import os
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))

def now_iso():
    return datetime.now(TZ).isoformat()

def append_beancount(path, txns):
    """Append transactions to beancount file."""
    lines = []
    for t in txns:
        lines.append("")
        lines.append(f'{t["date"]} * "{t["payee"]}" "{t["narration"]}"')
        lines.append(f'  {t["account"]}    {t["amount"]} {t.get("currency", "TWD")}')
        lines.append(f'  {t.get("payment", "Assets:Cash")}')
    
    with open(path, "a") as f:
        f.write("\n".join(lines) + "\n")

def main():
    parser = argparse.ArgumentParser(description="Add bookkeeping transaction")
    parser.add_argument("--db", required=True)
    parser.add_argument("--beancount", required=True)
    parser.add_argument("--message", required=True, help="Original message text")
    parser.add_argument("--sender", default=None)
    parser.add_argument("--transactions", required=True, help="JSON array of transactions")
    args = parser.parse_args()

    txns = json.loads(args.transactions)
    ts = now_iso()

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    # Insert message
    cur.execute(
        "INSERT INTO messages (text, sender_id, created_at) VALUES (?, ?, ?)",
        (args.message, args.sender, ts)
    )
    msg_id = cur.lastrowid

    # Insert transactions
    for t in txns:
        cur.execute(
            """INSERT INTO transactions 
               (message_id, date, payee, narration, account, amount, currency, payment, shop, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (msg_id, t["date"], t["payee"], t["narration"], t["account"],
             t["amount"], t.get("currency", "TWD"), t.get("payment", "Assets:Cash"),
             t.get("shop"), ts)
        )

    conn.commit()
    conn.close()

    # Append to beancount
    append_beancount(args.beancount, txns)

    print(f"[OK] Added {len(txns)} transaction(s) from message #{msg_id}")

if __name__ == "__main__":
    main()
