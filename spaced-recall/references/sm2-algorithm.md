# SM-2 間隔重複演算法

基於 SuperMemo SM-2，針對本工具做簡化調整。

## 參數

- **EF (Ease Factor)**：難度係數，初始值 2.5，最低 1.3
- **interval**：複習間隔（天）
- **repetitions**：連續正確次數

## 評分對照

Telegram 按鈕映射：

| 按鈕 | 分數 | 含義 |
|------|------|------|
| ✅ 記得 | 4 | 正確，稍有遲疑 |
| 🤔 勉強 | 3 | 正確但費力 |
| ❌ 忘了 | 1 | 錯誤 |

## 計算邏輯

```python
def sm2(quality, repetitions, ease_factor, interval):
    """
    quality: 0-5 評分
    返回: (new_repetitions, new_ease_factor, new_interval)
    """
    if quality >= 3:  # 正確
        if repetitions == 0:
            interval = 1 / 24  # 1 小時（新卡片第一次）
        elif repetitions == 1:
            interval = 1       # 1 天
        elif repetitions == 2:
            interval = 3       # 3 天
        else:
            interval = interval * ease_factor
        repetitions += 1
    else:  # 錯誤
        repetitions = 0
        interval = 1 / 24  # 1 小時後重新來

    # 更新難度係數
    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease_factor = max(1.3, ease_factor)

    return repetitions, ease_factor, interval
```

## 間隔上限

- 最大間隔：180 天（6 個月）
- 超過此值的卡片視為「已掌握」，降低推送優先級但不完全停止
