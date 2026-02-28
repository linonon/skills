---
name: spaced-recall
description: Spaced repetition quiz system via Telegram + OpenClaw cron. Use when user wants to create flashcards, add quiz questions, review knowledge, manage study decks, or configure recall settings. Triggers on keywords like "背誦", "複習", "quiz", "flashcard", "記憶", "考我", "新增題目", "學習進度".
---

# Spaced Recall

間隔重複背誦工具。透過 Telegram 隨機推送題目，基於 SM-2 演算法動態調整複習間隔，實現「少食多餐」式學習。

## 核心理念

- **不定時推送**：不是固定 cron 批量推題，而是每次推完立刻排下一次隨機時間
- **少食多餐**：每次 1-3 題，融入日常對話流
- **自適應間隔**：答對的題間隔越來越長，答錯的回到短間隔

## 架構

```
spaced-recall/
├── SKILL.md
├── scripts/
│   ├── db.py            # SQLite 資料庫操作
│   ├── sm2.py           # SM-2 間隔重複演算法
│   ├── import_deck.py   # 從 .md 匯入題庫
│   ├── schedule.py      # 排程計算（隨機間隔）
│   └── stats.py         # 學習統計
├── references/
│   ├── deck-format.md   # 題庫 Markdown 格式說明
│   └── sm2-algorithm.md # SM-2 演算法參考
└── data/                # 運行時資料（gitignore）
    ├── recall.db        # SQLite 資料庫
    └── decks/           # 題庫 .md 檔案
```

## 資料儲存

### 題庫（Markdown）

題庫存為 `.md` 檔案，放在 `data/decks/` 目錄。格式見 [references/deck-format.md](references/deck-format.md)。

### 學習狀態（SQLite）

`data/recall.db` 儲存：

**cards 表：**
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | TEXT PK | UUID |
| deck | TEXT | 所屬題庫名稱 |
| front | TEXT | 題目（問題面） |
| back | TEXT | 答案（答案面） |
| card_type | TEXT | basic / cloze / multi_choice |
| tags | TEXT | JSON array of tags |
| created_at | TEXT | ISO timestamp |

**reviews 表（SM-2 狀態）：**
| 欄位 | 類型 | 說明 |
|------|------|------|
| card_id | TEXT FK | 對應 cards.id |
| ease_factor | REAL | 難度係數（初始 2.5） |
| interval_days | REAL | 當前間隔（天） |
| repetitions | INT | 連續正確次數 |
| next_review | TEXT | 下次複習時間（ISO） |
| last_review | TEXT | 上次複習時間 |
| total_reviews | INT | 總複習次數 |
| correct_count | INT | 答對次數 |

**schedule_queue 表：**
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | TEXT PK | UUID |
| fire_at | TEXT | 預計推送時間（ISO） |
| card_ids | TEXT | JSON array，本次要推的卡片 ID |
| status | TEXT | pending / fired / cancelled |
| cron_job_id | TEXT | OpenClaw cron job ID |

## SM-2 演算法

使用 SuperMemo SM-2 變體。見 [references/sm2-algorithm.md](references/sm2-algorithm.md)。

回答評分：
- **5** — 完美，毫不猶豫
- **4** — 正確，稍有遲疑
- **3** — 正確，但費力回想
- **2** — 錯誤，但看到答案覺得熟悉
- **1** — 錯誤，模糊記憶
- **0** — 完全不記得

簡化互動（Telegram 按鈕）：
- ✅ 記得（映射為 4）
- 🤔 勉強（映射為 3）
- ❌ 忘了（映射為 1）

## 排程規則

### 隨機間隔
每次推送完成後，計算下一次推送時間：

1. 從 SQLite 查詢所有 `next_review <= 預計時間` 的卡片
2. 如果有到期卡片：隨機間隔 = `15min ~ 2hr`
3. 如果沒有到期卡片：間隔 = `min(距離最近到期卡片的時間, 6hr)`
4. 在計算出的間隔上加 ±20% 隨機擾動
5. 透過 OpenClaw `cron add`（kind: "at"）建立一次性排程

### 約束
- **最短間隔**：15 分鐘
- **最長間隔**：6 小時
- **靜默時段**：00:00 - 06:00（如果計算出的時間落在此區間，推遲到 06:00 + 隨機 0-30min）
- **每次題數**：1-3 題（根據到期卡片數量和近期答題狀態動態決定）

### 使用 OpenClaw Cron

每次推送後，用 `cron add` 建立下一次的一次性排程（`schedule.kind: "at"`）：

```json
{
  "name": "spaced-recall-next",
  "schedule": { "kind": "at", "at": "<calculated-ISO-timestamp>" },
  "payload": { "kind": "agentTurn", "message": "Run spaced-recall: push due cards to Oliver" },
  "sessionTarget": "isolated",
  "delivery": { "mode": "announce" }
}
```

## 工作流程

### 新增題目

用戶說「新增題目」或提供學習材料時：

1. 解析內容，生成 Q&A 卡片
2. 寫入 `data/decks/<deck-name>.md`
3. 執行 `scripts/import_deck.py` 匯入 SQLite
4. 確認新增數量，並排程第一次複習（30min 後）

### 推送複習

cron job 觸發時：

1. 執行 `scripts/db.py` 查詢到期卡片
2. 選 1-3 張卡片
3. 透過 Telegram 發送題目（含 inline buttons）
4. 等待用戶回答
5. 根據回答執行 `scripts/sm2.py` 更新間隔
6. 執行 `scripts/schedule.py` 計算下一次時間
7. 用 `cron add` 建立下一次排程
8. 如果有舊的 pending 排程，用 `cron remove` 清除

### 查看進度

用戶問學習進度時：

1. 執行 `scripts/stats.py`
2. 顯示：總卡片數、已學習、待複習、正確率、各題庫狀態

## Telegram 互動格式

### 推送題目

```
📝 複習時間！

【題庫：JavaScript 基礎】

Q: What does `===` do in JavaScript?
```

附帶 inline buttons：`✅ 記得` | `🤔 勉強` | `❌ 忘了` | `💡 看答案`

### 點擊「看答案」後

```
A: Strict equality operator. Compares both value and type without type coercion.

你答對了嗎？
```

附帶 inline buttons：`✅ 記得` | `🤔 勉強` | `❌ 忘了`

### 回答後回饋

```
✅ Nice！下次複習：3 天後
📊 這張卡片：已複習 5 次，正確率 80%
```
