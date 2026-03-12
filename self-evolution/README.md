# Self-Evolution Skill

Self-evolution engine for OpenClaw agents — SKILL.md 驅動架構。

## Status

**v0.4.0** — SKILL.md 驅動，放棄 Node.js CLI

## Architecture

Agent 直接用原生工具（`sessions_list`、`sessions_history`、`sessions_spawn`）執行分析和修復，所有邏輯定義在 `SKILL.md` 中。

```
self-evolution/
├── SKILL.md                # 主入口：完整 analyze / fix / trend 流程
├── README.md               # 本檔案
├── lib/
│   ├── risk-rules.json     # 風險分級規則
│   └── validator.sh        # config backup/rollback 腳本
├── snapshots/              # 每日健康快照（JSON）
├── pending-actions.md      # high-risk 待人工確認
├── fixes-history.json      # 修復歷史記錄
└── legacy/                 # v0.3.0 Node.js 程式碼（封存）
```

## Usage

透過 OpenClaw agent 觸發：

| 指令 | 功能 |
|------|------|
| `self-evolution analyze` | 掃描 session 歷史，偵測錯誤，輸出 snapshot |
| `self-evolution fix` | 根據 snapshot 修復問題（low-risk 自動，high-risk 通知） |
| `self-evolution trend` | 讀取最近 7 天 snapshots，分析健康趨勢 |
| `self-evolution full` | 依序執行 analyze → fix → trend |

## Key Changes from v0.3

- **No Node.js dependency** — 所有分析邏輯由 agent 按 SKILL.md 指令執行
- **Structured snapshots** — JSON 格式取代 markdown 報告
- **Deduplication** — 同 session 同 tool 同 error 只計 1 次
- **Risk classification** — `lib/risk-rules.json` 定義 low/high risk 規則
- **Shell validator** — `lib/validator.sh` 純 shell 實作，不依賴 Node.js
- **Trend tracking** — 跨日 snapshot 比較，追蹤錯誤趨勢

## Safety

- Low-risk 修復在 isolated session 執行（`sessions_spawn`）
- Config 修改前自動備份（`validator.sh backup`）
- 驗證失敗自動回滾（`validator.sh safe-apply`）
- High-risk 問題寫入 `pending-actions.md`，等待人工確認
- 未知類型預設 high_risk（安全優先）

## Legacy

v0.3.0 的 Node.js 程式碼保留在 `legacy/` 目錄供參考，不再使用。
