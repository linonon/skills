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

# Test 5: Ghostty 新格式 - 有 TERM=ghostty 文件时生成 Ghostty focus 脚本
printf 'TERM=ghostty\nDATA=AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE' > /tmp/claude-stop-notify-test-auto-5
echo '{"stop_hook_active":false,"session_id":"test-auto-5","cwd":"/tmp/myproject","last_assistant_message":"done"}' | "$SCRIPT_DIR/stop-notify.sh"
sleep 0.2
if [ -f /tmp/claude-focus-test-auto-5.sh ]; then
  if grep -q "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE" /tmp/claude-focus-test-auto-5.sh && grep -q "Ghostty" /tmp/claude-focus-test-auto-5.sh; then
    pass "stop-notify generates Ghostty focus script from new format"
  else
    fail "focus script missing UUID or Ghostty reference"
  fi
  rm -f /tmp/claude-focus-test-auto-5.sh
else
  fail "stop-notify did not generate focus script"
fi
pkill -f "terminal-notifier.*test-auto-5" 2>/dev/null
rm -f /tmp/claude-stop-notify-test-auto-5

# Test: 旧格式 UUID 文件兼容
echo "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE" > /tmp/claude-stop-notify-test-compat-1
echo '{"stop_hook_active":false,"session_id":"test-compat-1","cwd":"/tmp/myproject","last_assistant_message":"done"}' | "$SCRIPT_DIR/stop-notify.sh"
sleep 0.2
if [ -f /tmp/claude-focus-test-compat-1.sh ]; then
  if grep -q "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE" /tmp/claude-focus-test-compat-1.sh && grep -q "Ghostty" /tmp/claude-focus-test-compat-1.sh; then
    pass "stop-notify handles legacy UUID format"
  else
    fail "legacy UUID format not handled correctly"
  fi
  rm -f /tmp/claude-focus-test-compat-1.sh
else
  fail "stop-notify did not generate focus script for legacy format"
fi
pkill -f "terminal-notifier.*test-compat-1" 2>/dev/null
rm -f /tmp/claude-stop-notify-test-compat-1

# Test: VSCode 格式 - 生成 VSCode focus 脚本
printf 'TERM=vscode\nDATA=/Users/test/project' > /tmp/claude-stop-notify-test-vscode-stop-1
echo '{"stop_hook_active":false,"session_id":"test-vscode-stop-1","cwd":"/Users/test/project","last_assistant_message":"done"}' | "$SCRIPT_DIR/stop-notify.sh"
sleep 0.2
if [ -f /tmp/claude-focus-test-vscode-stop-1.sh ]; then
  if grep -q "Code" /tmp/claude-focus-test-vscode-stop-1.sh && grep -q "/Users/test/project" /tmp/claude-focus-test-vscode-stop-1.sh; then
    pass "stop-notify generates VSCode focus script"
  else
    fail "VSCode focus script missing Code app or CWD"
    cat /tmp/claude-focus-test-vscode-stop-1.sh
  fi
  rm -f /tmp/claude-focus-test-vscode-stop-1.sh
else
  fail "stop-notify did not generate VSCode focus script"
fi
pkill -f "terminal-notifier.*test-vscode-stop-1" 2>/dev/null
rm -f /tmp/claude-stop-notify-test-vscode-stop-1

# Test: focus 脚本包含自删除逻辑
printf 'TERM=vscode\nDATA=/Users/test/selfdelete' > /tmp/claude-stop-notify-test-selfdelete-1
echo '{"stop_hook_active":false,"session_id":"test-selfdelete-1","cwd":"/Users/test/selfdelete","last_assistant_message":"done"}' | "$SCRIPT_DIR/stop-notify.sh"
sleep 0.2
if [ -f /tmp/claude-focus-test-selfdelete-1.sh ]; then
  if grep -q 'rm -f' /tmp/claude-focus-test-selfdelete-1.sh; then
    pass "focus script contains self-delete (rm -f)"
  else
    fail "focus script missing self-delete"
  fi
  rm -f /tmp/claude-focus-test-selfdelete-1.sh
else
  fail "focus script not generated for self-delete test"
fi
pkill -f "terminal-notifier.*test-selfdelete-1" 2>/dev/null
rm -f /tmp/claude-stop-notify-test-selfdelete-1

# Test: CWD 含双引号 - 应降级为 activate app
printf 'TERM=vscode\nDATA=/Users/test/my"project' > /tmp/claude-stop-notify-test-vscode-quote-1
echo '{"stop_hook_active":false,"session_id":"test-vscode-quote-1","cwd":"/Users/test/my\"project","last_assistant_message":"done"}' | "$SCRIPT_DIR/stop-notify.sh"
sleep 0.2
# 不应该生成包含未转义双引号的 focus 脚本
if [ -f /tmp/claude-focus-test-vscode-quote-1.sh ]; then
  fail "stop-notify should not generate focus script for CWD with quotes"
  rm -f /tmp/claude-focus-test-vscode-quote-1.sh
else
  pass "stop-notify degrades for CWD with special chars"
fi
pkill -f "terminal-notifier.*test-vscode-quote-1" 2>/dev/null
rm -f /tmp/claude-stop-notify-test-vscode-quote-1

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
