#!/bin/bash
# Claude Code SessionStart hook
# 记录当前 Ghostty terminal UUID, 供 Stop hook 使用

command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id')

[ -z "$SESSION_ID" ] && exit 0

TERMINAL_UUID=$(osascript -e '
tell application "Ghostty"
  set t to selected tab of front window
  return id of focused terminal of t
end tell
' 2>/dev/null)

[ -z "$TERMINAL_UUID" ] && exit 0

echo "$TERMINAL_UUID" > "/tmp/claude-stop-notify-${SESSION_ID}"
exit 0
