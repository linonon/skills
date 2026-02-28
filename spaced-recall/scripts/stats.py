#!/usr/bin/env python3
"""Generate learning statistics report."""

import json
import sys
from db import init_db, get_stats, list_decks


def format_report(deck: str = None):
    """Generate a formatted stats report."""
    init_db()
    
    if deck:
        s = get_stats(deck)
        lines = [f"📊 **{deck}** 學習統計"]
    else:
        s = get_stats()
        lines = ["📊 **整體學習統計**"]
    
    lines.extend([
        "",
        f"📚 總卡片：{s['total_cards']}",
        f"✅ 已學習：{s['learned']}",
        f"🆕 未學習：{s['new']}",
        f"⏰ 待複習：{s['due_now']}",
        f"🔄 總複習次數：{s['total_reviews']}",
        f"🎯 正確率：{s['accuracy']}%",
    ])
    
    if not deck:
        decks = list_decks()
        if decks:
            lines.extend(["", "**各題庫：**"])
            for d in decks:
                ds = get_stats(d["deck"])
                lines.append(f"  • {d['deck']}：{d['count']} 題，正確率 {ds['accuracy']}%")
    
    return "\n".join(lines)


if __name__ == "__main__":
    deck_filter = sys.argv[1] if len(sys.argv) > 1 else None
    print(format_report(deck_filter))
