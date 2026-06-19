# 最新资讯 tab 前后端架构

## 目标

`最新资讯` 是小程序第一个 tab。它不是静态内容页，而是由 Lighthouse 轻量后端生成可信资讯数据，小程序只负责展示、刷新交互和缓存兜底。

## 部署边界

- 小程序前端：`pages/news/*`
- 后端服务器：Tencent Lighthouse，公网主机 `${BACKEND_HOST}`
- 当前后端目录：`/home/ubuntu/wow-news-backend`
- 当前服务端口：`80`
- 当前 API Base URL：`${API_BASE_URL}`

> 实际主机和 API 地址不要写入仓库，放在不提交的环境配置或部署记录里。微信小程序正式环境需要 HTTPS 且域名加入 request 合法域名；开发版可临时使用 Lighthouse IP + HTTP 联调。

## 数据来源规则

后端只允许进入首页展示的资讯满足这些条件：

1. 有中文标题、原文标题、中文摘要、完整中文正文块、频道、来源名、来源 URL、发布日期、来源说明。
2. 来源域名在可信来源白名单内。
3. 频道只能是：
   - 正式服动态
   - 测试服前瞻
   - 职业强度变化
4. 发布日期使用 `YYYY-MM-DD`。
5. 每条前端可见新闻都必须携带 `sourceName`、`sourceUrl`、`publishedAt`、`sourceNote`、`originalTitle`、`bodyZh`、`bodyBlocksZh`、`tagItems`、`sourceBadges`、`contentStatus=ready`。
6. 每条前端可见新闻必须同时满足 `licenseStatus=approved`、`verificationStatus=official_verified`、`translationStatus=llm`、`translationFidelity=source_translation`、`sourceTier=official`。未授权第三方全文翻译、未找到官方依据、冲突条目、summary-only 正文或 LLM 改写导读都必须 blocked。
7. 自动采集文章如果正文抓取、LLM 翻译、授权门禁、官方校验或中文质检失败，必须进入 refresh run 的 blocked 记录，不发布到首页、列表或详情页。

当前第一版可信来源：

- Blizzard News：`worldofwarcraft.blizzard.com`、`news.blizzard.com`，`tier=official`，`licenseStatus=approved`，默认启用全文采集和发布。
- Blizzard Forums：`us.forums.blizzard.com`，`tier=official`，`licenseStatus=approved`，默认启用 PTR / 开发说明 / Raid Testing 主题发现；通过翻译和发布质检后才可公开。
- Wowhead：`www.wowhead.com`，`tier=trusted_media`，`licenseStatus=reference_only`，默认不发布全文翻译，仅保留发现/佐证。
- Icy Veins：`www.icy-veins.com`，`tier=trusted_media`，`licenseStatus=reference_only`，默认不发布全文翻译，仅保留发现/佐证。

## API

### `GET /api/news/home`

返回资讯首页完整 payload。

```json
{
  "navTitle": "最新资讯",
  "heroNews": [],
  "metrics": [],
  "channels": [],
  "highlights": [],
  "lastRefreshedAt": "2026-06-09T03:00:00+00:00",
  "refreshMode": "scheduled"
}
```

首页、列表和详情页的公共文章字段保持一致：

```json
{
  "id": "article-id",
  "title": "中文标题",
  "summary": "中文摘要",
  "bodyZh": "完整中文正文",
  "bodyBlocksZh": [{ "type": "paragraph", "text": "中文正文段落" }],
  "originalTitle": "Original source title",
  "tags": ["content-update"],
  "tagItems": [{ "id": "content-update", "label": "内容更新" }],
  "contentStatus": "ready",
  "translationStatus": "llm",
  "translationFidelity": "source_translation",
  "verificationStatus": "official_verified",
  "licenseStatus": "approved",
  "sourceTier": "official",
  "sourceBadges": ["官方已核验", "全文翻译"],
  "canonicalTopicId": "news:24276957",
  "readingMeta": { "bodyBlockCount": 3, "estimatedReadingMinutes": 1 },
  "sourceName": "Blizzard News",
  "sourceUrl": "https://...",
  "publishedAt": "2026-06-09",
  "sourceNote": "来源说明"
}
```

公共 API 不返回 `originalBody` 或 `originalSummary`。原文正文只作为后端重翻译、审计和 blocked 归因的内部材料。

### `POST /api/news/refresh?mode=scheduled`

触发刷新并返回同结构首页 payload。

- `mode=scheduled`：服务器定时任务或运维手动触发。
- 小程序首页不提供手动刷新按钮，也不通过下拉刷新直接触发源站采集。
- `mode` 只能使用上述值；其他值返回：

```json
{
  "error": "invalid_refresh_mode",
  "allowedModes": ["scheduled"]
}
```

刷新过程异常时返回：

```json
{
  "error": "refresh_failed",
  "message": "collector or backend error"
}
```

生产环境在接入 HTTPS 域名后，需要增加服务端鉴权或网关策略：`scheduled` 只允许服务器定时任务、localhost 或授权 IP 调用，避免用户端连续触发源站采集。

## 后端实现

当前为了适配新服务器的最小环境，后端使用 Python 标准库：

- `server/news_backend.py`：HTTP API、SQLite 初始化、来源注册表、discovery queue、raw/evidence 记录、可信发布门禁、刷新记录、payload 构建。
- `server/news_collector.py`：无依赖 RSS / Atom / HTML / Blizzard Forums 采集器，负责列表发现、Blizzard 官方详情页正文块抽取、官方论坛主题发现、标准化日期、版本事件识别、频道分类、来源证据和去重。
- `server/news_translator.py`：负责 LLM 中文化 schema、tag 白名单、逐块原文直译、完整正文质检、`translationFidelity=source_translation` 和 `ready / blocked` 发布状态。
- `server/news/articles.seed.json`：第一版已核验来源的新闻种子。
- `server/news/home-payload.js`：前后端共享契约的 JS 实现，用于本地 Node 测试和小程序 fallback。

线上自动采集采用 `discovery -> processing queue -> publication` 三段式。Discovery 覆盖 Blizzard News、Blizzard 官方论坛 PTR / 开发说明主题，以及可用 reference-only 第三方来源；processing queue 持久保存所有发现条目并按批次处理，单条 LLM 或正文抓取失败不会阻塞后续条目；publication 仍只发布 `official + approved + official_verified + source_translation` 的文章。Wowhead / Icy Veins 仍只作为 reference-only 来源保存发现和佐证，未确认授权前不公开展示第三方全文翻译。

刷新链路分层：

1. 发现：按来源抓取 URL、标题、摘要、日期、source tier 和 `versionEvent`，并写入 `news_discovery_queue`。`versionEvent` 从标题、摘要、URL 和正文中抽取 `patchVersion`、`productPhase`、`sourceIntent`、`contentType`；`12.1`、`12.0.5 PTR`、`13.0 PTR`、`Midnight Beta` 等未来版本靠结构化正则识别，不依赖写死版本关键词。
2. 队列处理：每轮发现至少 10 条，每轮默认处理 3-5 条；`queued`、`retryable`、`blocked`、`published` 状态会保留到下轮，backlog 可续跑。
3. 详情抽取：Blizzard 官方文章抓取正文块，Blizzard Forums 主题保存官方论坛题目/摘要/链接，保留 `originalTitle`、内部 `originalBody` 和 `bodyBlocks`。
4. LLM 加工：仅对可发布的官方 approved 来源请求全文直译，输出中文标题、中文摘要、逐块 `bodyBlocksZh`、`translationFidelity=source_translation` 和白名单 tag；不得把正文改写成导读、摘要或阅读建议。
5. 来源与发布门禁：`news_sources` 控制授权状态，`news_raw_articles` 记录原文内部材料，`news_article_evidence` 记录官方/第三方证据；只有 `contentStatus=ready` 且通过四重门禁的文章进入公共 API；失败原因写入 `news_refresh_runs.message.blockedArticles`。

采集器通过环境变量控制：

```text
WOW_NEWS_ENABLE_COLLECTORS=0  # 默认，仅读取已核验种子
WOW_NEWS_ENABLE_COLLECTORS=1  # 启用 RSS / Atom 采集并写入 SQLite
WOW_NEWS_DISCOVERY_LIMIT=10  # 每个来源每轮至少发现的条数；旧 WOW_NEWS_MAX_COLLECTED_ARTICLES 会被视为下限输入
WOW_NEWS_PROCESS_LIMIT=5  # 每轮从 discovery queue 处理的条数，建议 3-5
WOW_LLM_TIMEOUT_SECONDS=45  # 单次 LLM 翻译请求超时
```

当前 Lighthouse 服务器已启用 `WOW_NEWS_ENABLE_COLLECTORS=1`。
V1 只会跳过已经具备 `translationFidelity=source_translation` 的官方 seed 重复条目，避免同一篇合格文章反复送入 LLM；旧的 summary-only / 导读式 seed 即使命中同一 canonical topic，也必须由新采集到的官方全文重新翻译并重新通过发布门禁。

服务器侧定时刷新使用可执行脚本，避免 inline crontab 静默失败：

```text
0 8 * * * /home/ubuntu/wow-news-backend/refresh_cron.sh
```

脚本支持环境变量覆盖：

```text
WOW_NEWS_REFRESH_URL=http://127.0.0.1/api/news/refresh?mode=scheduled
WOW_NEWS_REFRESH_LOG=/home/ubuntu/wow-news-backend/logs/refresh_cron.log
WOW_NEWS_REFRESH_TIMEOUT=240
```

每次执行会记录开始/结束时间、HTTP 状态和错误退出码，便于排查定时刷新失败。
`WOW_NEWS_DISCOVERY_LIMIT` 控制每源发现规模，后端会保证至少 10 条，避免 12.1 PTR 这类爆发更新被旧的 `WOW_NEWS_MAX_COLLECTED_ARTICLES=1` 截断。`WOW_NEWS_PROCESS_LIMIT` 控制每轮 LLM / 正文处理吞吐，未处理和 retryable 条目会留在 `news_discovery_queue` 供下轮继续。

`GET /api/news/refresh-runs/latest` 会暴露 `discoveredCount`、`queuedCount`、`processedCount`、`publishedCount`、`blockedCount`、`retryableCount`、`sourceCoverage` 和 `oldestBacklogAge`。`/api/data/health` 的 news 组件会把 backlog 视为可解释的 partial 状态，而不是把“发现数大于发布数”误报为整轮失败。

## 前端实现

- `app.json`：第一个 tab 文案改为 `最新资讯`。
- `pages/news/news-api.js`：请求后端 API，失败时回落到本地同结构 payload。
- `pages/news/news.js`：页面加载时判断是否跨天，自动消费最新 ready payload；小程序端不再提供手动刷新入口。
- `pages/news/news.wxml`：顶部 `swiper` 展示最重要 3 条新闻。
- `pages/news/news.wxss`：整体改为 WoW 风格深色金边、羊皮纸底色和高对比信息卡。
- `pages/news/detail.*`：详情页中文标题为主、原文标题作为副标题；顶部展示 `官方已核验` / `全文翻译` badge；正文只按 `bodyBlocksZh` 渲染中文翻译块；tag 使用中文 chip；来源缩小为底部复制链接按钮。

## 后续演进

1. 增加抓取 run 的错误记录和管理端查看能力。
2. 接入域名、HTTPS、微信合法域名配置。
3. 将端口从开发用 HTTP `80` 切换到正式域名后的 `443`。
