# 官方 QQ 动态功能引导

用户要求：默认回复根据当句灵活回应，继续保持无法自由聊天的产品边界。已更新原官方单群 Candidate；真实群内效果待用户实测。

## 行为

非现有命令的文本进入受限引导任务，由现有无工具模型只读取当前一句，生成最多160字的短回复并引导至 `/帮助`。例如问聊天就回应闲聊范围，问团本成绩就引导相应入口。规则在 guidance.md；不新增自由聊天、历史读取、自然语言执行工具或游戏能力。

完整帮助、状态与已知命令参数提示仍直接返回；分组帮助489字保持，战斗分析 v8 代码和证据合同保持。动态引导在现有线程池中执行，不阻塞网关；复用独立官方任务与租约，不创建 chat.agent_runs／聊天会话。`/状态` 排除引导任务，保留正式查询结果；战斗上下文仍只复用本人同群同报告场次的合格战斗包。

模型单次20秒、无自动重试；生成异常或格式／长度／命令校验失败时使用短兜底。引导租约到期也结束为兜底，不重跑模型；旧租约不能覆盖结果。格式校验限制长度、帮助入口、已知命令及外链，语义边界由专用规则与真实模型用例核对。

## 验证

- [初始失败](red.log)确认尚无动态模块与路由；新增8项检查，[31项针对性检查](targeted.log)通过。旧默认回复与官方查询测试按新范围调整，继续验证不创建通用聊天任务。
- [219项云端回归](cloud-tests.log)通过，无skipped，包括官方、角色、PostgreSQL隔离、默认回复、战斗 v8 和现有无工具模型约束。未运行本地应用测试。
- [8条staging真实模型结果](staging-model-results.json)：聊天／能力／招呼／SimC／天气／忽略规则讲笑话／团本意图／重复聊天问题，均单次ready，6.18–8.69秒。未回答范围外知识或启动工具；同一问题两次措辞不同。[实际回复](CASE-MESSAGES.md)。
- [部署回执](deployment.json)、[最终检查](final-check.json)：28文件哈希匹配、gatewayReady、queryOnly、单群；动态引导启用且工具关闭，分组帮助与战斗 v8 保持。部署后额外1条真实模型生成成功，无QQ验证发送和Candidate业务数据写入。
- 对照本轮WIP副本审阅新分流、异步返回、租约恢复、状态筛选、无工具适配器及输出约束。新增 guidance.py／guidance.md，修改 query_commands.py／query_repository.py／query_service.py／runtime.py；[精确清单](runtime-manifest.json)保留前后SHA。
- Web API／Web worker／官方AIworker PID保持2319609／2319544／267252；Web来源与通道配置SHA保持。未改数据库schema、凭据或旧QQ服务，未主动发送QQ验证消息。

云端旧文件副本：`/etc/chickenbro-qq-official/dynamic-guidance-backup-20261016T082610Z`，旧SHA已核验；未做恢复演练。恢复脚本保留新文件副本，避免永久删除。本地原WIP副本见 [before-manifest.json](before-manifest.json)。仍使用 codex/qq-official，未提交、推送或合入。
