# Architecture

> **维护规则**：每次对项目做任何改动（新增功能、重构、删除模块）后，必须同步更新本文件。
> 本文件与 `DESIGN_INTENT.md` 共同构成项目的"活文档"，优先级等同于源代码。

---

## 总览

```
Browser (SPA)
    │  REST/JSON
    ▼
FastAPI  (main.py)
    ├── Middleware: RequestLoggingMiddleware
    ├── /user/*        ← UserProfile 管理
    ├── /sources/*     ← 核心：来源摄取 + 聚类
    ├── /search/*      ← 学术搜索 (arXiv / Semantic Scholar)
    └── /kb/*          ← 遗留论文知识库（向后兼容）

Services Layer
    ├── tagging/       ← LLM 语义分析
    ├── clustering/    ← Jaccard 标签聚类
    ├── llm/           ← 多 LLM provider 抽象
    ├── search/        ← 外部搜索 API 封装
    └── knowledge/     ← 持久化存储

Storage: JSON files in data/  (gitignored, runtime only)
Logs:    logs/*.log            (gitignored, runtime only)
```

---

## 目录结构

```
academic-kb/
│
├── ARCHITECTURE.md          ← 本文件（架构活文档）
├── DESIGN_INTENT.md         ← 设计意图文档
├── CLAUDE.md                ← Claude Code 工作规程
│
├── main.py                  ← FastAPI 入口，lifespan 事件，路由挂载
├── config.py                ← Pydantic Settings，从 .env 读取
├── logger.py                ← 日志系统：console(INFO+) + 3个文件 handler
├── middleware.py            ← HTTP 请求/响应日志中间件，附 X-Request-Id
│
├── api/
│   ├── models/
│   │   ├── source.py        ← Source, TagSet, SourceIngest, Cluster
│   │   ├── user.py          ← UserProfile, ProfileSummary
│   │   └── knowledge.py     ← Paper, KnowledgeBase（遗留）
│   └── routes/
│       ├── sources.py       ← /sources  主核心路由
│       ├── user.py          ← /user/profile
│       ├── search.py        ← /search/arxiv  /search/semantic_scholar
│       └── knowledge.py     ← /kb/*（遗留，保持向后兼容）
│
├── services/
│   ├── llm/
│   │   ├── base.py          ← BaseLLM 抽象类：chat(system, user) -> str
│   │   ├── __init__.py      ← get_llm(provider?) 工厂，带自动降级
│   │   ├── anthropic_service.py  ← claude-sonnet-4-6
│   │   ├── openai_service.py     ← gpt-4o-mini
│   │   └── gemini_service.py     ← gemini-1.5-flash
│   ├── tagging/
│   │   └── tagger.py        ← analyse_source()：类型检测→抓取→LLM分析
│   ├── clustering/
│   │   └── clusterer.py     ← build_clusters()：Jaccard 算法 + LLM 命名
│   ├── search/
│   │   ├── arxiv_service.py
│   │   └── semantic_scholar.py
│   └── knowledge/
│       ├── source_store.py  ← Source/Cluster JSON 持久化
│       └── kb_service.py    ← 遗留 Paper KB 操作
│
├── static/
│   ├── index.html           ← 单页应用骨架
│   ├── style.css            ← 全部样式（CSS 变量 + 组件）
│   └── app.js               ← 状态管理、渲染、API 调用
│
├── data/                    ← 运行时数据（.gitignore 屏蔽）
│   ├── profile.json
│   └── knowledge_base/
│       ├── sources.json     ← 主数据库：sources + clusters
│       └── kb.json          ← 遗留论文库
│
├── logs/                    ← 日志文件（.gitignore 屏蔽）
│   ├── app_YYYYMMDD.log     ← 全量 DEBUG 日志
│   ├── llm_YYYYMMDD.log     ← 仅 LLM 调用
│   └── search_YYYYMMDD.log  ← 仅搜索调用
│
├── docs/
│   └── github_api_manual.md
└── scripts/
    ├── check_secrets.sh / .ps1   ← pre-commit 安全钩子
    └── install_hooks.bat
```

---

## 核心数据流：来源摄取

```
POST /sources  { content: "2307.09288", hint?: "..." }
       │
       ▼
tagger.py :: analyse_source()
  1. _detect_type(content)
     → "arxiv_id" | "arxiv_url" | "doi" | "url" | "text"
  2. 如果是 arXiv ID/URL → _fetch_arxiv() 抓取标题+摘要
  3. LLM.chat(ANALYSIS_SYSTEM, text)
     → JSON: { title, summary, key_concepts, notable_quote, tags:{...} }
  4. 构建 Source 对象（含 TagSet）
       │
       ▼
source_store.py :: save_source()
  → 写入 data/knowledge_base/sources.json
       │
       ▼  (if recluster=True)
clusterer.py :: build_clusters()
  1. 为每对 source 计算 Jaccard(tags_a, tags_b)
  2. 贪心合并：以连接度最高的 source 为 seed，
     拉入 Jaccard ≥ 0.20 的邻居
  3. 对每个 cluster：统计 dominant tags
     → LLM 命名 + 一句话描述
  4. 将 cluster_id / cluster_label 写回各 source
       │
       ▼
source_store.py :: save_clusters()
  → 更新 sources.json（sources + clusters 两个顶层 key）
       │
       ▼
Response: Source（含 cluster_label）
```

---

## 数据模型

### Source（`api/models/source.py`）

```
Source
  id              : str (uuid4 前12位)
  title           : str
  content_type    : "text"|"arxiv_id"|"arxiv_url"|"doi"|"url"
  raw_text        : str (摘要/正文片段，最多4000字符)
  url             : str?
  authors         : list[str]
  year            : int?
  tags            : TagSet
    .topics       : list[str]    # 主题
    .methods      : list[str]    # 方法
    .concepts     : list[str]    # 概念
    .domain       : list[str]    # 领域
    .problem_type : list[str]    # 问题类型
  summary         : str          # LLM 生成的白话摘要
  key_concepts    : list[str]    # 关键概念名词短语
  notable_quote   : str          # 原文中一句值得注意的话
  cluster_id      : str?
  cluster_label   : str?
  added_at        : ISO8601
```

### Cluster（`api/models/source.py`）

```
Cluster
  id            : str (uuid4 前8位)
  label         : str     # LLM 命名，如 "Deep Learning Methods"
  dominant_tags : list[str]
  source_ids    : list[str]
  summary       : str     # LLM 对该簇的一句话描述
```

### sources.json 文件格式

```json
{
  "sources": {
    "<id>": { ...Source fields... }
  },
  "clusters": {
    "<id>": { ...Cluster fields... }
  },
  "updated_at": "2026-05-04T14:00:00"
}
```

---

## LLM 抽象层

```
BaseLLM (services/llm/base.py)
  chat(system: str, user: str) -> str
  available() -> bool

get_llm(provider?) -> BaseLLM
  优先级：指定 provider → .env DEFAULT_LLM → 任意可用 provider
  若全部未配置 → RuntimeError（明确提示用户配置 .env）

当前支持的 provider：
  anthropic → claude-sonnet-4-6
  openai    → gpt-4o-mini
  gemini    → gemini-1.5-flash
```

**添加新 provider 的步骤**：
1. 继承 `BaseLLM`，实现 `chat()` 和 `available()`
2. 在 `services/llm/__init__.py` 的 `candidates` 字典中注册
3. 在 `config.py` 中添加对应 API key 字段
4. 更新本文件的"当前支持的 provider"列表

---

## API 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/sources` | 摄取来源（主入口） |
| GET  | `/sources` | 列出所有来源 |
| GET  | `/sources/clusters` | 列出所有聚类 |
| POST | `/sources/recluster` | 强制重新聚类 |
| GET  | `/sources/{id}` | 获取单个来源 |
| DELETE | `/sources/{id}` | 删除来源 |
| POST | `/user/profile` | 设置用户画像（可选，辅助搜索） |
| GET  | `/user/profile` | 获取用户画像 |
| GET  | `/search/arxiv` | 搜索 arXiv（直接入库） |
| GET  | `/search/semantic_scholar` | 搜索 SS |
| GET  | `/kb/export` | 导出完整知识库 JSON |
| POST | `/kb/import` | 导入外部知识库 |
| GET  | `/health` | 健康检查 |

---

## 日志体系

```
logger.py 初始化层级：

root logger (DEBUG)
  ├── ConsoleHandler  (INFO+)   彩色输出
  ├── FileHandler     (DEBUG+)  logs/app_YYYYMMDD.log
  ├── llm logger      (DEBUG+)  logs/llm_YYYYMMDD.log    每次 LLM 调用：provider/model/耗时/token
  └── search logger   (DEBUG+)  logs/search_YYYYMMDD.log 每次搜索：query/来源/耗时/命中数

middleware.py 记录：
  每个 HTTP 请求：[req_id] → METHOD PATH | client | UA
  每个 HTTP 响应：[req_id] ← METHOD PATH | status | ms
  4xx/5xx 以 WARNING 级别输出
  Response headers: X-Request-Id, X-Response-Time-Ms
```

---

## 安全边界

| 风险 | 防护措施 |
|------|----------|
| API Key 提交到 Git | `.gitignore` 屏蔽 `.env`；pre-commit 钩子扫描 key 格式 |
| 测试数据提交到 Git | `.gitignore` 屏蔽 `data/**/*.json` |
| CI/CD 中 key 泄露 | GitHub Secrets + TruffleHog 扫描 |
| 运行时数据暴露 | `data/` 目录不进镜像，Docker volume 挂载 |

---

## 已知限制与后续扩展点

| 限制 | 影响 | 推荐方案 |
|------|------|----------|
| 搜索用简单关键词 Jaccard | 同义词不能聚类 | 替换为 sentence-transformers 向量距离 |
| 聚类阈值 0.20 硬编码 | 小知识库可能过度分裂 | 暴露为 `/sources/recluster?threshold=0.15` 参数 |
| sources.json 无并发保护 | 多用户同时写可能覆盖 | SQLite + aiosqlite 替换 JSON 文件 |
| arXiv 抓取用 HTML 解析 | 脆弱，arXiv 改版会断 | 改用 arXiv API (`export.arxiv.org/api/query`) |
| LLM 调用无缓存 | 重复 enrich 重复计费 | 以 content hash 为 key 的本地缓存 |
