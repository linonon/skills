---
name: reading
description: Guided reading system for articles and books. Use when user wants to read, continue reading, add a new article/book, check reading list, or manage reading progress. Triggers on keywords like "讀書", "繼續讀", "reading", "閱讀", "書單", "導讀", "下一段".
---

# Reading Skill

管理閱讀清單、導讀文章、追蹤進度的系統。

## 檔案結構

```
~/.openclaw/workspace/reading/
├── index.json              # 閱讀清單索引
├── <slug>-source.md        # 原文
└── <slug>.md               # 筆記 + 進度
```

## index.json 格式

```json
{
  "books": [
    {
      "slug": "dan-koe-fix-life-in-1-day",
      "title": "How to Fix Your Entire Life in 1 Day",
      "author": "Dan Koe",
      "url": "https://...",
      "status": "reading",
      "totalSections": 12,
      "currentSection": 8,
      "addedAt": "2026-02-21",
      "lastReadAt": "2026-02-22"
    }
  ]
}
```

- `status`: `unread` | `reading` | `finished`
- `currentSection`: 下次要讀的段落編號（1-indexed）

## 操作流程

### 新增文章

1. 用 `web_fetch` 抓取內容
2. 存為 `<slug>-source.md`，按段落分節（`## 段落 N：標題`）
3. 建立 `<slug>.md` 筆記檔，包含：
   - 文章資訊（標題、作者、連結、日期）
   - 段落目錄表（含狀態 ⬜/✅）
   - 導讀筆記區（每段讀完後填入）
   - 金句收藏區
   - 讀後反思區
4. 更新 `index.json`

### 導讀（核心流程）

1. 讀取 `index.json` 確認目前進度（`currentSection`）
2. 從 `<slug>-source.md` 讀取對應段落
3. 導讀內容：
   - 原文關鍵段落 + 中文翻譯/解說
   - 核心概念提煉
   - 金句標記
4. **⚠️ 每讀完一段，立即：**
   - 更新 `<slug>.md` 段落狀態 ⬜ → ✅
   - 寫入導讀筆記
   - 更新 `index.json` 的 `currentSection` 和 `lastReadAt`
   - 不要等 session 結束，不要靠「記住」
5. 問 Oliver 有沒有想法，或直接繼續下一段

### 繼續閱讀

1. 如果 Oliver 沒指定哪本 → 讀取 `index.json`，找 `status: "reading"` 的書
2. 如果只有一本在讀 → 直接繼續
3. 如果多本在讀 → 列出讓他選
4. 從 `currentSection` 開始

### 查看書單

讀取 `index.json`，列出所有書的狀態和進度。格式：

```
📚 閱讀清單

📖 How to Fix Your Entire Life in 1 Day — Dan Koe
   進度：7/12 段  |  上次：2026-02-22

📕 [書名] — [作者]
   狀態：未讀
```

## 注意事項

- 進度以 `index.json` 為 source of truth，不靠記憶
- 每次讀完一段就寫檔，這是硬性規則
- 筆記檔的段落目錄和 index.json 的 currentSection 必須同步
