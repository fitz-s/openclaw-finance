# Finance Workspace — Working Principles (Definitive)

> 适用对象：所有 finance 模块子 agent、scanner、report orchestrator、cron job 及相关脚本。
> 核心原则：**不是新闻转发器**。是 24/7 有判断力的市场监控系统。

## Executable Truth Precedence

本文件是 **finance executable truth 的总结层**，不是独立真源。

如果本文与代码 / 配置 / state 冲突，以这些 surface 为准：
- `services/market-ingest/state/latest-context-packet.json`
- `finance/state/latest-wake-decision.json`
- `finance/state/judgment-envelope.json`
- `finance/state/judgment-validation.json`
- `finance/state/finance-decision-report-envelope.json`
- `finance/state/finance-report-product-validation.json`
- `finance/state/finance-decision-log-report.json`
- `finance/state/report-delivery-safety-check.json`
- `finance/scripts/gate_evaluator.py`
- `finance/state/intraday-gate-config.json`
- `finance/state/decay-config.json`
- `finance/state/report-gate-state.json`
- `finance/scripts/event_watcher.py`
- `finance/scripts/price_fetcher.py`
- `finance/state/prices.json`

稳定归一化规则：
- watchlist 中的 crypto 可以写成 `BTC/USD`，确定性价格层使用 `BTC-USD`
- quote 消费方必须先归一 `change_pct` 与 `pct_change`
- watcher 身份应优先使用 `source_uid` / `canonical_wake_key`，而不是只看原始 `id`

---

## 一、使命与核心约束

**使命**：24/7 市场扫描 + 美股交易时段决策报告 + 非交易时段事件告警。系统必须嵌入 OpenClaw：scanner 和 report orchestrator 都是 OpenClaw cron surface，Python 只做确定性 feeder / normalizer / validator。

**反模式**：成为新闻标题的搬运工。每个报告必须有过滤、有判断、有增量。

**核心循环（active）**：

```
OpenClaw scanner cron
  → buffer observations
  → finance_worker.py
  → gate_evaluator.py
  → typed EvidenceRecord / ContextPacket / WakeDecision
  → OpenClaw report orchestrator
  → JudgmentEnvelope
  → product report validator
  → decision log
  → delivery safety gate
  → Discord announce
```

报告触发条件：
- **Urgency branch / immediate_alert**：由 `gate_evaluator.py` + `intraday-gate-config.json` 决定。当前默认 urgent 阈值是 `urgency ≥ 9`；该分支绕过 global cooldown 与 quiet hours，但仍受数据新鲜度守卫和 `alert_min_minutes_since_last` 约束。
- **Accumulated Signal STRONG**：多条观察形成连贯叙事，值得压缩输出。
- **Typed wake / threshold bridge**：canonical wake 若为 `ISOLATED_JUDGMENT_WAKE` 会走 wake dispatch；若 wake 只是 `PACKET_UPDATE_ONLY` 但 legacy intraday threshold 已通过，`gate_evaluator.py` 必须桥接到 active OpenClaw report orchestrator，而不是旧 renderer。

---

## 二、系统架构

```
确定性 feeder: price / Flex / enrichment / option risk / resolver
    ↓ 写入 finance/state/*.json
OpenClaw scanner cron: bounded web/source discovery
    ↓ 写入 finance/buffer/*.json
finance_worker.py: 去重 + 积分叠加 + 原子写入 scan state
    ↓
gate_evaluator.py: 衰减 + 阈值 + wake pipeline + report-orchestrator dispatch
    ↓
services/market-ingest: EvidenceRecord → Temporal Alignment → ContextPacket → WakeDecision
    ↓
OpenClaw cron finance-premarket-brief: JudgmentEnvelope + product report + decision log + safety
    ↓
OpenClaw announce delivery
```

**关键文件路径**：
- `finance/buffer/` — scanner 输出原始观察
- `finance/state/intraday-open-scan-state.json` — 全局累积状态（seen_ids + accumulated）
- `finance/state/report-gate-state.json` — 门控判决输出
- `finance/state/prices.json` — 确定性价格数据（yfinance）
- `finance/scripts/gate_evaluator.py` — 评分引擎
- `finance/scripts/finance_worker.py` — 缓冲处理
- `finance/scripts/price_fetcher.py` — 确定性价格获取
- `services/market-ingest/state/latest-context-packet.json` — active cognition packet
- `finance/state/judgment-envelope.json` — active judgment contract
- `finance/state/finance-decision-report-envelope.json` — active final report markdown
- `finance/state/report-input-packet.json` — deprecated compatibility view only；不得作为 cognition source

**数据源集成**（实际运行中）：
- **yfinance**：免费、无 key → provider quote snapshot / 收盘与日内快照字段（`price_fetcher.py`）。注意：`*/20` 是轮询节奏，不等于 tick-real-time 数据保证；必须读取 `quote_granularity` 与 `freshness_semantics`。
- **OpenClaw scanner web_search**：OpenClaw cron cognition surface → 主动搜索宏观、watchlist、unknown discovery。
- **IBKR Flex Web Service**：当前 portfolio/performance/NAV/options snapshot 替代方案，避免每天依赖 Client Portal brokerage login。
- **IBKR Client Portal API**：可选 snapshot source；默认 phone/TWS-priority，不长期占用同一 username 的 brokerage session。

**暂未集成**（key 缺失或未实现）：
- ~~Twelve Data~~：keychain 中无 `skill_twelve_data_api_key`
- ~~MarketAux~~：keychain 中无 `skill_marketaux_api_key`
- SEC / broad proxy / options flow 已作为 context evidence source 接入 typed packet；metadata-only SEC 标题不得作为交易支持证据。

---

## 三、报告类型（active semantics）

所有用户可见报告都由 OpenClaw cron `finance-premarket-brief` 输出。这个 job 名称是历史兼容名，不代表所有输出都可以叫“盘前/开盘”。标题必须由实际 window / report_class 决定。

### Short / Core / Immediate Thresholds

- `short` / `core` / `immediate_alert` 是 gate recommendation，不是旧 renderer 模板选择。
- 如果触发，`gate_evaluator.py` 只负责把报告请求派发给 OpenClaw report orchestrator。
- 最终报告仍必须通过 JudgmentEnvelope、product validator、decision log、safety gate。

### Decision Reports

- **定位**：把 typed packet 中的机会、风险、矛盾、持仓影响、未知探索压缩为可读决策上下文。
- **必须包含**：结论、为什么现在、市场机会雷达、未知探索、潜在机会/风险候选、期权与风险雷达、分层证据、矛盾与裁决、持仓影响、反证/Invalidators、下一步观察、数据质量、来源。
- **禁止**：`thresholds not met`、`Native Shadow`、raw ISO timestamp、raw Flex XML、account identifiers、内部 gate reason、直接交易执行指令。

### Health-only Reports

如果 safety gate 不通过，report orchestrator 只能输出系统状态，不得输出市场判断、watchlist、持仓影响、ticker 涨跌、新闻结论或交易建议。

---

## 四、时段定义（America/Chicago）

| 时段 | 时间范围 | 市场小时？ |
|------|----------|-----------|
| overnight | 19:00–03:30 | 否 |
| pre | 03:30–08:30 | 否 |
| open | 08:30–11:30 | ✅ |
| mid | 11:30–14:00 | ✅ |
| late | 14:00–15:00 | ✅ |
| post | 15:00–19:00 | ✅ |

时段决定阈值集合（market_hours vs off_hours）和评分权重。

---

## 五、评分体系

### 四维评分

| 维度 | 含义 | 满分 |
|------|------|------|
| **urgency** | 延迟是否会损失信息价值 | 10 |
| **importance** | 是否影响市场主线或 watchlist | 10 |
| **novelty** | 是否为新信息（对比 seen_ids） | 10 |
| **cumulative_value** | 是否与已有信号形成连贯更新 | 10 |

### 衰减机制

**连续衰减**（每次 gate_evaluator 运行）：
- 所有候选项的 urgency、importance、cumulative_value × `decay_factor`（默认 0.9）
- 任何一项核心分数跌破 `min_threshold`（1.5）则淘汰
- 豁免关键词项不参与衰减

**报告后衰减**（报告触发后）：
- 所有分数 × `post_report_decay_factor`（默认 0.7）
- 防止同一信号重复触发

### 豁免关键词
`assassination`、`nuclear`、`declaration of war`、`暗杀`、`核打击`、`宣战`
→ 这类事件 urgency 不衰减，直到被确认解决

---

## 六、门控阈值（Baseline defaults；runtime 以 config + calibration 为准）

| 报告类型 | 市场时段条件 | 非市场时段条件 |
|----------|-------------|--------------|
| immediate_alert | urgency ≥ 9，`alert_min_minutes_since_last ≥ 120` | urgency ≥ 9，`alert_min_minutes_since_last ≥ 240` |
| short | cv ≥ 20 且 ≥45min | cv ≥ 40 且 ≥60min |
| core | importance ≥ 30 且 ≥180min | importance ≥ 50 且 ≥240min |

**同发冲突**：若 short 和 core 同时满足，优先发 core（避免 short 循环锁死 core）

**数据陈旧守卫**：若 `last_scan_time` > 120min，强制 hold（防止用旧数据出报告）

**Runtime note**：
- 当前 active thresholds 不是只看这张表，而是由 `intraday-gate-config.json` 提供 baseline，再由 `gate_evaluator.py` 内的 calibration 逻辑做 runtime 调整。
- 因此报告里若要引用当前阈值，应优先看 `report-gate-state.json.thresholdsUsed`。

---

## 七、市场时段扫描节奏

| 时段 | 扫描频率 | 报告目标 |
|------|---------|---------|
| pre（盘前） | 每 20min | 固定 context report + threshold/wake 报告 |
| open/mid/late | 每 20min | 按 signal 触发，目标是少量有信息增量的决策报告 |
| post（盘后） | 每 20min | 按 signal 触发；标题不得误称开盘/盘前 |
| overnight | 4次/日（0, 7, 17, 20 CT） | 即时告警仅危机级事件 |

---

## 八、数据政策

### 价格新鲜度语义

- `price_fetcher.py` 输出的是 `provider_quote_snapshot`，不是逐 tick 实时行情。
- `fetched_at` 表示本地抓取时间；单个 quote 的 `as_of` 表示该 quote 快照写入时间；两者都不是交易所 tick timestamp。
- 下游 consumer 不得因为 cron 是 `*/20` 就假设价格数据必然 20 分钟内真实更新；必须在报告里按 snapshot / delayed / unavailable 语义表达。
- 如需严格实时 quote，应接入 IBKR Web API / websocket 或付费数据源，并单独处理 username session 冲突。

### 允许
- **Partial data**：数据不完整时允许报告，但必须在 Risks/Unknowns 中显式说明
- **推测性结论**：在 Core 报告中可包含，但必须标注为 Interpretation

### 禁止
- **伪造来源确认**：未实际获取的数据不得声称"成功"
- **旧快照复用**：不得将昨日或更旧的行情数据静默传入今日报告（必须标记为快照 + 时间戳）
- **虚假一致性**：涨跌/价格/百分比三项数学不自洽时，不得删除其中一项掩盖

---

## 九、报告质量标准

### 数值自洽
```
watchlist 中：最新价、涨跌额、涨跌幅 三者必须数学一致
（涨跌额 ≈ 最新价 − 前收盘，涨跌幅 ≈ 涨跌额 / 前收盘 × 100）
```
跨报告一致性：同一标的同一时间戳的价格在所有报告中应相同。

### 时间精度
- 报告 section header（盘前/盘中/盘后）必须与数据时间窗口匹配
- 数据时间戳应接近数据获取时刻，文件 mtime 应接近报告生成时刻
- 不得将盘前数据放入盘中报告，或反之

### 信息增量
- 同一 session 内各 short 报告之间应有新增信号
- 重复相同数值/结论是失败模式

### Fact / Interpretation / To Verify 分离（仅 Core 报告）
- **Fact**：可验证的数字、事件、公告
- **Interpretation**：对 Fact 含义的解读
- **To Verify**：未经确认的线索.watchlist.focus

---

## 十、已知的失败模式（Anti-Patterns）

| # | 模式 | 描述 |
|---|------|------|
| P1 | **模板完全复用** | 报告从历史文件复制，内容未更新日期/数值 |
| P2 | **旧快照跨日期复用** | 旧日期的价格数据被标为当日数据 |
| P3 | **API 静默降级** | 数据源失败时回退旧快照，不在 Risks/Unknowns 中声明 |
| P4 | **时间穿越** | 盘前报告包含盘后价格，或相反 |
| P5 | **数值污染** | 百分比字段包含模型名称等非数值字符 |
| P6 | **累积信号重复** | 多份报告含相同数值，无增量贡献 |
| P7 | **不可能日期** | 报告显示日期为非交易日（周六/周日） |

---

## 十一、Watchlist / Universe 语义

Active universe 以 `finance/state/watchlist-resolved.json` 为准。它由三层合成：
- IBKR Client Portal watchlists：登录可用时同步，失败时可使用 last-good cache。
- IBKR Flex holdings：无人值守的持仓/期权 underlying fallback。
- `finance/watchlists/core.json`：本地 pinned fallback，不再冒充 IBKR watchlist。

当前本地 pinned core tickers：
`AAPL`、`MSFT`、`NVDA`、`TSLA`、`GOOG`、`HIMS`、`IAU`、`MSTR`、`NFLX`、`ORCL`、`SMR`、`INTC`

辅助 market proxies：
`SPY`、`QQQ`、`BTC/USD`

---

## 十二、语言规范

- 所有面向用户输出：**中文主体框架 + 英文专有名词**（公司名、ticker、技术术语保留英文）
- 禁止：全英文报告、全中文无结构
- 报告内部：数字、ticker、时间 保持原始格式

---

## 十三、文件规范

- buffer 文件命名：`YYYY-MM-DD-{window}-{HHMM}.json`
- 报告文件命名：`YYYY-MM-DD_{report_type}_us.md`
- 所有 JSON 写入：先写 `.tmp`，再 `rename`（atomic write，防止状态损坏）
- seen_ids 上限：保留最近 200 条，超出截断

---

## 十四、配置（可调参数）

**衰减配置**（`state/decay-config.json`）：
```json
{
  "decay_factor": 0.9,
  "post_report_decay_factor": 0.7,
  "min_threshold": 1.5,
  "exempt_keywords": ["assassination", "nuclear", "declaration of war", ...]
}
```

**阈值配置**（`state/intraday-gate-config.json`）：
```json
{
  "thresholds": {
    "market_hours": { "short_cumulative_value": 20, ... },
    "off_hours": { "short_cumulative_value": 40, ... }
  }
}
```

阈值和衰减系数通过配置文件管理，scanner/report orchestrator 无需硬编码。
如果需要知道 **当前生效阈值**，优先读 `report-gate-state.json.thresholdsUsed`，不要把本文当作 runtime snapshot。

---

*Last updated: 2026-04-14 | Version: 4.0*
