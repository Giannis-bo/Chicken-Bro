# G2 durable execution checkpoint — 2026-09-09

状态：`已完成 / 后端已发布`。已合入最新 QQ 登录、图片输入及粘贴/拖拽主线，公网业务回归通过。人工产品体验验收与本轮自动化验证分别记录。

基底 f4535c7cde94ab334aac11ea7d68e7395e92c108。最终发布前刷新发现 main/origin 已至 fc0ba96c3，生产为 `/opt/chickenbro-releases/qq-a89dc8a334d892a826e80fcb2e1decdeadbdee47`，已含图片输入及 Web-only QQ 身份合同。当前 application/repository/main 与这些改动重叠；不能将旧基底 overlay 推广到当前生产。原主工作树仍有其他任务 WIP，未操作它。

## 验证

- 后端 449 通过；真实 PG migration 套件 91 项，其中 1 项因非空库跳过。独立新空库另跑 schema 13 项全部通过，覆盖该场景。
- durable PG 8 项包含事务原子性、owner、幂等、失租写入、成功提交后中断和锁等待跨过租约。审查发现 now() 固定事务开始时间，先新增失败回归，再改为拿锁后 clock_timestamp() 核对；审查复核关闭。
- 控制面 62 通过。ops Node 首次 92 通过、1 文件因缺 Taro 依赖无法加载；使用已有主工作树依赖的 NODE_PATH 单独补跑该文件 9 项通过。ops Python 14 通过。无安装、无本地 SimC。
- 隔离数据库真实 API/Worker 进程故障测试：准入后 API 重启、工具执行后 API 重启均保留唯一回答；账号互斥/owner 隔离/幂等回放通过。Worker 中断后即使不重启 Worker，API 也将过期任务明确 failed；重启不自动重放，不重复 SimC。SimC 只验证真实 application/repository 入队，未运行模拟。
- 最后一轮故障测试曾在 SimC 写入可见、工具回执尚未提交时提前 kill，回执断言失败；收紧故障注入为两份回执提交后重跑通过。业务代码未因该测试修改。

## 真实模型计时（单次观测，不代表分布或 SLA）

| 问题 | 旧代码 direct adapter | 新代码独立 Worker + API 重启 | 工具墙钟变化 |
|---|---|---|---|
| 原问题 | 480.02 秒超时，46 次调用 | 291.41 秒成功，18 次调用 | 285.72 → 69.20 秒 |
| 同类问题 | 248.11 秒成功，23 次调用 | 162.05 秒成功，8 次调用 | 126.21 → 30.52 秒 |

真实模型和 WCL 均启用；两次新路径都在生成期间杀掉并重启 Candidate API，随后共享历史、owner 隔离、唯一回答与幂等回放通过。非工具墙钟包含模型、调度及其他等待，不称为纯推理时间。原问题 Candidate v3 与 v4 仅租约时钟保护不同；同类问题与故障测试已用 v4。

质量人工复核：答案明确区分核验与缺证据，不把圣能溢出换算有效治疗损失，不凭道标外鸣钟断言可提前。原问题关键时间点从保存的工具事件独立核对：美德 309639ms、结束 318642ms、鸣钟 319976ms，间隔 1334ms；190997ms 圣闪有效 0、过量 188011；翅膀 90234/211981/332782ms。两组答案提供具体建议及反事实限制；没有宣称每句均独立验真。私有对话和答案留在云端，仓库仅保存统计。

保留失败尝试：最初使用未允许端口的 50.96 秒回答没有成功工具调用，不能计入基线；早期优化一次 74.23 秒 CodexStreamError，根因未证实，不能声称完全消除协议失败；另一次早期优化 217.45 秒成功不作为最终 Worker 数据。随后新增原生工具文本有界保护测试，超大结果明确 partial，模型需缩小查询。

## 首轮发布前检查（历史）

发布脚本尚未执行。已补 API 启动失败时借仍运行 Worker 环境回滚、staged manifest 完整一致性、非 overlay 文件集合/内容/类型核对及 API 开放准入前的自动恢复。当前生产身份变化，须先基于最新 main 整合 G2 与图片输入/Web-only QQ 合同，再重新跑受影响测试及最新组合 Candidate；当前脚本旧基底 manifest 必须拒绝发布。最终再执行精确 release、公开业务 smoke、合入推送和身份核对。


## 最终组合与发布

用户授权解决冲突后，组合后端 476、真实 PG 102（无跳过）、控制面 62、ops Node 80 + Python 11 全部通过。新增图片入队/独立 Worker 读取/幂等回放测试通过；最终端口变更后 adapter/native 38 项通过。独立审查关闭租约时钟、回滚入口、staged 身份、端口与双服务状态检查问题；QQ/图片组合无新增 P1/P2。

最终 runtime commit `08404a091a6dc9a08bcf65a759b47763c2942711`，12 个运行文件与 [精确 manifest](release-manifest.json) 一致。代码指向 `/opt/chickenbro-releases/g2-08404a091a6dc9a08bcf65a759b47763c2942711`，API/Worker 均启用持久执行和图片能力。新增迁移 `0008_chat_durable_execution`；运行角色无 CREATE，停服排空后由本地 postgres peer 执行 additive DDL。Web 保留 `inline-images-4a519c4c1882db9085fe5b4ad345cc1c062e522d`，13 个公网文件逐字节匹配。

- 合并后真实复杂问题：168.83 秒成功，12 次工具调用、45.94 秒工具墙钟；生成中 API 重启，唯一回答/两份 Web 会话读取/owner/幂等通过。此前“双端”只代表历史旧基底，当前测试均为 QQ owner 的 Web cookie。
- 真实随机图片：生成中 API 重启后 6.28 秒完成，准确识别 8 位码；最终独立端口的真实来源查询再次通过。
- [公网业务验证](public-smoke.json)：上传/消息幂等、CSRF/类型/大小、owner 隔离、断线继续、账号互斥、真实图片识别、历史回放及真实来源事实与答案一致全部通过。独立合成 QQ 身份只用于 smoke，凭据已撤销；未冒称本轮重新完成真人 QQ OAuth 授权。QQ 登录授权 URL 创建与公网 readiness 正常。
- [首切恢复](first-cutover-recovery.json)：第一次排空检查拦下新请求；随后 Worker 因 8794 被 QQ Candidate 占用未启动，确认无活动 Chat 后安全回滚，旧服务与 readiness 恢复，保留 schema。最终改用 28794；停服前检查端口，Worker MainPID 拥有监听后才开放 API。端口探测还曾保守拒绝 Candidate 关闭后的 TIME_WAIT，等待释放后重新发布成功。
- 最终 smoke 脚本补正 SQL 百分号转义与 Raider.IO `source_reference` 状态校验；改为直接检查取回的角色/专精事实与答案一致，完整回归重新通过。业务代码没有因这两处脚本问题修改。

回滚保留源 `/opt/chickenbro-releases/qq-a89dc8a334d892a826e80fcb2e1decdeadbdee47`、本次 manifest 与旧 drop-in。使用对应 `/var/tmp/g2-release-v2/deploy.py ... rollback` 前仍须排空；保留新增任务表，不做破坏性反向迁移。首次恢复是实际执行证据，最终配置使用独立端口。Worker/模型被杀后明确失败，不自动重放未知副作用，也不声称任意恢复 Codex 会话。
