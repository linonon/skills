#!/usr/bin/env python3
"""
Claude Code Quota Checker
Queries Anthropic OAuth API to show subscription usage.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)


def get_anthropic_token() -> Optional[str]:
    """
    Get Anthropic OAuth token from Claude Code credentials.
    Tries macOS Keychain first, then falls back to credentials file.
    """
    # Try macOS Keychain
    if sys.platform == "darwin":
        try:
            # Get current username
            import getpass
            username = getpass.getuser()
            
            result = subprocess.run(
                [
                    "security",
                    "find-generic-password",
                    "-s",
                    "Claude Code-credentials",
                    "-a",
                    username,
                    "-w",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Parse JSON from keychain
                try:
                    data = json.loads(result.stdout.strip())
                    token = data.get("claudeAiOauth", {}).get("accessToken")
                    if token:
                        return token
                except Exception:
                    pass
        except Exception:
            pass

    # Try credentials file
    creds_path = Path.home() / ".claude" / ".credentials.json"
    if creds_path.exists():
        try:
            with open(creds_path) as f:
                data = json.load(f)
                # Claude Code structure
                token = data.get("claudeAiOauth", {}).get("accessToken")
                if token:
                    return token
        except Exception:
            pass

    return None


def fetch_quota(token: str) -> dict:
    """Fetch quota data from Anthropic OAuth API."""
    url = "https://api.anthropic.com/api/oauth/usage"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "anthropic-beta": "oauth-2025-04-20",
        "User-Agent": "claude-quota-checker/1.0",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("Error: Unauthorized - invalid token")
        elif e.response.status_code == 403:
            print("Error: Forbidden - token may be revoked")
        else:
            print(f"Error: HTTP {e.response.status_code}")
        sys.exit(1)
    except Exception as e:
        print(f"Error fetching quota: {e}")
        sys.exit(1)


def parse_time(time_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 timestamp."""
    if not time_str:
        return None
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except Exception:
        return None


def format_reset_time(reset_time: datetime, show_weekday: bool = False) -> str:
    """Format reset time as absolute local time (Asia/Taipei)."""
    try:
        from zoneinfo import ZoneInfo
        local_tz = ZoneInfo("Asia/Taipei")
    except ImportError:
        import datetime as _dt
        local_tz = _dt.timezone(_dt.timedelta(hours=8))
    
    local_time = reset_time.astimezone(local_tz)
    now = datetime.now(local_time.tzinfo)
    
    if (local_time - now).total_seconds() < 0:
        return "即將重置"
    
    time_str = local_time.strftime("%H:%M")
    
    if show_weekday:
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        day_name = weekdays[local_time.weekday()]
        return f"重置於{day_name} {time_str}"
    else:
        return f"重置於 {time_str}"


def get_status_icon(utilization: float) -> str:
    """Get status icon based on utilization."""
    if utilization >= 0.9:
        return "🔴"
    elif utilization >= 0.7:
        return "🟡"
    else:
        return "🟢"


def format_quota_entry(name: str, entry: dict) -> None:
    """Format and print a single quota entry."""
    if not entry or entry.get("utilization") is None:
        return

    # Skip disabled quotas
    if entry.get("is_enabled") is False:
        return

    utilization = entry["utilization"]
    resets_at = entry.get("resets_at")

    # Display name mapping
    display_names = {
        "five_hour": "5-Hour Cycle",
        "seven_day": "Weekly (All Models)",
        "seven_day_sonnet": "Weekly (Sonnet)",
        "monthly_limit": "Monthly Limit",
        "extra_usage": "Extra Usage",
    }
    display_name = display_names.get(name, name)

    # Utilization is already 0-1 (e.g., 0.42 = 42%)
    # If it's >1, API might have changed format
    if utilization > 1:
        # Already in percentage or count format
        percent = utilization
        normalized_util = min(utilization / 100, 1.0)  # For icon
    else:
        # Standard 0-1 format
        percent = utilization * 100
        normalized_util = utilization

    # Status icon
    icon = get_status_icon(normalized_util)

    # Format reset time
    reset_time = parse_time(resets_at)
    if reset_time:
        show_weekday = name not in ("five_hour",)
        reset_str = format_reset_time(reset_time, show_weekday=show_weekday)
    else:
        reset_str = "無重置時間"

    # Monthly limit shows actual values
    if name == "monthly_limit" and "monthly_limit" in entry:
        used = entry.get("used_credits", 0)
        limit = entry["monthly_limit"]
        print(f"{icon} {display_name:20} 已用 {percent:5.1f}%  ({used:.1f}/{limit:.0f}h)  {reset_str}")
    else:
        print(f"{icon} {display_name:20} 已用 {percent:5.1f}%  {reset_str}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Check Claude Code subscription quota")
    parser.add_argument("--debug", action="store_true", help="Show raw API response")
    args = parser.parse_args()
    
    print("🦞 Claude Code Quota Checker\n")

    # Get token
    token = get_anthropic_token()
    if not token:
        print("Error: Could not find Anthropic OAuth token")
        print("\nTried:")
        print("  - macOS Keychain (Claude Code-credentials)")
        print("  - ~/.claude/.credentials.json")
        print("\nMake sure Claude Code is installed and you're logged in:")
        print("  claude auth login")
        sys.exit(1)

    # Fetch quota
    print("Fetching quota from Anthropic API...\n")
    quota_data = fetch_quota(token)
    
    if args.debug:
        print("=== Raw API Response ===")
        print(json.dumps(quota_data, indent=2))
        print("========================\n")

    # Print quotas in order
    quota_order = ["five_hour", "seven_day", "seven_day_sonnet", "monthly_limit", "extra_usage"]

    for name in quota_order:
        if name in quota_data:
            format_quota_entry(name, quota_data[name])

    # Print any other quotas not in our predefined list
    for name, entry in quota_data.items():
        if name not in quota_order:
            format_quota_entry(name, entry)

    print()


if __name__ == "__main__":
    main()
