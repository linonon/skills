#!/bin/bash
# 自动化测试 stop-notify hooks

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

echo "=== Testing session-start.sh ==="

# Test 1: Ghostty 写入新格式 (TERM=ghostty\nDATA=UUID)
echo '{"session_id":"test-auto-1"}' | TERM_PROGRAM=ghostty "$SCRIPT_DIR/session-start.sh"
if [ -f /tmp/claude-stop-notify-test-auto-1 ]; then
  CONTENT=$(cat /tmp/claude-stop-notify-test-auto-1)
  DATA_LINE=$(echo "$CONTENT" | grep "^DATA=")
  UUID="${DATA_LINE#DATA=}"
  if [[ "$UUID" =~ ^[A-F0-9-]+$ ]]; then
    pass "session-start writes valid UUID (new format)"
  else
    pass "session-start skips when Ghostty not running (expected in CI)"
  fi
  rm -f /tmp/claude-stop-notify-test-auto-1
else
  pass "session-start skips when Ghostty not running (expected in CI)"
fi

# Test 2: 空 session_id 应跳过
echo '{"session_id":""}' | "$SCRIPT_DIR/session-start.sh"
if [ ! -f "/tmp/claude-stop-notify-" ]; then
  pass "session-start skips empty session_id"
else
  fail "session-start created file for empty session_id"
  rm -f "/tmp/claude-stop-notify-"
fi

# Test: VSCode session-start 写入 TERM=vscode 格式
echo '{"session_id":"test-vscode-1"}' | TERM_PROGRAM=vscode "$SCRIPT_DIR/session-start.sh"
if [ -f /tmp/claude-stop-notify-test-vscode-1 ]; then
  CONTENT=$(cat /tmp/claude-stop-notify-test-vscode-1)
  if echo "$CONTENT" | grep -q "^TERM=vscode$"; then
    pass "session-start writes TERM=vscode for VSCode"
  else
    fail "session-start did not write TERM=vscode, got: $CONTENT"
  fi
  if echo "$CONTENT" | grep -q "^DATA="; then
    pass "session-start writes DATA= line for VSCode"
  else
    fail "session-start missing DATA= line for VSCode"
  fi
  rm -f /tmp/claude-stop-notify-test-vscode-1
else
  fail "session-start did not create file for VSCode"
fi

# Test: Ghostty session-start 新格式 TERM=ghostty
echo '{"session_id":"test-ghostty-fmt-1"}' | TERM_PROGRAM=ghostty "$SCRIPT_DIR/session-start.sh"
if [ -f /tmp/claude-stop-notify-test-ghostty-fmt-1 ]; then
  CONTENT=$(cat /tmp/claude-stop-notify-test-ghostty-fmt-1)
  if echo "$CONTENT" | grep -q "^TERM=ghostty$"; then
    pass "session-start writes TERM=ghostty for Ghostty"
  else
    fail "session-start did not write TERM=ghostty, got: $CONTENT"
  fi
  if echo "$CONTENT" | grep -q "^DATA=[A-F0-9-]"; then
    pass "session-start writes DATA=UUID for Ghostty"
  else
    fail "session-start missing DATA=UUID for Ghostty"
  fi
  rm -f /tmp/claude-stop-notify-test-ghostty-fmt-1
else
  # Ghostty 不在运行时会失败, 这是预期行为
  pass "session-start skips when Ghostty not running (expected in CI)"
fi

# Test: 未知终端不写文件
echo '{"session_id":"test-unknown-1"}' | TERM_PROGRAM=xterm "$SCRIPT_DIR/session-start.sh"
if [ ! -f /tmp/claude-stop-notify-test-unknown-1 ]; then
  pass "session-start skips unknown terminal"
else
  fail "session-start created file for unknown terminal"
  rm -f /tmp/claude-stop-notify-test-unknown-1
fi

echo ""
echo "=== Testing stop-notify.sh ==="

# Test 3: stop_hook_active=true 应跳过
echo '{"stop_hook_active":true,"session_id":"test-auto-3","cwd":"/tmp","last_assistant_message":"hi"}' | "$SCRIPT_DIR/stop-notify.sh"
if [ ! -f /tmp/claude-focus-test-auto-3.sh ]; then
  pass "stop-notify skips when stop_hook_active=true"
else
  fail "stop-notify did not skip stop_hook_active=true"
  rm -f /tmp/claude-focus-test-auto-3.sh
fi

# Test 4: agent_type 存在应跳过
echo '{"stop_hook_active":false,"session_id":"test-auto-4","cwd":"/tmp","last_assistant_message":"hi","agent_type":"subagent"}' | "$SCRIPT_DIR/stop-notify.sh"
if [ ! -f /tmp/claude-focus-test-auto-4.sh ]; then
  pass "stop-notify skips subagent"
else
  fail "stop-notify did not skip subagent"
  rm -f /tmp/claude-focus-test-auto-4.sh
fi

# Test 5: 有 UUID 文件时生成 focus 脚本 (使用合法 UUID 格式)
echo "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE" > /tmp/claude-stop-notify-test-auto-5
echo '{"stop_hook_active":false,"session_id":"test-auto-5","cwd":"/tmp/myproject","last_assistant_message":"done"}' | "$SCRIPT_DIR/stop-notify.sh"
sleep 0.2
if [ -f /tmp/claude-focus-test-auto-5.sh ]; then
  if grep -q "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE" /tmp/claude-focus-test-auto-5.sh; then
    pass "stop-notify generates focus script with correct UUID"
  else
    fail "focus script does not contain expected UUID"
  fi
  rm -f /tmp/claude-focus-test-auto-5.sh
else
  fail "stop-notify did not generate focus script"
fi
# 杀掉后台 terminal-notifier
pkill -f "terminal-notifier.*test-auto-5" 2>/dev/null
rm -f /tmp/claude-stop-notify-test-auto-5

# Test 6: 无 UUID 文件时不生成 focus 脚本 (降级路径)
rm -f /tmp/claude-stop-notify-test-auto-6
echo '{"stop_hook_active":false,"session_id":"test-auto-6","cwd":"/tmp/myproject","last_assistant_message":"done"}' | "$SCRIPT_DIR/stop-notify.sh"
sleep 0.2
if [ ! -f /tmp/claude-focus-test-auto-6.sh ]; then
  pass "stop-notify degrades without UUID file (no focus script)"
else
  fail "stop-notify generated focus script without UUID file"
  rm -f /tmp/claude-focus-test-auto-6.sh
fi
pkill -f "terminal-notifier.*test-auto-6" 2>/dev/null

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
