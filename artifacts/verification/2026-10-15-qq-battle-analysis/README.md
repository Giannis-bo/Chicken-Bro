# 官方 QQ 单场战斗分析：Candidate 交付

2026-10-16：本页记录首版历史。用户已否定首版分析深度并授权修订；当前升级与源码身份见[深度分析v2交付](../2026-10-16-qq-battle-depth/README.md)。

2026-10-15 用户确认并授权：默认一条战斗摘要，支持击杀和灭团；详情入口为 `/战斗详情-大腿`、`/战斗详情-毒瘤`，各最多三人且必须有日志证据。保持现有独立工作区、Candidate、测试群，不提交、不推送、不合入。

## 当前交付

- `/战斗分析 WCL链接 [场次=5]`，可直接粘贴带 `fight=` 的链接；未选场次列出最近最多五个已结束团本首领场次，同时包含击杀和灭团。显式 `场次=` 优先于链接参数。日志里的 source 选择不缩窄团队范围。
- `/战斗详情-大腿`、`/战斗详情-毒瘤` 使用本 bot/group/sender 最近一次成功战斗摘要；支持显式链接另查。角色查询、其他用户、失败／仅场次选择及迟到租约不会覆盖战斗上下文。
- 三种分析回复均在完整段落层面限制到 1200 字符，一条消息；详情各最多三人，有几人显示几人。原三个角色命令仍保留最近三场及既有格式。
- 只用 WCL 服务端 OAuth API。复用鉴权、严格来源解析和官方队列，不调用模型、SimC、PoB 或通用问答。

## 首版证据口径

大腿入口按完整职责名单及完整表格，展示输出职责伤害第一、治疗职责有效治疗第一、随后输出第二（候选不足时按已有证据）。同职责排名按当前样本的日志总量，不声称装等／专精归一、操作水平、首领本体贡献或坦克质量。WCL 父级玩家记录使用其返回总量，不重复累加嵌套宠物。

毒瘤入口当前提供承伤／减员复盘关注：按首次死亡时间选最多三名不同角色，分别取死亡前五秒承伤窗口，展示最后三条正数伤害。成员、角色、目标、时间、技能 ID 与本报告身份绑定；同毫秒并列，重复死亡保留。只描述取得的事件；可规避、驱散可用性、救场或操作责任需对应证据，本版未采集的判断不输出。

摘要的承伤片段来自上述已查窗口；无死亡则读取结束前十秒。它不是整场峰值扫描。技能名取本报告 masterData，源名称缺失保留 ID；WCL 返回英文技能名时原样展示。事件分页、语义字段或职责缺失会降级范围；未读取不记零。每次读取总计不超过18次 GraphQL调用，100秒截止；分页4页/窗口，死亡最多3页。

## 验证

- [181项云端测试](cloud-tests.log)通过，无 skipped。覆盖解析、单条长度、击杀/灭团选择、职责/宠物、时间窗与分页、字段缺失、真实 PostgreSQL 的本人上下文／第二用户／租约 fencing／失败保留、异步查询、原有角色与官方协议及 WCL/Chat相关回归。Starlette/httpx 有原有弃用提示。
- 需求及审查问题均有红绿记录：[首批](red-tests.log)、[SQL](postgres-red.log)、[承伤](window-red.log)、[不同角色窗口](distinct-death-red.log)、[审查](review-red.log)、[元数据成功而统计全失败](metadata-only-red.log)、[空报告](empty-report-red.log)。
- 独立只读代码审查发现并修正三个重要问题：缺职责名单导致错误排名、事件语义字段缺失却称完整、统计读取全失败覆盖成功上下文；对应回归已包含在181项中。空报告无法选择也补充明确结果。无遗留 Critical/Important；审查后未做第二次独立复审，以新增红绿回归和整组测试验证修复。
- [staging真实来源](staging-source.json)与[部署后真实来源](deployed-source.json)各验证两个击杀、一场灭团，均一条回复、角色数量不超过三。所有来源验证 `qqMessagesSent=0`、`modelCalls=0`；不作为真实群收发验收。

## 用户给定案例

[mZBg8DbyNdTrXcFL，第3场](https://www.warcraftlogs.com/reports/mZBg8DbyNdTrXcFL?fight=3)：英雄乌拉特克，已击杀，591.311秒，28人，6次死亡。部署后摘要270字符，大腿535字符、三人，毒瘤743字符、三人。实际输出保存于[案例回复](CASE-MESSAGES.md)。

## Candidate 身份与更新

- 原目录 `/opt/chickenbro-qq-official-candidate-20261014`，数据库 `chickenbro_qq_official_candidate`，AppID `102828220`，白名单仅炸鸡test `1127827451`，仍只接收真实群 @ 事件。
- [运行清单](runtime-manifest.json)18文件匹配，其中更新8文件。旧14文件哈希在更新前全量核对，任务和发送排空，停止后再次检查排空；只重启 `chickenbro-qq-official.service`。数据库仅新增 nullable `result_packet` 列，wow_app 读写权限已核验。
- [部署回执](deployment.json)、[最终核验](final-check.json)：网关 READY、queryOnly=true、白名单1；网站 API/Worker PID `1195642`/`1195577`、官方 AI Worker `267252` 保持；旧 `chickenbro-qq-channel.service` 与 `chickenbro-qq-worker.service` 仍 inactive。配置、凭据、网站源码及 Web 制品未修改。
- 源码仍为 `codex/qq-official` 上的未提交 WIP，基础 HEAD `8682f05fed6657b3354db7a8d2bfb29914c8f21b`。health.runtimeRevision 沿用接入标识，本轮源码身份按18文件哈希，不把该字段当成本轮版本。
- 回退副本 `/etc/chickenbro-qq-official/battle-backup-20261015T122939Z`，旧文件备份哈希已核对；本轮未执行恢复演练。回退只还原旧文件，新增模块与nullable列可保留且旧代码不使用，不删除任何业务数据。

## 指令面板与人工验收

[面板回执](panel.json)：通过[官方修改接口](https://bot.q.qq.com/wiki/develop/api-v2/autogen/api/v2_panels_panel_id.put.html)更新原群聊面板，版本1→2，保留原三条并追加三条战斗命令。scope/target_type 不变，API读回六项一致；菜单备份留在服务端私有目录。管理页登录已过期，改用API完成，无需用户登录。

桌面 QQ 菜单可见性本轮未核验完成；操作期间用户切换了 QQ 群，未继续抢占界面。群内业务收发、两位真人操作及用户验收均 pending。完整步骤见[验收说明](ACCEPTANCE.md)。此前角色查询的用户验收继续有效，不延伸为新战斗功能验收。
