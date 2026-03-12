---
name: self-evolution
description: "Self-evolution engine for OpenClaw. Analyzes session history for recurring errors, classifies risk, auto-fixes low-risk issues, and tracks health trends via daily snapshots. Trigger with: analyze, fix, or trend."
---

# Self-Evolution v0.4

SKILL.md 驅動架構 — agent 直接用原生工具執行分析和修復，不依賴 Node.js CLI。

## 觸發條件

當使用者說以下任一關鍵詞時觸發本 skill：

- **「self-evolution analyze」** → 執行 Analyze 流程
- **「self-evolution fix」** → 執行 Fix 流程
- **「self-evolution trend」** → 執行 Trend 流程
- **「self-evolution full」** → 依序執行 Analyze → Fix → Trend

---

## Analyze（分析）

目標：掃描最近的 session 歷史，偵測錯誤模式，輸出結構化 snapshot。

### 步驟 1：取得 session 清單

使用 `sessions_list` 工具取得最近的 session：

```
sessions_list(limit=20)
```

記錄回傳的 session key 清單。

### 步驟 2：取得每個 session 的 transcript

對每個 session key，使用 `sessions_history` 取得對話記錄：

```
sessions_history(sessionKey=<key>, limit=50, includeTools=true)
```

### 步驟 3：掃描錯誤

在每個 session 的 transcript 中，掃描以下 6 種錯誤類型：

| 錯誤類型 | 識別方式 |
|----------|----------|
| `tool_error` | toolResult 中 `status === "error"` |
| `exec_failure` | Bash 工具回傳 non-zero exit code |
| `timeout` | 包含 "timeout"、"timed out"、"ETIMEDOUT" |
| `network_error` | 包含 "ECONNREFUSED"、"ENOTFOUND"、"fetch failed" |
| `permission_error` | 包含 "EACCES"、"permission denied"、"EPERM" |
| `not_found` | 包含 "ENOENT"、"not found"、"No such file" |

### 步驟 4：去重計數

**去重規則：**
- 同一個 session 內，相同的 `errorType + tool + errorMessage` 組合只計 **1 次**
- 跨 session 的相同錯誤各計 1 次（代表問題重複出現）

實作方式：對每個 session 維護一個 Set，key 為 `${errorType}|${toolName}|${normalizedMessage}`。

### 步驟 5：與前一天 snapshot 比較

1. 讀取 `snapshots/` 目錄，找到最新的 `.json` 檔案
2. 如果存在前一天的 snapshot，計算 delta：
   - `errorDelta` = 今日 totalErrors - 前次 totalErrors
   - `newIssues` = 今日有但前次沒有的 errorType+tool 組合
   - `resolvedIssues` = 前次有但今日沒有的 errorType+tool 組合

### 步驟 6：輸出 snapshot

將分析結果寫入 `snapshots/YYYY-MM-DD.json`，格式如下：

```json
{
  "date": "YYYY-MM-DD",
  "sessionsScanned": 15,
  "errors": {
    "tool_error": { "count": 3, "tools": ["read", "exec"], "deduped": true },
    "exec_failure": { "count": 1, "tools": ["exec"], "deduped": true },
    "timeout": { "count": 0, "tools": [], "deduped": true },
    "network_error": { "count": 0, "tools": [], "deduped": true },
    "permission_error": { "count": 0, "tools": [], "deduped": true },
    "not_found": { "count": 0, "tools": [], "deduped": true }
  },
  "totalErrors": 4,
  "topIssues": [
    {
      "type": "tool_error",
      "tool": "read",
      "pattern": "ENOENT",
      "count": 2,
      "risk": "low",
      "sessions": ["session-key-1", "session-key-2"]
    }
  ],
  "recommendations": [
    {
      "priority": "high",
      "type": "missing_file",
      "description": "File /path/to/file not found in 2 sessions",
      "risk": "low_risk",
      "suggestedFix": "Check if file should exist and create it, or update references"
    }
  ],
  "comparedToPrevious": {
    "errorDelta": -2,
    "newIssues": [],
    "resolvedIssues": ["timeout on web_fetch"]
  }
}
```

### 步驟 7：生成摘要

向使用者輸出人類可讀的摘要報告，包含：
- 掃描了多少 sessions
- 各類錯誤的數量
- Top 3 問題
- 與前次相比的趨勢（上升/下降/持平）
- 建議的修復動作

---

## Fix（修復）

目標：根據最新 snapshot 的 recommendations，按風險等級執行修復。

### 步驟 1：讀取風險規則

讀取 `lib/risk-rules.json`，載入分級規則：

```json
{
  "low_risk": {
    "types": ["missing_file", "workspace_file", "cron_prompt", "config"],
    "action": "auto_fix"
  },
  "high_risk": {
    "types": ["js_patch", "system_service", "config_change", "binary"],
    "paths": ["/opt/homebrew/lib/node_modules/openclaw/", "node_modules/"],
    "patterns": ["gateway restart", "systemctl", "brew services"],
    "action": "notify_human"
  }
}
```

### 步驟 2：分級 recommendations

對最新 snapshot 中每個 recommendation：

1. 檢查 `recommendation.type` 是否在 `low_risk.types` 中 → low_risk
2. 檢查 `recommendation.type` 是否在 `high_risk.types` 中 → high_risk
3. 檢查涉及的路徑是否匹配 `high_risk.paths` → 強制 high_risk
4. 檢查描述是否匹配 `high_risk.patterns` → 強制 high_risk
5. 未知類型 → 預設 high_risk（安全優先）

### 步驟 3A：Low-risk 自動修復

對每個 low_risk recommendation：

1. 使用 `sessions_spawn` 建立 isolated session
2. 給定明確的修復任務 prompt，包含：
   - 錯誤描述
   - 建議的修復方式
   - 安全約束（不要修改 high_risk 路徑下的檔案）
3. 如果涉及 config 修改，先執行 `lib/validator.sh backup <filepath>`
4. 等待 session 完成，檢查結果
5. 如果涉及 config 修改，執行 `lib/validator.sh safe-apply <filepath> <backup_path>`
6. 記錄修復結果到 `fixes-history.json`

### 步驟 3B：High-risk 通知人類

對每個 high_risk recommendation：

1. 將詳細資訊寫入 `pending-actions.md`，格式：
   ```markdown
   ## [YYYY-MM-DD] <issue description>
   - **Risk**: high_risk
   - **Type**: <type>
   - **Details**: <description>
   - **Suggested Fix**: <suggestedFix>
   - **Status**: pending
   ```
2. 通知使用者（透過 message tool 或直接輸出）

### 步驟 4：更新修復歷史

將本次修復結果追加到 `fixes-history.json`：

```json
{
  "timestamp": "2026-03-12T09:00:00Z",
  "snapshot": "2026-03-12",
  "fixes": [
    {
      "recommendation": "<description>",
      "risk": "low_risk",
      "action": "auto_fix",
      "result": "success|failure",
      "sessionKey": "<spawned-session-key>",
      "error": null
    }
  ]
}
```

---

## Trend（趨勢）

目標：讀取最近 7 天的 snapshots，分析系統健康趨勢。

### 步驟 1：讀取 snapshots

讀取 `snapshots/` 目錄下最近 7 個 `.json` 檔案（按日期排序）。

### 步驟 2：計算趨勢

對每個 snapshot 提取 `totalErrors`，計算：
- 錯誤率變化趨勢（上升/下降/持平）
- 最近一次 vs 7 天前的 delta 百分比
- 持續出現的問題（連續 3+ 天出現的錯誤）
- 已解決的問題（前幾天有但最近消失的錯誤）
- 新出現的問題（最近才開始出現的錯誤）

### 步驟 3：輸出趨勢報告

格式範例：
```
系統健康趨勢（最近 7 天）
─────────────────────────
錯誤率：下降 23%（12 → 9）
已解決：timeout on web_fetch, ENOENT config.json
新問題：exec permission denied（low-risk，已自動修復）
持續問題：read ENOENT /path/to/file（出現 5 天）
```

### 步驟 4：Snapshot 保留策略

- 最近 30 天：每日保留
- 30 天以上：自動刪除

清理方式：刪除 `snapshots/` 中日期超過 30 天的 `.json` 檔案。

---

## 參考資料

### 目錄結構

```
self-evolution/
├── SKILL.md                # 本檔案：完整分析和修復流程
├── README.md               # 專案說明
├── lib/
│   ├── risk-rules.json     # 風險分級規則（結構化）
│   └── validator.sh        # config backup/rollback 腳本
├── snapshots/              # 每日健康快照
│   └── YYYY-MM-DD.json     # 結構化分析結果
├── pending-actions.md      # high-risk 待人工確認
├── fixes-history.json      # 修復歷史記錄
└── legacy/                 # v0.3.0 Node.js 程式碼（封存）
```

### Snapshot JSON Schema

```json
{
  "date": "YYYY-MM-DD",
  "sessionsScanned": "number — 掃描的 session 數量",
  "errors": {
    "<errorType>": {
      "count": "number — 去重後的錯誤次數",
      "tools": ["string — 涉及的工具名稱"],
      "deduped": true
    }
  },
  "totalErrors": "number — 所有錯誤類型的 count 總和",
  "topIssues": [
    {
      "type": "string — 錯誤類型",
      "tool": "string — 工具名稱",
      "pattern": "string — 錯誤訊息中的關鍵模式",
      "count": "number — 出現次數",
      "risk": "string — low 或 high",
      "sessions": ["string — 相關 session keys"]
    }
  ],
  "recommendations": [
    {
      "priority": "string — high/medium/low",
      "type": "string — 對應 risk-rules.json 的類型",
      "description": "string — 問題描述",
      "risk": "string — low_risk 或 high_risk",
      "suggestedFix": "string — 建議的修復方式"
    }
  ],
  "comparedToPrevious": {
    "errorDelta": "number — 正數表示增加，負數表示減少",
    "newIssues": ["string — 新出現的問題描述"],
    "resolvedIssues": ["string — 已解決的問題描述"]
  }
}
```

### validator.sh 用法

```bash
# 備份檔案
lib/validator.sh backup /path/to/config

# 回滾
lib/validator.sh rollback /path/to/config /path/to/backup

# 驗證 config
lib/validator.sh validate

# 健康檢查
lib/validator.sh health-check

# 完整安全套用流程
lib/validator.sh safe-apply /path/to/config [backup_path]

# 清理舊備份（保留每檔最近 20 個）
lib/validator.sh prune
```
