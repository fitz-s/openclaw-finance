# Finance Report Style Guide

## 语言

中文主体 + 英文专有名词。
- Ticker 永远英文: `AAPL`, `SPY`, `BTC/USD`
- 数据永远带单位: `$107.36`, `+2.3%`, `VIX 28.5`
- 时间永远标时区: `09:30 ET`, `14:00 Chicago`

## 数据纪律

- **每个数字必须有来源**。不说"市场下跌", 说"SPY 盘前 -1.2% (yfinance 08:15 ET)"
- **不要编造数据**。搜不到就不写, 写"数据不可用"
- **价格用最新 prices.json**, 不要从记忆推算
- **涨跌幅算法**: `(current - previous_close) / previous_close × 100`
- **不要混时间窗口**: 盘前报告不引用盘后数据

## 写作风格

- **一句话 > 一段话**。能用 bullet 不用段落。
- **数据 > 观点**。先列事实, 再给解读, 明确标注哪个是哪个。
- **不要开场白**。不要"今日市场概况如下"。直接进入内容。
- **不要客套结尾**。不要"以上是本次报告"。最后一条信息就是结尾。
- **Fact / Interpretation / To Verify 永远分开**, 不要混在同一个 bullet 里。

## 格式约束

- 标题和章节: 按 `systems/finance-report-contract.md` 与当前 `finance-report-envelope` contract；旧 `REPORT_TEMPLATE.md` 已移入 `legacy/report-v1/`，不得作为 active template。
- Watchlist 表格: 只列**有变动**的 ticker, 不要全列
- Surface 分层:
  - `Discord Primary`: 主频道主消息；必须单独可读；必须有 `Fact / Interpretation / To Verify / 对象`
  - `Discord Thread`: thread 首帖；负责对象卡 + 可直接追问；不代替主频道报告
  - `Artifact Record`: 完整 `markdown` / envelope / decision log；供 validator / audit / replay
- 长度上限:
  - Short: ≤ 300 字
  - Core: ≤ 800 字
  - Immediate Alert: ≤ 200 字
- 不要用 emoji (除了 🚨 在 immediate_alert 标题)

## 反模式 (quality_gate 会 reject)

- None/null 出现在输出里
- 数字中间混入中文 (`-1.主模型32`)
- 同一 ticker 在同一报告里出现不同价格
- 旧日期的数据出现在新报告里
- 重复上一份报告已经覆盖的 observation
- 全英文输出
