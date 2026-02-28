#!/usr/bin/env python3
"""Calculate next push time with randomized intervals."""

import random
from datetime import datetime, timedelta, timezone


# Constraints
MIN_INTERVAL_MIN = 15
MAX_INTERVAL_HR = 6
QUIET_START = 0   # 00:00
QUIET_END = 6     # 06:00
JITTER_RATIO = 0.2  # ±20%


def next_push_time(has_due_cards: bool, nearest_due_iso: str = None, tz_offset_hours: int = 8):
    """
    Calculate next push time.
    
    Args:
        has_due_cards: whether there are cards due now
        nearest_due_iso: ISO timestamp of nearest due card (if no due cards now)
        tz_offset_hours: timezone offset (default +8 for Asia/Taipei)
    
    Returns:
        dict with fire_at (ISO), interval_minutes, reason
    """
    now = datetime.now(timezone.utc)
    tz = timezone(timedelta(hours=tz_offset_hours))
    
    if has_due_cards:
        # Cards are due → short random interval (15min ~ 2hr)
        base_minutes = random.randint(MIN_INTERVAL_MIN, 120)
        reason = "due_cards_pending"
    elif nearest_due_iso:
        # No due cards → wait until nearest due
        nearest = datetime.fromisoformat(nearest_due_iso.replace("Z", "+00:00"))
        delta = (nearest - now).total_seconds() / 60
        base_minutes = min(max(delta, MIN_INTERVAL_MIN), MAX_INTERVAL_HR * 60)
        reason = "waiting_for_next_due"
    else:
        # No cards at all
        base_minutes = MAX_INTERVAL_HR * 60
        reason = "no_cards"
    
    # Add jitter ±20%
    jitter = base_minutes * JITTER_RATIO
    final_minutes = base_minutes + random.uniform(-jitter, jitter)
    final_minutes = max(MIN_INTERVAL_MIN, final_minutes)
    
    fire_at = now + timedelta(minutes=final_minutes)
    
    # Check quiet hours (in local time)
    local_fire = fire_at.astimezone(tz)
    if QUIET_START <= local_fire.hour < QUIET_END:
        # Push to 06:00 + random 0-30min
        local_fire = local_fire.replace(hour=QUIET_END, minute=0, second=0)
        local_fire += timedelta(minutes=random.randint(0, 30))
        fire_at = local_fire.astimezone(timezone.utc)
        reason += "_delayed_quiet_hours"
    
    return {
        "fire_at": fire_at.isoformat(),
        "interval_minutes": round(final_minutes, 1),
        "reason": reason,
    }


if __name__ == "__main__":
    import json, sys
    has_due = "--due" in sys.argv
    nearest = None
    for i, a in enumerate(sys.argv):
        if a == "--nearest" and i + 1 < len(sys.argv):
            nearest = sys.argv[i + 1]
    result = next_push_time(has_due, nearest)
    print(json.dumps(result, indent=2))
