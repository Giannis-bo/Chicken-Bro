# 摘要角色校验故障修复 v8

已更新现有官方QQ Candidate，2026-10-16 用户复测后认可 v8 群端效果。无提交、推送或合入，主工作区与其他WIP保护。

最新用户反馈：“可以了，目前我觉得OK，再新增一个会话，用来优化默认回复。”v8 作为后续优化基线；新会话已接续背景，默认回复具体方向待用户补充。该反馈未扩大发布或Git授权。下文保留此前交付时的技术证据与复测说明。

## 事实与原因

用户记录 `YptH9vaxBChMTn7b?fight=last` 实际为fight1，诸王之眠+12，已完成22:15、5人。[原始失败packet](failed-packet.json)证实来源ready；模型调用1次、36.3秒后以`summary actor`拒绝。原处理已经结束，旧“暂未完成”提示不准确。

[v7源码](v7-battle_narrative.py)按摘要正文中最近出现的人名推断后续事实卡的主体；该匹配对自然语序敏感。原模型完整原文未保留，不能推测具体触发句。此次删除该位置推断，改为显式actorId与本角色事实卡绑定，服务端添加人名和栏目。跨角色引用、未知/重复actor、required致死证据、650/230/1200预算继续校验；同人可以在贡献和问题栏目分别展开。

摘要结构为opening/good/review/closing，人物点评保留原风格和单条输出。失败提示区分超时、证据校验、服务异常，并明确本次处理已结束。未增加自动模型重试或放开通用AI。

## 验证

- 新增6项回归，[初始红灯](red.log)，[19项针对性通过](targeted.log)。原新增功能回归一并适配结构化摘要。
- [292项云端回归](cloud-tests.log)通过，无skipped；包括原官方、角色、战斗、隔离PostgreSQL、模型适配与答案取证合同。未运行本地应用/引擎测试。
- 独立只读代码审查通过，核对v7/v8的角色绑定、事实卡、去重、必需事件与预算，无新增重要问题。既有短人名子串检查和超预算拒绝策略未扩大本次范围。
- [原失败数据真实模型重放](staging-user-case.json)：一次33.96秒成功，摘要/大腿/毒瘤613/614/360字符；JSON缓存复用无新增模型调用。[实际三种原文](CASE-MESSAGES.md)。未伪称原模型错在某个具体句子。
- [原团本击杀/灭团真实数据模型回归](staging-raid-regression.json)：均ready，分别41.02/40.70秒，三回复长度655/829/887和722/865/931。保留灭团最早已核验致死事件与10/11范围缺口。
- [Candidate详情复用](candidate-cache.json)：原目录、v8、同一packet输出一致，额外来源/模型调用0，QQ发送0。原失败数据库记录保留，未用新结果覆盖历史。

## Candidate与恢复

[26文件清单](runtime-manifest.json)精确更新3文件：battle_narrative.py、battle_narrative.md、runtime.py。前置旧SHA、staging与空队列核验，旧文件副本核验后只重启官方channel。[回执](deployment.json)、[终检](final-check.json)：v8、gatewayReady、queryOnly、单测试群、26文件哈希一致。

本次切换前后Web API/worker/官方AIworker PID保持2319609/2319544/267252，Web来源SHA保持。Web进程和发布目录在本次切换前已由其他工作更新，当前目录见终检，未回退或修改该独立发布。旧QQ服务inactive。

回退目录 `/etc/chickenbro-qq-official/battle-summary-binding-backup-20261016T074311Z`；旧副本核验，未执行恢复演练。数据库schema、凭据和配置不变。基础HEAD仍为8682f05fed6657b3354db7a8d2bfb29914c8f21b、codex/qq-official。

用户重新发送同一战斗分析命令即可群端复测；原请求未在后台继续运行。
