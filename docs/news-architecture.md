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

1. 有标题、摘要、频道、来源名、来源 URL、发布日期、来源说明。
2. 来源域名在可信来源白名单内。
3. 频道只能是：
   - 正式服动态
   - 测试服前瞻
   - 职业强度变化
4. 发布日期使用 `YYYY-MM-DD`。
5. 每条前端可见新闻都必须携带 `sourceName`、`sourceUrl`、`publishedAt`、`sourceNote`。

当前第一版可信来源：

- Blizzard News：`worldofwarcraft.blizzard.com`、`news.blizzard.com`
- Wowhead：`www.wowhead.com`
- Icy Veins：`www.icy-veins.com`

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

### `POST /api/news/refresh?mode=manual|scheduled`

触发刷新并返回同结构首页 payload。

- `mode=manual`：前端手动刷新按钮触发。
- `mode=scheduled`：服务器定时任务触发。
- `mode` 只能使用上述两个值；其他值返回：

```json
{
  "error": "invalid_refresh_mode",
  "allowedModes": ["manual", "scheduled"]
}
```

刷新过程异常时返回：

```json
{
  "error": "refresh_failed",
  "message": "collector or backend error"
}
```

当前开发联调环境允许小程序直接调用 `manual` 刷新。生产环境在接入 HTTPS 域名后，需要增加服务端鉴权或网关策略：`scheduled` 只允许 localhost / 授权 IP 调用，`manual` 建议增加限流，例如每用户每小时 5 次，避免用户连续点击导致源站压力。

## 后端实现

当前为了适配新服务器的最小环境，后端使用 Python 标准库：

- `server/news_backend.py`：HTTP API、SQLite 初始化、刷新记录、payload 构建。
- `server/news_collector.py`：无依赖 RSS / Atom 采集器，负责解析条目、标准化日期、频道分类、来源证据和去重。
- `server/news/articles.seed.json`：第一版已核验来源的新闻种子。
- `server/news/home-payload.js`：前后端共享契约的 JS 实现，用于本地 Node 测试和小程序 fallback。

线上自动采集源当前收敛为暴雪官方 World of Warcraft 新闻列表页。Wowhead 仍可作为可信来源保存已核验条目，但不作为当前定时抓取源，避免其 RSS 反爬返回 403 时污染每日刷新结果。

采集器通过环境变量控制：

```text
WOW_NEWS_ENABLE_COLLECTORS=0  # 默认，仅读取已核验种子
WOW_NEWS_ENABLE_COLLECTORS=1  # 启用 RSS / Atom 采集并写入 SQLite
```

当前 Lighthouse 服务器已启用 `WOW_NEWS_ENABLE_COLLECTORS=1`。

服务器侧定时刷新使用可执行脚本，避免 inline crontab 静默失败：

```text
0 8 * * * /home/ubuntu/wow-news-backend/refresh_cron.sh
```

脚本支持环境变量覆盖：

```text
WOW_NEWS_REFRESH_URL=http://127.0.0.1/api/news/refresh?mode=scheduled
WOW_NEWS_REFRESH_LOG=/home/ubuntu/wow-news-backend/logs/refresh_cron.log
WOW_NEWS_REFRESH_TIMEOUT=45
```

每次执行会记录开始/结束时间、HTTP 状态和错误退出码，便于排查定时刷新失败。

## 前端实现

- `app.json`：第一个 tab 文案改为 `最新资讯`。
- `pages/news/news-api.js`：请求后端 API，失败时回落到本地同结构 payload。
- `pages/news/news.js`：页面加载时判断是否跨天，支持自动刷新；按钮和下拉触发手动刷新。
- `pages/news/news.wxml`：顶部 `swiper` 展示最重要 3 条新闻。
- `pages/news/news.wxss`：整体改为 WoW 风格深色金边、羊皮纸底色和高对比信息卡。

## 后续演进

1. 增加抓取 run 的错误记录和管理端查看能力。
2. 接入域名、HTTPS、微信合法域名配置。
3. 将端口从开发用 HTTP `80` 切换到正式域名后的 `443`。
