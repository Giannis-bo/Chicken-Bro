# 动态引导 v2：鸡哥口语与按需帮助

用户要求：默认回复更像群里的鸡哥，别每次列全能力和 `/帮助`，继续不开放自由聊天。已更新原官方单群 Candidate；真实群内效果待用户复测。

## 改动

v1提示词和输出校验都强制带一次 `/帮助`，导致句尾反复出现帮助入口。v2移除必带要求，最多出现一次；提示词按意图区分简短接话、能力概括、边界回应与用法引导。招呼／道谢／问聊天／问能力不带帮助入口，明确询问用法或查询意图时才提示相关命令，完整格式需要时才指向 `/帮助`。

默认一至两句、通常15–45字，程序上限80字；适度游戏口语，避免公告腔、自我介绍和全能力清单。异常兜底也缩为“鸡哥刚卡了一下，具体用法先看 /帮助。”，避免失败后重贴能力介绍。

无工具、无历史、当前单句、20秒单次模型及不自动重试保持；不开放知识问答、攻略咨询、笑话或持续闲聊。分组帮助、正式查询、状态筛选、租约与战斗分析 v8 逻辑保持。

## 验证和交付

- [初始失败](red.log)复现无帮助回复被拒和长兜底；新增无命令／无帮助的回归，调整无效输出检查。[32项针对性检查](targeted.log)与[220项云端回归](cloud-tests.log)通过，无skipped，未运行本地应用测试。
- [8条staging真实模型结果](staging-model-results.json)均单次ready：问聊天、能力、招呼、道谢、天气、忽略规则讲笑话均不带 `/帮助`；问团本用法和完整格式时按需给入口。未转为范围外问答。[实际回复](CASE-MESSAGES.md)。
- [清单](runtime-manifest.json)精确更新 guidance.py、guidance.md、runtime.py，28文件哈希核对，前置旧SHA、staging、空队列、原目录和单群验证，旧副本核验后仅重启官方channel。
- [部署回执](deployment.json)、[最终检查](final-check.json)：gatewayReady、queryOnly、单群、v2、无工具；部署后1条真实模型ready且不带帮助入口。分组帮助489字和战斗 v8 保持。
- Web API／Web worker／官方AIworker PID保持2319609／2319544／267252；Web来源和通道配置SHA保持。无数据库schema／凭据改动，未主动发送QQ验证消息。

原WIP副本见 [before-manifest.json](before-manifest.json)。云端回退副本 `/etc/chickenbro-qq-official/guidance-colloquial-backup-20261016T083630Z`，旧SHA已核验，未做恢复演练。沿用原工作区与 codex/qq-official，未提交、推送或合入。
