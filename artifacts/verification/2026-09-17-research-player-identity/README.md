# 已采样玩家的 WCL 追问被额度误拦

状态：已按用户“发布，提交、合入”授权发布。运行源码 `5ba5ff6ce689c1d95bf954022d3abb2f475ed6b3` 已提交并推送 main，Candidate 与线上真实 Chat/WCL 验收通过。

## 线上证据

只读查询生产 PostgreSQL，事务使用 `BEGIN READ ONLY` 和 30 秒 statement timeout。
目标 run：`1895358c-01b4-4948-84e1-52b442309fc1`，请求时间 2026-09-17 17:41:53（北京时间）。
记录的 runtime revision：`codex:sha256:56ef98ab4032d317ab26e9b5e5a175650717351edb16ed9cde0cb6d1734d62da`。

- 此研究先分两次各读取 5 名 Raider.IO 玩家，合计 10 名。
- 已计数身份：`character:us:bleeding-hollow:shadarek`。
- WCL 总览返回 actor 472，名字 Shadarek、服务器 BleedingHollow、区域 US。
- 保存的 actor 身份：`character:us:bleedinghollow:shadarek`。
- 17:42:13 的 `source.warcraftlogs` 调用仅查询已选战斗 `fight=10&source=472`、`view=overview`，返回 `RESEARCH_BUDGET_EXCEEDED`，维度为 players。
- 原因：原 identity key 仅把空格换成连字符，未兼容 WCL 紧凑服务器名；同一玩家被当作第 11 人。预算在上游读取前拒绝请求。

未保存聊天全文、账号身份、凭据或完整生产数据副本。

## 修复

仅在研究预算身份中统一服务器名称的空格／连字符格式，区域和角色名仍独立匹配，角色重音保持区分。
恢复持久化研究时同步规范化 players、slots、report_actors、report_players，支持已有会话继续研究。
保留 10 玩家限制及其他预算；不更改认证、角色来源 URL 或业务归属。

## 验证

- 新增网关及旧研究恢复用例在修复前均失败，错误为玩家额度拦截；修复后通过。
- 将线上目标 run 保存的 budget 和 request 在内存中交给 HEAD 原代码与修复代码回放：原代码 blocked，修复代码 admitted，玩家数保持 10；不同玩家仍 blocked。未执行 WCL 上游调用或生产写入。
- `python3 -m unittest tests.app_research_budget_test tests.app_research_lifecycle_test tests.app_research_evidence_test tests.app_research_context_test tests.app_research_completion_test tests.app_research_grounding_integration_test tests.app_research_status_test tests.app_research_usage_test tests.app_chickenbro_source_gateway_test tests.app_research_lifecycle_postgres_test`：67 项通过、14 项 PostgreSQL 集成测试跳过。
- 跳过原因：未配置 `WOW_RESEARCH_TEST_DSN`，系统 Python 与已有测试虚拟环境均缺少 psycopg。未安装依赖；新增数据库回归用例尚未执行。
- `git diff --check` 通过。

## 发布与真实验收

- [验证汇总](validation.json)：本地 67 项相关测试、23 项发布 helper 回归通过；云端已有独立 Candidate 库补跑 14 项 PostgreSQL 测试，全部通过；发布文档及保留规则的 63 项控制面检查通过。上面的 skipped 记录为发布前本地环境结果。
- [Candidate](candidate.json)：1 次真实 Chat 请求、1 次 WCL 读取，55.440 秒；成功读回 actor 472 的完整技能伤害表，玩家数保持 10。首次验收脚本把字符串 sourceId 当数字比较而误报，修正脚本后复核已保存回执，没有重复模型请求，初次私有记录保留。
- [线上](live.json)：1 次真实 Chat 请求、1 次 WCL 读取，45.223 秒；玩家数保持 10，第二账号无法读取该会话，幂等重放未新增 run 或回答。
- 两次最终回答均正确列出原表独立条目前三项：献祭光环 174,171,501（25.69%）、恶魔涌动 87,720,299（12.94%）、精华破碎 63,788,111（9.41%）；表内合计 677,955,875。独立核算与工具回执一致。
- 夹具使用已有专用测试账号的新会话，预置 1 个已研究角色与 9 个占位名额，复现旧身份格式；这些名额不冒称 10 次实际榜单查询。原用户的聊天和预算没有被人工修改。
- [manifest](manifest.json)、[源码核对](source-parity.json)、[执行器哈希](executor-pins.json)：只覆盖 `server/app/chickenbro/research_budget.py`，发布锁内重查基底并等待全任务空闲，API/Worker 同时切换。
- [最终核验](final-check.json)：147 份后端文件及 13 份公网 Web 文件匹配；47.24 秒观察、10 次 readiness、最大响应 0.252 秒，无新增 error 日志，API/Worker 均正常。
- [恢复材料](recovery-check.json)：旧文件独立复制后哈希匹配，原后端和 Web 保留；root/0600 环境恢复快照另由 final-check 核验。未执行生产回切演练。

发布私有目录为 `/var/lib/chickenbro-research-player-identity-20260917/`。原始合成验收回执保留在该 root/0700 目录；仓库仅保存限定公开证据。当前后端为 `/opt/chickenbro-releases/badcase-5ba5ff6ce689c1d95bf954022d3abb2f475ed6b3`，Web 为 `changelog-7a457b6dab5571647af8626b182577b462b26d78`。

验证范围是本次玩家身份、额度复用和真实伤害表回答；人工 QQ 登录、用户手动验收、完整职业机制分析与生产回切演练不在本次通过项中。
