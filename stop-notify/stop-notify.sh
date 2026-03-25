#!/bin/bash
# Claude Code Stop hook
# 发送 macOS 通知, 点击跳转到对应终端窗口 (Ghostty / VSCode)

command -v terminal-notifier >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat)
STOP_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // empty')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
MESSAGE=$(echo "$INPUT" | jq -r '.last_assistant_message // empty')

# 防无限循环
[ "$STOP_ACTIVE" = "true" ] && exit 0

# SESSION_ID 格式验证 (防路径注入)
[[ "$SESSION_ID" =~ ^[a-zA-Z0-9_-]+$ ]] || exit 0

# 跳过 subagent
AGENT_TYPE=$(echo "$INPUT" | jq -r '.agent_type // empty')
[ -n "$AGENT_TYPE" ] && exit 0

# 读取 SessionStart 时记录的终端信息
NOTIFY_FILE="/tmp/claude-stop-notify-${SESSION_ID}"
TERM_TYPE=""
TERM_DATA=""
if [ -f "$NOTIFY_FILE" ]; then
  FILE_CONTENT=$(cat "$NOTIFY_FILE")

  # 向后兼容: 旧格式是纯 UUID 单行
  if [[ "$FILE_CONTENT" =~ ^[A-F0-9-]+$ ]]; then
    TERM_TYPE="ghostty"
    TERM_DATA="$FILE_CONTENT"
  else
    TERM_TYPE=$(echo "$FILE_CONTENT" | grep '^TERM=' | head -1 | cut -d= -f2)
    TERM_DATA=$(echo "$FILE_CONTENT" | grep '^DATA=' | head -1 | cut -d= -f2-)
  fi
fi

PROJECT=$(basename "$CWD")
# 去换行, 去双引号/反引号 (防 shell 注入), 截取 80 字
BODY=$(echo "$MESSAGE" | tr '\n' ' ' | tr -d '"\`' | cut -c1-80)

FOCUS_SCRIPT="/tmp/claude-focus-${SESSION_ID}.sh"

case "$TERM_TYPE" in
  ghostty)
    # UUID 格式验证
    [[ "$TERM_DATA" =~ ^[A-F0-9-]+$ ]] || TERM_TYPE=""
    if [ -n "$TERM_TYPE" ]; then
      cat > "$FOCUS_SCRIPT" << SCRIPT
#!/bin/bash
osascript << 'APPLESCRIPT'
tell application "Ghostty"
  activate
  repeat with w in every window
    repeat with t in every tab of w
      if id of focused terminal of t is "${TERM_DATA}" then
        select tab t
        return
      end if
    end repeat
  end repeat
end tell
APPLESCRIPT
rm -f "\$0"
SCRIPT
      chmod +x "$FOCUS_SCRIPT"

      terminal-notifier \
        -title "Claude Code - ${PROJECT}" \
        -message "${BODY}" \
        -group "${SESSION_ID}" \
        -execute "$FOCUS_SCRIPT" &
    fi
    ;;
  vscode)
    # CWD 安全检查: 包含双引号则降级
    if [[ "$TERM_DATA" == *'"'* ]]; then
      terminal-notifier \
        -title "Claude Code - ${PROJECT}" \
        -message "${BODY}" \
        -group "${SESSION_ID}" \
        -activate "com.microsoft.VSCode" &
    else
      cat > "$FOCUS_SCRIPT" << SCRIPT
#!/bin/bash
osascript << 'APPLESCRIPT'
tell application "Code"
  activate
  repeat with w in every window
    if name of w contains "${TERM_DATA}" then
      set index of w to 1
      exit repeat
    end if
  end repeat
end tell
APPLESCRIPT
rm -f "\$0"
SCRIPT
      chmod +x "$FOCUS_SCRIPT"

      terminal-notifier \
        -title "Claude Code - ${PROJECT}" \
        -message "${BODY}" \
        -group "${SESSION_ID}" \
        -execute "$FOCUS_SCRIPT" &
    fi
    ;;
  *)
    # 降级: 只发通知, 不做窗口跳转
    terminal-notifier \
      -title "Claude Code - ${PROJECT}" \
      -message "${BODY}" \
      -group "${SESSION_ID}" &
    ;;
esac

exit 0
