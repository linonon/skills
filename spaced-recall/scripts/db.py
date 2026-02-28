#!/usr/bin/env python3
"""SQLite database operations for spaced-recall."""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "recall.db"


def get_conn():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY,
            deck TEXT NOT NULL,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            card_type TEXT DEFAULT 'basic',
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reviews (
            card_id TEXT PRIMARY KEY REFERENCES cards(id),
            ease_factor REAL DEFAULT 2.5,
            interval_days REAL DEFAULT 0,
            repetitions INTEGER DEFAULT 0,
            next_review TEXT NOT NULL,
            last_review TEXT,
            total_reviews INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS schedule_queue (
            id TEXT PRIMARY KEY,
            fire_at TEXT NOT NULL,
            card_ids TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            cron_job_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_reviews_next ON reviews(next_review);
        CREATE INDEX IF NOT EXISTS idx_cards_deck ON cards(deck);
        CREATE INDEX IF NOT EXISTS idx_schedule_status ON schedule_queue(status);
    """)
    conn.commit()
    conn.close()


def add_card(deck: str, front: str, back: str, card_type: str = "basic", tags: list = None):
    conn = get_conn()
    card_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO cards (id, deck, front, back, card_type, tags, created_at) VALUES (?,?,?,?,?,?,?)",
        (card_id, deck, front, back, card_type, json.dumps(tags or []), now)
    )
    conn.execute(
        "INSERT INTO reviews (card_id, next_review) VALUES (?,?)",
        (card_id, now)
    )
    conn.commit()
    conn.close()
    return card_id


def get_due_cards(before: str = None, limit: int = 3):
    """Get cards due for review."""
    if before is None:
        before = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    rows = conn.execute("""
        SELECT c.*, r.ease_factor, r.interval_days, r.repetitions,
               r.next_review, r.last_review, r.total_reviews, r.correct_count
        FROM cards c
        JOIN reviews r ON c.id = r.card_id
        WHERE r.next_review <= ?
        ORDER BY r.next_review ASC
        LIMIT ?
    """, (before, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_review(card_id: str, ease_factor: float, interval: float, repetitions: int, correct: bool):
    """Update review state after answering."""
    conn = get_conn()
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    next_review = (now + timedelta(days=interval)).isoformat()
    conn.execute("""
        UPDATE reviews SET
            ease_factor = ?,
            interval_days = ?,
            repetitions = ?,
            next_review = ?,
            last_review = ?,
            total_reviews = total_reviews + 1,
            correct_count = correct_count + ?
        WHERE card_id = ?
    """, (ease_factor, interval, repetitions, next_review, now.isoformat(), 1 if correct else 0, card_id))
    conn.commit()
    conn.close()


def get_stats(deck: str = None):
    """Get learning statistics."""
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    
    where = "WHERE c.deck = ?" if deck else ""
    params = (deck,) if deck else ()
    
    total = conn.execute(f"SELECT COUNT(*) FROM cards c {where}", params).fetchone()[0]
    
    due = conn.execute(f"""
        SELECT COUNT(*) FROM cards c
        JOIN reviews r ON c.id = r.card_id
        {where + ' AND' if where else 'WHERE'} r.next_review <= ?
    """, params + (now,)).fetchone()[0]
    
    learned = conn.execute(f"""
        SELECT COUNT(*) FROM cards c
        JOIN reviews r ON c.id = r.card_id
        {where + ' AND' if where else 'WHERE'} r.repetitions > 0
    """, params).fetchone()[0]
    
    stats_row = conn.execute(f"""
        SELECT COALESCE(SUM(r.total_reviews), 0) as total_reviews,
               COALESCE(SUM(r.correct_count), 0) as correct
        FROM cards c
        JOIN reviews r ON c.id = r.card_id
        {where}
    """, params).fetchone()
    
    conn.close()
    
    total_reviews = stats_row[0]
    correct = stats_row[1]
    accuracy = round(correct / total_reviews * 100, 1) if total_reviews > 0 else 0
    
    return {
        "total_cards": total,
        "learned": learned,
        "due_now": due,
        "new": total - learned,
        "total_reviews": total_reviews,
        "accuracy": accuracy,
    }


def list_decks():
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT deck, COUNT(*) as count FROM cards GROUP BY deck").fetchall()
    conn.close()
    return [{"deck": r[0], "count": r[1]} for r in rows]


if __name__ == "__main__":
    import sys
    init_db()
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(json.dumps(get_stats(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "due":
        cards = get_due_cards()
        print(json.dumps(cards, indent=2, default=str))
    elif len(sys.argv) > 1 and sys.argv[1] == "decks":
        print(json.dumps(list_decks(), indent=2))
    else:
        print("Usage: db.py [stats|due|decks]")
        print("DB initialized at:", DB_PATH)
