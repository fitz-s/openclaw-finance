# RALPLAN Ingestion Fabric Phase 00: Review2 Intake And Master Plan Baseline

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Persist `docs/review2-04-17-2026.md` as the new main control document for the next large-scale OpenClaw Finance ingestion upgrade, and convert it into a phase ledger that preserves every major requirement through compaction and review.

This phase does not modify active ingestion/runtime behavior. It records the controlling review and establishes the implementation sequence.

## RALPLAN-DR Summary

### Principles

1. `review2-04-17-2026.md` supersedes prior planning for the upstream ingestion layer.
2. Never compress before provenance.
3. LLM scanner becomes query planner / scout / sidecar analyst, not canonical ingress.
4. Brave must be split into deterministic API lanes, not hidden behind generic `web_search`.
5. Every later phase requires RALPLAN + implementation + critic + verification + commit + push.

### Decision Drivers

1. Source acquisition is the real bottleneck, not report prose.
2. Current OpenClaw Brave adapter uses `web_search` with `llm-context`, and misses Brave News/Search/Answers lane distinctions.
3. Current evidence fabric improvements are useful, but review2 requires a deeper upstream source office and query/claim novelty system.

### Viable Options

Option A: Add Brave Answers directly to scanner.
- Pros: fast synthesis.
- Cons: violates provenance boundary and risks turning sidecar synthesis into authority.

Option B: Only improve current scanner prompt.
- Pros: low effort.
- Cons: keeps LLM scanner as canonical ingestion and repeats the current failure mode.

Option C: Build deterministic ingestion fabric: QueryPack -> SourceFetchRecord -> EvidenceAtom -> ClaimAtom -> ContextGap, with Brave lanes and source memory.
- Pros: matches review2 and fixes the structural issue.
- Cons: larger multi-phase implementation.

Selected: Option C.

Rejected: Option A | Brave Answers is sidecar-only, not canonical authority.
Rejected: Option B | prompt tuning cannot fix wrong substrate.

## Phase 00 Scope

- Track the source review2 file.
- Embed the full review text below.
- Add `ingestion-fabric-phase-ledger.json`.
- Add tests that verify full review preservation and phase coverage.
- Add critic artifact.
- Do not change active runtime behavior.

## Acceptance Criteria

- Full review2 text is embedded verbatim under markers.
- Ledger includes all major review2 requirements: Source Office, QueryPack, SourceFetchRecord, EvidenceAtom, ClaimAtom, ContextGap, Brave Web/News/LLM Context/Answers separation, query registry, lane watermarks, source memory, finance_worker reducer, follow-up slicing, parent market-ingest dependencies, rollout/rollback.
- Tests fail if critical concepts are removed.

## Full Source Review2

<!-- REVIEW2_04_17_2026_FULL_TEXT_BEGIN -->
现在真正的瓶颈不是“报告还不够好”，而是 OpenClaw Finance 还没有建立一个真正的 information office。
下游对象层已经很丰满了：Thesis Spine、CapitalAgendaItem、CapitalGraph、CommitteeMemo、reader bundle、Discord primary/thread seed 都在；但上游仍然是 LLM scanner 先搜、finance_worker.py 很早压缩、theme 去重、snapshot/proxy 充当近似真相、然后后端再努力重加工。repo README 也还把当前 source reality 写得很直白：主要是 yfinance quote snapshot、IBKR Flex / Client Portal、scanner web search、SEC / broad market / options proxies 这些输入，active path 里 finance_worker.py 仍然位于 typed ContextPacket 之前。

而 785f079 导出的 reviewer packets，反而把这个问题彻底暴露了出来。那批 packet 的 README 明确说：导出的 information acquisition snapshot 是 current sanitized finance/OpenClaw source state，不是 exact historical replay；而且五份最近报告里，只有 RF63A 一份标记了 operator_surface_available=true。更关键的是 RF63A 自己的 packet 里，source health 已经很难看：只有 8 个可见 source，freshness 分布是 fresh 1 / aging 1 / stale 1 / unknown 5，rights 则是 restricted 6 / ok 1 / unknown 1；source_atom_summary 和 claim_graph_summary 都只有 9 个对象，而且 8/9 还是 news_policy_narrative 这条 lane，示例 atom 里还出现了 source:unknown_web、source_class=untrusted_web、reliability_score=0.2、uniqueness_score=0.1。这不是“感觉上有点粗糙”，而是 repo 自己已经把“信息面太窄、太旧、太 narrative-heavy、太弱 provenance”写进 reviewer packet 了。

你附件里的诊断是对的，而且击中了真正的结构性问题：当前本机 OpenClaw 把 Brave 当 web_search provider 用，实际模式是 llm-context，并且在你这套 runtime 里它不支持 freshness/date filters；再叠加额度 402，scanner 会退化成对旧 state / 旧 narrative 的重复再解释，state/source-atoms/latest.jsonl 还体现出 11 行里 8 行是 unknown_web。更重要的是，附件已经给出了非常接近正确方向的改法：把 Brave 分层成 Web/News for discovery、LLM Context for reading、Answers for sidecar only，并把 scanner 从 canonical source ingestion 降级成 query planner / anomaly explainer / source scout / sidecar analyst。这一点我完全同意，但我要把它从“Brave patch”提升成一整套 Source-to-Claim Intelligence Fabric。

一、真正的问题不是“缺几个源”，而是 canonical substrate 放错了

现在 repo 里最错位的文件不是 report renderer，而是 finance_worker.py。它把 buffer observation 很早压成：

theme
urgency
importance
novelty
cumulative_value
summary
sources

然后靠 theme equality、substring、词重叠做 semantic dedup，还把 accumulated list 截成最近 50 条。这意味着 信息还没变成可追溯 claim，就先被压成了摘要对象。后面不管是 event_watcher.py 的 theme overlap 触发、还是 gate_evaluator.py 的 wake、还是 report/follow-up，都是围着这层扁平物在转。

event_watcher.py 进一步放大了这个问题。它的 watcher 更新，本质上仍是：

price move 过阈值；
或者新 observation 的 theme 跟已有 watcher 的 theme，前 3 个词 + 至少 2 个词重叠；
默认 7 天 TTL；
4 小时 rate limit。

这对“headline 级事件”有用，但对 暗流、peacetime 机会、跨 lane 弱信号积累 非常弱。因为它盯的是 theme 文本和价格，而不是 claim、证据谱系、source diversity、scenario relevance。

所以你现在遇到的“多轮重复和低效”，不是 Brave 一个 provider 的局部 bug，而是一个更深的错层：

scanner 仍是 canonical ingress
ingress 很早压成 summary
重复控制基于 theme text，不基于 claim novelty
source lane 太少，narrative lane 比例过高
point-in-time replay 不成立
follow-up 没有按 verb + handle 去做 evidence slicing

这就是为什么你越往后做，越容易出现一种假象：对象很多、surface 很花、thread 能问、board 能看，但核心信息还是低密度、重复、旧、来源窄。

二、主路径裁决：Finance Intelligence Ingestion Fabric

我只给一条主路径，不做第二第三个候选稀释注意力：

Finance Intelligence Ingestion Fabric

副标题：Deterministic Source Office → EvidenceAtom → ClaimGraph → ContextGap → Campaign OS

这条路的核心戒律只有一句：

Never compress before provenance.

在 provenance、lineage、event-time、rights、confidence 没固定之前，不允许把信息压成 summary/theme。

这条路不是“再加几个数据源”，也不是“换个更强模型”。它要同时解决五件事：

把 scanner 从 canonical ingestion 主体降级成 query planner / scout / sidecar analyst
把 source acquisition 变成多 lane 的 deterministic source office
把 canonical substrate 从 summary 改成 EvidenceAtom / ClaimAtom / ContextGap
把重复和低效，从 theme 去重改成 query registry + claim novelty + lane watermarks
把 peacetime / undercurrent 和 follow-up，都建立在 claim/evidence 上，而不是建立在摘要 prose 上
三、先讲 repo reality：现在哪些地方已经证明这条路是对的

你现在 repo 其实已经把“正确的下游架构”搭出来了，只是上游没跟上。

1. canonical authority 不在 finance repo 内部全闭合

parent-dependency-inventory.json 已经把真正 load-bearing 的 canonical 组件列出来了，而且它们大多在 parent OpenClaw workspace：

source_registry
source_promotion
semantic_normalizer
temporal_alignment
packet_compiler
wake_policy
judgment_validator
以及对应 schema

这说明：真正的 canonical ingestion fabric，本来就该跨 finance repo 和 parent workspace 设计，而不是只在 finance repo 里打补丁。

2. 官方 gap review 还停在 telemetry 调优层

runtime-gap-review.json 目前显式 unresolved gap 还是：

ibkr_client_portal_watchlist_sync_not_fresh
parent_market_ingest_dependency_external_to_repo

并把下一步 candidate 主要写成 telemetry 调 report delta density / wake usefulness，而不是重做 upstream ingestion。也就是说，当前 repo 自己“正式承认”的下一个动作，仍然过于靠下游。这个判断现在已经不够了。

3. 现有 scripts tree 证明下游多、上游少

最新 main 的 scripts/ 里，你已经有：

capital_agenda_compiler.py
capital_graph_compiler.py
committee_memo_merge.py
finance_discord_report_job.py
finance_report_reader_bundle.py

但看不到：

source_atom_compiler.py
claim_graph_compiler.py
context_gap_compiler.py
brave_news_search_fetcher.py
brave_web_search_fetcher.py
brave_llm_context_fetcher.py
brave_answers_sidecar.py
undercurrent_compiler.py

这正是现在系统的真实剖面：消费层和投影层很多，证据 fabric 和 deterministic ingress 层还没真正站起来。

四、最佳设计：六层架构
Layer 0 — Authority split：先把权责边界写死
Parent OpenClaw workspace 负责
source registry / source health
source promotion / source deactivation
temporal alignment
semantic normalization
packet compiler
wake policy
judgment validator
canonical schemas
finance repo 负责
deterministic finance fetchers
lane-specific parsers
atom/claim/gap compilers
undercurrent/campaign compilers
operator/report/follow-up consumers

这一步是为了避免实现者误以为“只改 finance repo 就能完成 canonical ingestion fabric”。

Layer 1 — Source Office：把 source acquisition 从“自由搜索”变成六条 deterministic lanes

我建议六条 lane，和你附件的方向一致，但扩大成完整 operating model。

1. market_structure

目标：不是 HFT/L3，而是比现在 yfinance snapshot 高一个量级的 point-in-time market context。
当前 price_fetcher.py 明写自己只是 yfinance 的 provider_quote_snapshot，不是 tick-real-time feed；options_flow_proxy_fetcher.py 也明写是 conservative proxy。它们都该保留，但只能是 lane 内的 fallback / proxy，不再能被误读为近似真相。

2. corp_filing_ir

目标：从现在的 current SEC atom discovery，升级成真正的 filing / IR claims lane。
当前 sec_discovery_fetcher.py 只是抓 SEC current filings atom feed 上少数表单，默认还是 8-K / 4 / SC 13D / SC 13G；sec_filing_semantics.py 也还是 conservative heuristic classification。它们可以继续做 discovery trigger，但不能继续充当 corp/fundamental intelligence 的主体。

3. news_policy_narrative

目标：把新闻从“摘要源”升级成 event intelligence lane。
你附件对 Brave 的三层分工是对的。Brave Web Search 和 Brave News Search 适合 discovery，LLM Context 适合 reading，Answers 只能做 sidecar。Brave 官方文档当前明确支持：

/res/v1/web/search：freshness、date range、search operators
/res/v1/news/search：freshness、extra snippets、operators、Goggles
/res/v1/llm/context：当前官方文档也列出 freshness/date range
/v1/chat/completions：Brave Answers，OpenAI-compatible

也就是说，Brave 平台能力本身并不弱；真正弱的是当前 OpenClaw 里把它包装成了一个 web_search / llm-context 抽象，没把这些能力 deterministic 地接到 finance lanes。 这正好对应你附件里指出的 runtime 限制与额度爆掉问题。

4. real_economy_alt

目标：真正服务 peacetime opportunity 和 undercurrent。
这条 lane 当前几乎是空的，只能靠 scanner narrative 间接碰到。它应该以后容纳：

job postings
pricing
traffic
shipping/customs
power/weather/disaster
app/web demand
supply-chain proxies
5. human_field_private

目标：吸收合规 private research，而不是碰任何越线信息。
只能是付费研究、用户自己的 confidential notes、expert transcript、field memo、渠道纪要、meeting notes 的合规 derived context，不允许 MNPI。

6. internal_private

目标：把 OpenClaw 真正独特的优势拉满。
这里包括：

watch intent
portfolio attachment
capital buckets
old committee memos
historical outcomes
old thread 的 unresolved unknowns
own thesis notes

外部产品做不到这条 lane 的深度；这是你真正能建立私人 information edge 的地方。

Layer 2 — Source Registry 2.0：每个 source 都要有 lane-specific operating contract

不要再全局用一个 stale knob。
每条 source 至少带这些字段：

from pydantic import BaseModel
from typing import Literal

class SourceSpec(BaseModel):
    source_id: str
    lane: Literal[
        "market_structure",
        "corp_filing_ir",
        "news_policy_narrative",
        "real_economy_alt",
        "human_field_private",
        "internal_private",
    ]
    modality: Literal["text", "table", "event", "timeseries", "transcript", "image"]
    asset_horizon: Literal["intraday", "multi_day", "quarterly", "structural"]
    freshness_budget_sec: int
    expected_latency_sec: int
    coverage_universe: list[str]
    reliability_prior: float
    uniqueness_prior: float
    point_in_time_policy: str
    compliance_class: Literal["public", "licensed_restricted", "internal_private", "unknown"]
    redistribution_policy: Literal["raw_ok", "derived_only", "none", "unknown"]
    promotion_policy: Literal["primary", "secondary", "sidecar_only", "disabled"]
这里的关键变化
Reuters 跟 SEC current feed 的 freshness budget 不一样
yfinance snapshot 跟 ThetaData/ORATS 的 authority level 不一样
Brave Answers 要写成 sidecar_only
options_flow_proxy_fetcher 要被 registry 显式标记成 proxy/fallback
unknown_web 必须从 source registry 角度被看作“低 reliability + 低 uniqueness + high audit burden”
Layer 3 — Evidence Fabric：把 canonical substrate 从 summary 改成 atoms/claims/gaps

这是本次升级的核心，不做这层，其他都会漂。

A. QueryPack

scanner 不再自由搜，而是产出 query packs。

from pydantic import BaseModel
from typing import Literal

class QueryPack(BaseModel):
    pack_id: str
    campaign_id: str | None
    lane: Literal[
        "market_structure",
        "corp_filing_ir",
        "news_policy_narrative",
        "real_economy_alt",
        "human_field_private",
        "internal_private",
    ]
    purpose: Literal[
        "source_discovery",
        "source_reading",
        "claim_closure",
        "followup_slice",
    ]
    query: str
    freshness: str | None = None      # pd / pw / pm / last_24h ...
    date_after: str | None = None
    date_before: str | None = None
    allowed_domains: list[str] = []
    required_entities: list[str] = []
    max_results: int = 10
    authority_level: Literal["canonical_candidate", "sidecar_only"] = "canonical_candidate"
    forbidden: list[str] = []
这一步的本质

LLM 不再做第一层采集主体。
它只做：

query planner
anomaly explainer
source scout
sidecar analyst

这和你附件的方向完全一致，但我把它正式提升成 canonical contract。

B. SourceFetchRecord

任何 fetcher 先写 fetch record，不直接写 summary。

class SourceFetchRecord(BaseModel):
    fetch_id: str
    pack_id: str
    source_id: str
    lane: str
    endpoint: str
    request_params: dict
    fetched_at: str
    status: Literal["ok", "partial", "rate_limited", "failed"]
    quota_state: str | None = None
    result_count: int = 0
    watermark_key: str
C. EvidenceAtom

任何结果先落 atom。

class EvidenceAtom(BaseModel):
    atom_id: str
    fetch_id: str
    source_id: str
    lane: str
    entity_ids: list[str]
    symbol_candidates: list[str]
    published_at: str | None
    observed_at: str | None
    ingested_at: str
    event_time: str | None
    modality: str
    title: str | None
    url: str | None
    raw_ref: str | None              # 内部 vault ref
    safe_excerpt: str | None         # 仅当 rights 允许
    language: str | None
    rights: str
    compliance_class: str
    reliability_score: float
    uniqueness_score: float
    freshness_budget_sec: int
    point_in_time_hash: str
D. ClaimAtom

atom 再派生成 claim。

class ClaimAtom(BaseModel):
    claim_id: str
    atom_id: str
    subject: str
    predicate: str
    obj: str | None = None
    magnitude: float | None = None
    unit: str | None = None
    direction: str | None = None
    horizon: str | None = None
    certainty: Literal["weak", "medium", "strong"]
    event_class: str
    supports: list[str] = []
    contradicts: list[str] = []
    capital_relevance_tags: list[str] = []
    why_it_matters_tags: list[str] = []
E. ContextGap

unknown 不能再停在口头 “To Verify”。

class ContextGap(BaseModel):
    gap_id: str
    campaign_id: str
    missing_lane: str
    why_load_bearing: str
    weak_claim_ids: list[str]
    suggested_source_ids: list[str]
    cost_of_ignorance: float
这一步的本质

从此之后，系统第一次能显式回答：

我知道什么
我是从哪知道的
我不知道什么
这个未知为什么重要
应该去哪条 lane 补

这是报告密度提升的唯一正道。

Layer 4 — Repetition Control：把“多轮重复和低效”从文本层，挪到 query/claim/source 层解决

你现在的重复，根源不是 prompt 不够聪明，而是系统没有真正的 source memory / query memory / lane watermarks / claim novelty accounting。

A. query_registry.jsonl

记录每一条 query pack 的历史产出。

class QueryRunRecord(BaseModel):
    query_hash: str
    lane: str
    fetched_at: str
    domains_seen: list[str]
    result_urls: list[str]
    novel_claim_count: int
    repeated_claim_count: int
    fresh_result_ratio: float
    quota_cost: float | None = None
    outcome: Literal["high_yield", "low_yield", "stale_repeat", "failed"]
B. lane_watermarks.json

每个 lane、实体、域名、主题，都要有最近一次有效 ingest 的 watermark。

class LaneWatermark(BaseModel):
    lane: str
    entity_key: str
    domain: str | None
    last_effective_fetch_at: str
    last_novel_claim_at: str | None
    cooldown_until: str | None
C. source_memory_index.json

不是按 theme 做 dedup，而是按 entity + event_time + source_domain + claim predicate 做 dedup / saturation accounting。

def should_skip_query(pack: QueryPack, recent: list[QueryRunRecord]) -> bool:
    same_lane = [r for r in recent if r.lane == pack.lane]
    if not same_lane:
        return False
    latest = same_lane[-1]
    return (
        latest.outcome in {"stale_repeat", "low_yield"}
        and latest.fresh_result_ratio < 0.2
        and latest.novel_claim_count == 0
    )
D. claim novelty 取代 theme novelty

现在 finance_worker.py 的 novelty 是在 summary/theme 层定义的，这是错层。应该改成：

def claim_novelty_score(new_claim: ClaimAtom, existing_claims: list[ClaimAtom]) -> float:
    overlaps = [
        c for c in existing_claims
        if c.subject == new_claim.subject
        and c.predicate == new_claim.predicate
        and c.horizon == new_claim.horizon
    ]
    if not overlaps:
        return 1.0
    same_direction = sum(1 for c in overlaps if c.direction == new_claim.direction)
    return max(0.0, 1.0 - 0.25 * same_direction)
关键意义
同样的 Reuters headline 不会一遍遍被当“新信息”
同样 domain、同样 event class、同样 claim predicate 的重复，不会再制造 busy work
PACKET_UPDATE_ONLY 可以只更新 campaign / undercurrent stage，而不是再生成一轮 narrative
Layer 5 — Brave lanes：把你附件里的方向正式做成 deterministic ingress，而不是继续依赖 web_search 抽象

这是当前最直接、最快能打到痛点的升级包。

关键裁决

不要再把 Brave 当 “LLM agent 的 web_search provider”。
应该直接把 Brave HTTP API 接成 finance deterministic fetchers。

原因很简单：

你附件里说当前 OpenClaw runtime 用的是 llm-context 模式，且不支持 freshness/date filters，额度还爆了，导致 scanner 回退成旧 narrative。
但 Brave 官方文档当前已经给出：
web/search 支持 freshness/date range
news/search 支持 freshness、extra snippets、operators、Goggles
llm/context 当前文档也列出 freshness/date range
Answers 是独立 OpenAI-compatible endpoint

这说明：瓶颈不是 Brave 平台能力，而是当前 OpenClaw Brave adapter / mode / quota policy / abstraction 方式。

A. brave_news_search_fetcher.py

第一层 discovery，用于 news_policy_narrative。

# scripts/brave_news_search_fetcher.py
import os, json, requests, hashlib, datetime
from pathlib import Path

API = "https://api.search.brave.com/res/v1/news/search"

def fetch_brave_news(pack: QueryPack) -> list[dict]:
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": os.environ["BRAVE_API_KEY"],
    }
    params = {
        "q": pack.query,
        "freshness": pack.freshness or "pd",
        "count": pack.max_results,
        "country": "US",
        "search_lang": "en",
        "extra_snippets": "true",
    }
    r = requests.get(API, headers=headers, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    out = []
    for item in data.get("results", []):
        out.append({
            "fetch_id": hashlib.sha1(f"{pack.pack_id}:{item.get('url')}".encode()).hexdigest()[:16],
            "pack_id": pack.pack_id,
            "lane": "news_policy_narrative",
            "source_id": f"domain:{item.get('meta_url', {}).get('hostname','unknown')}",
            "endpoint": "brave/news/search",
            "query": pack.query,
            "freshness": pack.freshness,
            "title": item.get("title"),
            "url": item.get("url"),
            "description": item.get("description"),
            "age": item.get("age"),
            "published": item.get("page_age"),
            "fetched_at": datetime.datetime.utcnow().isoformat() + "Z",
            "authority_level": "canonical_candidate",
            "no_execution": True,
        })
    return out
规则
只做 discovery，不做 synthesis
所有结果先进 SourceFetchRecord / EvidenceAtom
site operators、allowed domains、freshness 全在 query pack 控制
没有 raw answer synthesis
B. brave_web_search_fetcher.py

用于 corp_filing_ir / real_economy_alt / source discovery。

规则
site-specific only
strict date filtering
结果先进 atom，不进 report
对 unknown_web 设置低 reliability prior，除非后续 cross-lane confirmation 把它抬上去
C. brave_llm_context_fetcher.py

只用于 reading selected candidates，不准 first-pass 扫。

# scripts/brave_llm_context_fetcher.py
def fetch_brave_context(pack: QueryPack) -> dict:
    assert pack.purpose == "source_reading"
    assert pack.authority_level in {"canonical_candidate", "sidecar_only"}
    # 只允许对 selected URL / selected topic 调
    ...
    return {
        "pack_id": pack.pack_id,
        "endpoint": "brave/llm/context",
        "selected_url": "...",
        "freshness_filter_supported": True,  # 直接按官方 API 能力实现
        "status": "ok",
        "safe_excerpt_candidates": [...],
    }
关键点
不再继承当前 OpenClaw web_search provider 的局限
直接走 Brave HTTP API，按 finance fetcher 需求使用
只服务已知 URL / 已知主题 / follow-up / deep-dive
D. brave_answers_sidecar.py

只做 sidecar，不能当 canonical raw authority。

class BraveAnswerSidecar(BaseModel):
    answer_id: str
    campaign_id: str
    question: str
    answer_text: str
    citations: list[dict]
    derived_claim_candidates: list[dict]
    confidence: Literal["sidecar_only"] = "sidecar_only"
    not_authority: bool = True
    no_execution: bool = True
规则
answer text 只能进 DerivedContext / hypothesis
只有 citations 才能转成 EvidenceAtom candidates
没 citations，不准给 report authority
不准直接推动 wake
不准直接生成 actionability / trade / sizing

这和你附件的建议完全一致，但我把它升级成了正式 contract。

Layer 6 — Campaign / Undercurrent OS

这一层不是本轮唯一重点，但必须承接前面的 context fabric，否则 peacetime 机会永远抓不住。

关键变化

当前 event_watcher.py 盯的是 theme+price。
升级后应该盯的是：

claim persistence
cross-lane confirmation
source diversity
contradiction load
capital relevance
scenario attachment
新对象：UndercurrentCard
class UndercurrentCard(BaseModel):
    undercurrent_id: str
    theme_or_chain: str
    persistence_score: float
    acceleration_score: float
    cross_lane_confirmation: float
    source_diversity: int
    contradiction_load: float
    capital_relevance: float
    linked_campaign_ids: list[str]
    promotion_reason: str
    kill_conditions: list[str]
    freshness_health: float
    known_unknowns: list[str]
关键语义

PACKET_UPDATE_ONLY 不再等于“对你不可见”。
它应该等于：

不一定打扰你
但一定更新 Peacetime Board / Risk Board / campaign stage

这才是真正的 peacetime edge。

五、文件级改动清单
A. finance repo 内必须改的
1. scripts/finance_worker.py

降级为 compatibility reducer。
它不再是 canonical substrate，只负责：

接收 atoms/claims/gaps 的派生摘要
写 legacy observation bridge
保持旧消费者在 migration 期不炸
2. scripts/native_scanner_market_hours.py

从 LLM-first scanner 改成 ingress orchestrator。
职责变成：

调 query planner
执行 deterministic fetchers
记录 source batch manifests
写 atoms/claims/gaps
最后才写 scanner-derived summary
3. scripts/event_watcher.py

从 theme/price watcher 改成 claim/undercurrent watcher。
保留 price threshold 作为一个 signal，不再是主轴。

4. scripts/price_fetcher.py

重命名或包裹成 market_structure lane fallback。
必须在输出里强制：

authority_level=fallback_snapshot
provider_quote_snapshot=true
point_in_time_confidence_penalty
5. scripts/options_flow_proxy_fetcher.py

明确降级成 proxy lane。
输出必须显式：

proxy_only=true
freshness_semantics=delayed_or_incomplete
not_primary_iv_surface=true
6. scripts/sec_discovery_fetcher.py

保留为 corp_filing_ir 的 discovery trigger。
不要再把它当 deep filing lane 本体。

7. 新增
scripts/query_pack_planner.py
scripts/brave_news_search_fetcher.py
scripts/brave_web_search_fetcher.py
scripts/brave_llm_context_fetcher.py
scripts/brave_answers_sidecar.py
scripts/source_fetch_registry.py
scripts/evidence_atom_compiler.py
scripts/claim_atom_compiler.py
scripts/context_gap_compiler.py
scripts/source_health_monitor.py
scripts/source_memory_index.py
scripts/undercurrent_compiler.py
scripts/finance_followup_context_router.py
scripts/finance_campaign_cache_builder.py
8. scripts/finance_llm_context_pack.py

scanner pack 改成 query-planner pack；
report_followup pack 强制接受：

verb
selected_handle
secondary_handle（compare 时）

现在它虽然已经有 follow-up role 和 starter queries，但 pack 本身还不是真正的 handle-sliced contract。

9. scripts/finance_report_reader_bundle.py

加入：

claim ids
lane coverage summary
source health summary
context gaps
follow-up slices index

现在 starter queries 是自动从 object cards 生长出来的，这不够。它必须把 evidence slices 显式化。

10. scripts/finance_followup_answer_guard.py

从“结构 guard”升级到“evidence slice coverage guard”。
现在它主要是检查 verb、section、forbidden execution；下一步要检查：

answer 是否绑定 slice_id
selected handle 是否真有对应 claim/evidence
compare/scenario 是否带到 secondary handle / scenario exposure slice

11. scripts/finance_decision_report_render.py

主 operator surface 改成：

discord_live_board_markdown
discord_peacetime_board_markdown
discord_risk_board_markdown
campaign_cards

长 markdown 留作 artifact_record_markdown。
这一步不是本轮唯一焦点，但要顺手把 source health、known unknowns、lane coverage 放进 operator surface。

B. parent OpenClaw workspace 必须改的

这些是 parent-dependency-inventory.json 已经写出来的 load-bearing dependencies，不改不行。

1. services/market-ingest/config/source-registry.json

升级成 Source Registry 2.0

2. services/market-ingest/source_promotion.py

支持：

source lane promotion/deactivation
source health penalties
proxy vs primary 区分
3. services/market-ingest/semantic_normalizer.py

从 summary-normalizer 升级成 atom/claim-aware normalizer

4. services/market-ingest/temporal_alignment/alignment.py

引入 lane-specific freshness budget、event_time vs published_at vs ingested_at

5. services/market-ingest/packet_compiler/compiler.py

packet 不再只消费 summary/legacy observation；必须能消费 claims/gaps/undercurrents

6. services/market-ingest/wake_policy/policy.py

wake scoring 加入：

source diversity
claim novelty
contradiction load
undercurrent promotion
context-gap severity
7. services/market-ingest/validator/judgment_validator.py

强制高影响 judgment 绑定 claim ids / context gaps / lane coverage

六、新的 contracts 文档

我建议你一次性把 contract 层补齐，不然后面实现者一定会在不同层写出不同的“半真相”。

新增：

docs/openclaw-runtime/contracts/source-registry-v2-contract.md
docs/openclaw-runtime/contracts/query-pack-contract.md
docs/openclaw-runtime/contracts/source-fetch-record-contract.md
docs/openclaw-runtime/contracts/evidence-atom-contract.md
docs/openclaw-runtime/contracts/claim-atom-contract.md
docs/openclaw-runtime/contracts/context-gap-contract.md
docs/openclaw-runtime/contracts/source-health-contract.md
docs/openclaw-runtime/contracts/undercurrent-card-contract.md
docs/openclaw-runtime/contracts/followup-context-slice-contract.md
docs/openclaw-runtime/contracts/source-roi-contract.md
七、一个最关键的代码替换：把 finance_worker 从 ingestion 主体，降成 reducer

你现在最大的“重复和低效”，就是 finance_worker.py 还在扮演一个本不该属于它的角色。
我建议的迁移方式不是直接删它，而是先 parallel write。

新主链
query planner
  -> deterministic fetchers
  -> source fetch records
  -> evidence atoms
  -> claim atoms
  -> context gaps
  -> undercurrent/campaign compilers
  -> legacy finance_worker reducer
  -> packet compiler / wake / report
reducer 伪代码
# scripts/finance_worker.py (future role)
def reduce_claims_for_legacy_observation(
    claims: list[ClaimAtom],
    gaps: list[ContextGap],
) -> list[dict]:
    grouped = group_claims_by_theme_entity(claims)
    observations = []
    for group in grouped:
        observations.append({
            "id": f"legacy-{group.key}",
            "ts": group.latest_event_time,
            "theme": group.theme,
            "summary": compress_claims(group.claims),
            "importance": score_importance(group.claims),
            "novelty": score_group_novelty(group.claims),
            "sources": sorted({c.atom_id for c in group.claims})[:5],
            "known_unknowns": [
                g.gap_id for g in gaps if g.campaign_id == group.campaign_id
            ][:3],
        })
    return observations
这里的关键

不是让 finance_worker 消失，而是让它失去 canonical authority。
这一步会极大降低迁移风险。

八、如何修掉 follow-up 的“答非所问”

当前 follow-up 的根问题不是 context 太少，而是 切片不对。
finance_report_reader_bundle.py 虽然已经有 starter questions；finance_followup_answer_guard.py 也已经有 verb 和结构 guard；但如果没有 selected_handle + slice_id + claim lineage，答案还是会 generic。

新的 router
# scripts/finance_followup_context_router.py
VERB_SLICES = {
    "why": [
        "campaign_projection",
        "recent_claims",
        "source_health",
        "promotion_reason",
        "event_timeline",
    ],
    "challenge": [
        "countercase_memo",
        "invalidator_cluster",
        "contradiction_claims",
        "denied_hypotheses",
        "freshness_risks",
    ],
    "compare": [
        "capital_graph_slice",
        "displacement_case",
        "bucket_competition",
        "portfolio_attachment",
    ],
    "scenario": [
        "scenario_exposure_slice",
        "hedge_coverage",
        "crowding_risk",
        "linked_campaigns",
    ],
    "sources": [
        "source_atoms",
        "claim_lineage",
        "rights_and_redaction",
        "freshness_by_lane",
    ],
}

def build_followup_context(bundle, verb, primary_handle, secondary_handle=None):
    required = VERB_SLICES[verb]
    slice_bundle = bundle.select(required, primary=primary_handle, secondary=secondary_handle)
    missing = slice_bundle.missing_required()
    if missing:
        return {
            "status": "insufficient_data",
            "missing": missing,
            "context_gaps": bundle.lookup_context_gaps(primary_handle, missing),
        }
    return slice_bundle
关键点
不再喂 raw thread history
先命中 deep-dive cache
缺 lane 时显式返回 insufficient_data + context gaps

这一步会直接把“答非所问”从大模型风格问题，变成一个 deterministic routing 问题。

九、最重要的测试集

你要求“多给一些信息，不只是想法，改动什么，怎么动，代码片段，以防止实现时偏离设计理念”。
真正防偏离的，不只是文档，还有 tests。
我建议你至少先补这批：

def test_finance_worker_parallel_writes_atoms_before_summary(): ...
def test_brave_news_fetcher_respects_freshness_and_domain_filters(): ...
def test_brave_llm_context_never_runs_as_first_pass_discovery(): ...
def test_brave_answers_sidecar_never_promotes_without_citations(): ...
def test_query_registry_suppresses_zero_yield_repeat_queries(): ...
def test_claim_dedup_uses_subject_predicate_horizon_not_theme_text(): ...
def test_packet_update_only_updates_peacetime_board_without_alert_spam(): ...
def test_followup_compare_requires_selected_secondary_handle(): ...
def test_followup_sources_returns_claim_lineage_and_rights_notes(): ...
def test_reviewer_packet_replays_report_time_claims_not_current_source_state(): ...
def test_operator_board_discloses_known_unknowns_and_lane_coverage(): ...
def test_untrusted_web_atom_never_promotes_without_cross_lane_confirmation(): ...
这些 tests 的意义

不是让 CI 看起来更专业，而是锁住设计理念：

canonical substrate 先是 atoms/claims
Brave Answers 不是 authority
重复控制看 claim novelty，不看 theme similarity
peacetime board 是一等 surface
follow-up 必须是 handle-sliced
reviewer packet 必须 time-travel，而不是 current snapshot masquerading as history
十、rollout 方案
Phase 1 — parallel write，不切主链
新增 QueryPack / SourceFetchRecord / EvidenceAtom / ClaimAtom / ContextGap
old observation 继续写
finance_worker.py 继续服务旧消费者
不改 wake
Phase 2 — Brave lanes / source registry / query registry
brave_news_search_fetcher.py
brave_web_search_fetcher.py
brave_llm_context_fetcher.py
brave_answers_sidecar.py
lane watermarks / query registry / source health monitor
Phase 3 — event_watcher / undercurrent / peacetime board
watcher 改成 claim/undercurrent aware
PACKET_UPDATE_ONLY 更新 board，不一定 alert
Phase 4 — follow-up slices
report_followup 需要 verb + handle
prebuilt deep-dive cache
insufficient_data + ContextGap
Phase 5 — canonical packet/wake/judgment 接新 substrate
parent packet_compiler
wake_policy
judgment_validator
十一、回滚与 blast radius
blast radius 最大
parent packet_compiler
wake_policy
judgment_validator
source_registry

因为这些是 canonical authority chain。

blast radius 中等
finance_worker.py
event_watcher.py
finance_llm_context_pack.py
finance_report_reader_bundle.py
finance_followup_answer_guard.py
blast radius 较低
Brave deterministic fetchers
query registry
source health monitor
source ROI tracker
reviewer packet enrichment
回滚策略
atoms/claims/gaps 停用 consumer，保留 parallel writes
finance_worker 继续出 legacy observation
boards fallback 到 current discord_primary_markdown
follow-up fallback 到 current bundle digest
Brave deterministic fetchers 关掉后，旧 scanner 仍能跑

这能保证你不会因为升级 ingest plane，把整个可用系统炸穿。

十二、现在明确不该做的事
不要继续把 free-form scanner web_search 当 canonical source ingestion。
你附件已经把这个问题说透了，我完全同意。
不要把 Brave Answers 直接塞进 hot path。
它可以做 sidecar，但不能做 EvidenceAtom authority。Brave 官方文档把它定义成 OpenAI-compatible answer surface，这正说明它适合 synthesis，不适合 canonical raw evidence。
不要继续让 yfinance / Nasdaq proxy 以“默认真相”的姿态存在。
它们是 fallback/proxy lane，不是 primary market truth。
不要继续在 theme/summary 层做 novelty 和 dedup。
这是现在多轮重复和低效的直接机制根源。
不要把 reviewer packets 误认为你已经有 exact replay。
785f079 的 README 已经明确说 current sanitized source state 不是 historical replay。这个缺口必须正视。
十三、最后给你一句真正指导实现者的设计戒律

OpenClaw Finance 的下一次跃迁，不是把 scanner 再写聪明一点，也不是把报告再写顺一点，而是把整个系统从 LLM-scanner-first 的摘要机器，升级成 deterministic source office + evidence/claim fabric + campaign OS。

只有这样：

peacetime 机会才不会等 headline 才存在
暗流涌动才不会只在主题词里模糊发热
follow-up 才能回到真正的证据切片
reviewer packets 才能真正 time-travel replay
你的报告密度，才会由 信息质量 决定，而不是由 prose 技巧决定

你附件里的 Brave 分层建议是对的，但还不够大。
真正的最佳设计不是 “把 Brave 接好”，而是 把 Brave 只是当成六条 source lanes 里的一条 discovery/read/synthesis 基础设施，然后重建整个 canonical substrate。
做到这一层，系统才会从“对低质信息做更强推理”，变成真正开始拥有 information edge
<!-- REVIEW2_04_17_2026_FULL_TEXT_END -->

## Critic Review

Deferred to `docs/openclaw-runtime/critics/ingestion-fabric-phase-00-implementation-critic.md` after implementation.
