#!/bin/bash
# Claude Code SessionStart hook
# 检测终端类型, 记录终端标识供 Stop hook 使用

command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

[ -z "$SESSION_ID" ] && exit 0
[[ "$SESSION_ID" =~ ^[a-zA-Z0-9_-]+$ ]] || exit 0

NOTIFY_FILE="/tmp/claude-stop-notify-${SESSION_ID}"

case "$TERM_PROGRAM" in
  ghostty)
    TERMINAL_UUID=$(osascript -e '
tell application "Ghostty"
  set t to selected tab of front window
  return id of focused terminal of t
end tell
' 2>/dev/null)
    [ -z "$TERMINAL_UUID" ] && exit 0
    printf 'TERM=ghostty\nDATA=%s' "$TERMINAL_UUID" > "$NOTIFY_FILE"
    ;;
  vscode)
    # CWD: 优先 stdin JSON, fallback $PWD
    HOOK_CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
    [ -z "$HOOK_CWD" ] && HOOK_CWD="$PWD"
    [ -z "$HOOK_CWD" ] && exit 0
    printf 'TERM=vscode\nDATA=%s' "$HOOK_CWD" > "$NOTIFY_FILE"
    ;;
  *)
    # 未知终端, 不写文件
    exit 0
    ;;
esac

exit 0
