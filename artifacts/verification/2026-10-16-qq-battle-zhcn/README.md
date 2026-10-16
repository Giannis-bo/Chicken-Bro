# 官方QQ战斗分析：国服术语

本记录为v4历史验证；当前Candidate已升级[统一整场复盘v5](../2026-10-16-qq-battle-team-report/README.md)。

2026-10-16 根据用户截图反馈，将首领、副本、NPC与技能名称改用WCL国服API返回值，角色名原样保留。沿用独立工作区与现有Candidate，不提交、推送、合入。

## 改动与来源

- QQ战斗读取显式选择固定 `https://cn.warcraftlogs.com/api/v2/client` 与 `Accept-Language: zh-CN`，并请求翻译后的战斗／主数据；默认英文API仅追加locale参数不能完成本例翻译。
- 实际国服主数据：NPC 234763／237415「利希尔·烬怒」、234647「歼灭者萨祖克斯」、235465「破坏魔惩罚者」；技能474740「绝命凶径」。本例整趟标题返回「密谋小径」，原英文首领组合不再作为副本标题。[真实输出](CASE-MESSAGES.md)。
- 按原技能／角色／NPC ID关联事件。NPC施法上下文改按NPC游戏ID过滤，避免翻译名称影响内部查询。减伤展示优先使用来源返回的国服名称。
- 共享GraphQL模块仅新增固定zhCN可选项；默认端点和环境不变。部署只更新Candidate内独立文件，网站源码哈希保持原值。
- 旧英文战斗详情上下文会要求重新发送战斗分析；已发送消息及历史状态文本保留。群端重新生成摘要后，两个详情使用同一份中文证据。

## 验证

- [248项云端测试调用](qq-battle-zhcn-tests-20261016.log)通过，无skipped。新增5项测试先红后绿，覆盖固定端点、环境不变、未知locale拒绝、中文默认读取、玩家名保留、旧上下文失效和NPC ID过滤。[初始红灯](qq-battle-locale-red-20261016.log)。
- 独立只读代码审查无待修问题；[staging真实来源](staging-source.json)先通过，再更新Candidate。
- [部署后来源](deployed-source.json)逐场对比此前v3探针：报告、场次、时长、人数和每条死亡的角色ID／时间完全一致。中文标签生效；团本分摊后的恢复证据仍能闭合。

| 案例 | 场次 | 完成致死核验/记录死亡 | 大腿/毒瘤人数 | 来源耗时 |
| --- | --- | --- | --- | --- |
| key_first | 1 | 2/2 | 2/2 | 11.67秒 |
| key_last | 2 | 1/1 | 2/1 | 5.74秒 |
| raid_kill | 3 | 6/6 | 3/3 | 17.23秒 |
| raid_wipe | 49 | 10/11 | 3/3 | 26.72秒 |
| raid_no_deaths | 51 | 0/0 | 3/0 | 6.43秒 |

- 所有摘要／详情均不超过1200字符；大秘境各最多2人、团本各最多3人。无死亡场不生成减员候选；灭团10/11核验如实展示。探针模型调用0、QQ发送0，群端用户验收待进行。

## Candidate与恢复

- [21文件清单](runtime-manifest.json)，精确变更5文件。先比对现有／staging哈希、检查队列为空，核验旧文件副本后仅重启官方channel。[部署回执](deployment.json)、[最终检查](final-check.json)。
- `single_summary_raid_mplus_zhcn_v4` 网关ready，queryOnly=true、仅炸鸡test。API、worker、官方AIworker PID保持1195642／1195577／267252，旧QQ服务仍inactive。配置、凭据和数据库未改动。
- 网站来源文件SHA256保持 `b525e2fb883108c0fd5d2132381556b543688f7d7f15614ca7d4bfa6e1d783d4`。
- 回退目录 `/etc/chickenbro-qq-official/battle-zhcn-backup-20261016T030707Z`；5文件旧副本已核验，未执行恢复演练。
- HEAD仍为 `8682f05fed6657b3354db7a8d2bfb29914c8f21b`，分支codex/qq-official，未提交推送合入，其他WIP保留。

## 用户复测

真实@炸鸡并重新发送 `/战斗分析 https://www.warcraftlogs.com/reports/kNBvnCLXjqPQZhdg?fight=1`，之后查看两个详情命令。玩家名Giannis保留；标题和技能／怪物应显示上述国服术语。
