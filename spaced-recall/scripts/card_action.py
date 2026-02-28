#!/usr/bin/env python3
"""Card actions: get a card, answer a card. Used by the plugin."""

import json
import sys
from db import get_conn, init_db, update_review, get_due_cards
from sm2 import calculate


def get_card(card_id: str):
    init_db()
    conn = get_conn()
    row = conn.execute("""
        SELECT c.*, r.ease_factor, r.interval_days, r.repetitions,
               r.total_reviews, r.correct_count
        FROM cards c JOIN reviews r ON c.id = r.card_id
        WHERE c.id = ?
    """, (card_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def answer_card(card_id: str, quality: int):
    init_db()
    card = get_card(card_id)
    if not card:
        return None

    sm = calculate(quality, card["repetitions"], card["ease_factor"], card["interval_days"])
    correct = quality >= 3
    update_review(card_id, sm["ease_factor"], sm["interval"], sm["repetitions"], correct)

    card.update(sm)
    card["quality"] = quality
    card["correct"] = correct
    # Get remaining due count
    remaining = get_due_cards()
    card["remaining_due"] = len(remaining)
    return card


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: card_action.py <get|answer> <card_id> [quality]")
        sys.exit(1)

    action = sys.argv[1]
    card_id = sys.argv[2]

    if action == "get":
        result = get_card(card_id)
    elif action == "answer":
        quality = int(sys.argv[3]) if len(sys.argv) > 3 else 4
        result = answer_card(card_id, quality)
    else:
        result = None

    print(json.dumps(result, default=str))
