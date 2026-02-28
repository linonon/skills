#!/usr/bin/env python3
"""Import a Markdown deck file into SQLite."""

import sys
import re
from pathlib import Path
from db import init_db, add_card


def parse_deck(filepath: str):
    """Parse a .md deck file into cards."""
    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.strip().split("\n")
    
    # Parse header
    deck_name = "Untitled"
    global_tags = []
    content_start = 0
    
    for i, line in enumerate(lines):
        if line.startswith("# "):
            deck_name = line[2:].strip()
        elif line.lower().startswith("tags:"):
            global_tags = [t.strip() for t in line[5:].split(",") if t.strip()]
        elif line.strip() == "---":
            content_start = i + 1
            break
    
    # Split into cards by ---
    card_blocks = []
    current = []
    for line in lines[content_start:]:
        if line.strip() == "---":
            if current:
                card_blocks.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        card_blocks.append("\n".join(current))
    
    # Parse each card
    cards = []
    for block in card_blocks:
        block = block.strip()
        if not block:
            continue
        
        # Find Q: and A:
        q_match = re.search(r'^Q:\s*(.+?)(?=^A:)', block, re.MULTILINE | re.DOTALL)
        a_match = re.search(r'^A:\s*(.+)', block, re.MULTILINE | re.DOTALL)
        
        if not q_match or not a_match:
            continue
        
        front = q_match.group(1).strip()
        back = a_match.group(1).strip()
        
        # Detect card type
        if "{{" in front and "}}" in front:
            card_type = "cloze"
        elif re.search(r'^- [A-D]\)', block, re.MULTILINE):
            card_type = "multi_choice"
        else:
            card_type = "basic"
        
        cards.append({
            "deck": deck_name,
            "front": front,
            "back": back,
            "card_type": card_type,
            "tags": global_tags,
        })
    
    return cards


def import_file(filepath: str):
    init_db()
    cards = parse_deck(filepath)
    ids = []
    for c in cards:
        card_id = add_card(c["deck"], c["front"], c["back"], c["card_type"], c["tags"])
        ids.append(card_id)
    return {"imported": len(ids), "deck": cards[0]["deck"] if cards else "?", "ids": ids}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: import_deck.py <path-to-deck.md>")
        sys.exit(1)
    result = import_file(sys.argv[1])
    print(f"Imported {result['imported']} cards into deck '{result['deck']}'")
