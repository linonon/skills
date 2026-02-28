#!/usr/bin/env python3
"""SM-2 Spaced Repetition Algorithm"""

def calculate(quality: int, repetitions: int, ease_factor: float, interval: float):
    """
    Calculate next review parameters using SM-2 algorithm.
    
    Args:
        quality: 0-5 rating (0=blank, 1=wrong, 3=hard, 4=good, 5=perfect)
        repetitions: consecutive correct count
        ease_factor: difficulty factor (initial 2.5, min 1.3)
        interval: current interval in days
    
    Returns:
        dict with new_repetitions, new_ease_factor, new_interval (days)
    """
    if quality >= 3:  # correct
        if repetitions == 0:
            new_interval = 1 / 24  # 1 hour for first review
        elif repetitions == 1:
            new_interval = 1
        elif repetitions == 2:
            new_interval = 3
        else:
            new_interval = interval * ease_factor
        new_repetitions = repetitions + 1
    else:  # incorrect
        new_repetitions = 0
        new_interval = 1 / 24  # retry in 1 hour

    # Update ease factor
    new_ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ease_factor = max(1.3, new_ease_factor)

    # Cap interval
    new_interval = min(new_interval, 180)

    return {
        "repetitions": new_repetitions,
        "ease_factor": round(new_ease_factor, 2),
        "interval": round(new_interval, 4),
    }


# --- Telegram button mapping ---
BUTTON_MAP = {
    "記得": 4,
    "勉強": 3,
    "忘了": 1,
}


if __name__ == "__main__":
    import json, sys
    q = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    r = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    ef = float(sys.argv[3]) if len(sys.argv) > 3 else 2.5
    iv = float(sys.argv[4]) if len(sys.argv) > 4 else 0
    result = calculate(q, r, ef, iv)
    print(json.dumps(result, indent=2))
