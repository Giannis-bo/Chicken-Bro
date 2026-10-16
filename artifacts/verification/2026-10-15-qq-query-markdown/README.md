# QQBot Markdown 与最近五场

最新修复：团本默认改为全部分区，解决 12.1.5 为空而 12.1 已有成绩时的漏查。以[分区修复记录](../2026-10-15-qq-raid-partitions/README.md)及其运行清单为当前状态；下文保留前序 Markdown／整数显示证据。

用户 2026-10-15 已确认收到 `/角色查询 Giannis 白银之手` 的原版文字回复，本轮授权改为 Markdown，并将团本、大秘境各限制为最近 5 场。继续只开放炸鸡test（1127827451），源码保持未提交、未推送、未合入。

## 当前行为

- 使用 QQ 官方 `msg_type=2`、`markdown.content`，保留原消息关联和发送序号。标题、加粗、列表和日志链接采用[官方支持的格式](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/type/markdown.html)。
- `/角色查询` 返回角色资料与「团本」「大秘境」两个成绩分类；另两个命令只返回对应分类。选择当前 WCL 团本／赛季；团本覆盖全部分区，大秘境限定当前赛季默认分区，范围显示在分类标题下。
- 从单场 `encounterRankings` 的公开记录读取历史排名百分位。跨 Boss、难度、DPS/HPS 和当前目录统一按 `startTime` 倒序，去重后每类最多 5 场。支持同一个 Boss 或副本的多次记录；先筛选指定 Boss、副本、难度和层数，再取最近 5 场。
- 展示记录专精、难度／层数、限时状态、分数颜色、北京时间和具体日志链接。分数按四舍五入取整展示（`.5` 向上），颜色仍按原始百分位判定；缺失时间、无效分数或不完整返回不会被伪装成完整的最近五场。
- 无记录每类只提示一次。长回复按完整行拆分，不切断 Markdown 日志链接；`/状态` 同样使用此分段逻辑。

## 验证与部署

- 云端 82 项相关测试通过，含新增 6 项：时间排序、同 Boss 多场、去重与筛选、缺失时间、Markdown 转义、发送协议与分段。见 [cloud-tests.log](cloud-tests.log)。既有 Starlette/httpx 弃用提示仍在。
- [真实来源读取](source-smoke.json)：角色查询耗时 11.01 秒，大秘境 5 条按时间倒序，团本当前分区无记录；指定英雄 Boss 查询 4.38 秒；诸王之眠 +12 查询 5.70 秒，首条为 2026-10-08 16:35、84.83121009116554（紫分）。样本来自实时公开 API，没有群内发送动作。
- Candidate 精确更新 5 个文件，预先验证包清单和旧文件哈希，备份后只重启官方 QQ channel。网关 READY、`queryPresentation=markdown_recent5_v1`、queryOnly=true、白名单数量 1。配置、凭据和数据库无改动。
- 网站 API/Worker 与官方 AI Worker PID 保持 1195642、1195577、267252。回退副本 `/etc/chickenbro-qq-official/presentation-backup-20261015T024730Z` 已核对哈希；本轮未执行恢复演练。
- 身份与哈希见 [presentation-manifest-20261015.json](presentation-manifest-20261015.json)、[runtime-manifest.json](runtime-manifest.json)、[deployment.json](deployment.json) 和 [post-deployment.json](post-deployment.json)。
- 部署后重新读取 14/14 运行文件，哈希与本轮完整清单匹配。健康文件的 runtimeRevision 沿用初始接入环境标识，本轮源码以 `queryPresentation` 和完整文件哈希定位。

## 真实群验收

在炸鸡test 从成员候选选择真实 @炸鸡后分别发送：

1. `@炸鸡 /角色查询 Giannis 白银之手`：确认标题和加粗实际渲染；角色资料后只分「团本」「大秘境」，每类最多 5 场，按时间倒序。暂无记录只显示一条提示。
2. `@炸鸡 /角色大米查询 Giannis 白银之手 副本=诸王之眠 层数=12`：确认只含 +12、最多 5 场；点击日志核对对应战斗、时间和同层历史百分位，不能按最高分排序。
3. `@炸鸡 /角色团本查询 Giannis 白银之手 Boss=内克扎莉 难度=英雄`：确认只含指定 Boss／难度，当前样本无记录时仅一条提示。使用确有当前分区记录的角色补充团本正成绩验收。
4. `@炸鸡 /状态`：确认取回本人最近结果，Markdown 和日志链接完整。第二用户隔离继续按原验收步骤测试。

用户随后提供了实际 Markdown 群回复截图，已确认大秘境最近 5 场和日志链接正常展示，并要求分数四舍五入取整。该增量只更新 `query_commands.py`，云端 82 项测试通过，含 `.5` 向上取整和保留原始颜色的边界验证。截图中的五条分数显示为 80、92、74、67、85。见 [rounding-manifest.json](rounding-manifest.json)、[rounding-tests.log](rounding-tests.log)、[rounding-deployment.json](rounding-deployment.json)、[rounding-render.json](rounding-render.json)。此前清单与来源读取保留为上版证据，最新单文件哈希以 rounding-manifest 为准。

本轮状态：Markdown 和大秘境最近五场群展示已获用户截图确认；整数显示更新已部署 Candidate，待新查询确认。第二用户和团本正成绩验收继续 pending。
