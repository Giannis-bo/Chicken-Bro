# POE2 集成最终评审

结论：**此前两项 P1 均已修复；本轮限定范围复核未发现剩余 blocker**。静态复核 engine/runner/bridge、WebPoe2/WebShell、typed domain/API、专用 Candidate 启动器与受信 Chat approval 配置；未重复执行测试或修改云端 source。以下保留原发现的复现条件及修复结论。

## 已修复：[P1] 正常任务的 errorCode=null 被 typed client 拒绝

- 最终复核：`Poe2Job.errorCode` 已为 `string | null`，`isPoe2Job()` 接受 null；domain/client 回归加入 queued/null 响应合同。原阻断已关闭。

- 位置：`packages/domain/src/poe2.ts` 的 `Poe2Job.errorCode` 和 `isPoe2Job()`；对照 `server/app/poe2/application.py:129`。
- 后端 `job_packet()` 在 queued/running/succeeded 状态使用 `job.public_error_code or None`，实际 JSON 为 `errorCode: null`；前端类型和 validator 均只接受 string。
- 因此基线提交、正常任务列表、轮询到 succeeded 都会被 `ApiTransport.validate` 判为无效响应。任务实际上可能创建成功，但 Web 无法拿到其 ID/状态/结果，后续对比和方案导出全部受阻。已有 Web 测试模拟 failed + 字符串 errorCode，未经过真实 typed client，不能覆盖此问题。
- 修复：统一合同为 `string | null`，validator 接受 null；补真实后端形状的 queued/running/succeeded/failed 单包与 list 响应回归，覆盖 calculate → getJob → compare/export 的客户端路径。

## 已修复：[P1] 同步导入沿用 6 秒客户端超时，合法构筑会被提前中断

- 最终复核：`importBuild` 已单独设置 `timeoutMs=65000`，覆盖当前最多 10 秒 engine lock 等待、45 秒计算及响应余量；client 回归断言该值。原阻断已关闭。

- 位置：`packages/api-client/src/poe2.ts` 的 request helper/importBuild；默认值来自 `packages/api-client/src/transport.ts:261`。
- import_build 会同步执行真实 PoB，服务端允许引擎最多 45 秒；但 POE2 client 未指定 timeoutMs，Taro 请求默认仅 6000ms。合法构筑超过 6 秒时，页面报导入失败，服务端仍继续计算并创建 build。用户重试会再次创建一个构筑，且原请求的成功记录未进入当前列表。
- 修复：为同步 import 单独设置覆盖引擎及响应余量的超时（例如 60000ms，与现有 SimC 长请求方法一致），并以超过默认 6 秒的成功响应验证。其余快速读写请求无需统一放大。若保留取消/断网后重试体验，至少重新读取历史以显示已成功的导入；真正防重可后续增加导入幂等。

## 其余复核结论

- 引擎 runner 在 exec LuaJIT 前加载 seccomp 网络拒绝规则，失败会终止；执行沿用每任务临时目录、受限环境、1 GiB 地址空间/CPU/文件数限额与 45 秒 timeout。未发现本轮新增任意命令或任意路径输入通道。
- XML 根与实体检查、压缩扩展限额、装备/技能/配置白名单，以及 bridge 的槽位/宝石/天赋合法性检查均已读取。上下文使用独立进程，无跨任务 build 复用。
- 原始导出来自 build 持久化 exportCode，方案导出来自成功 job.result.exportCode；对比读相同 owner 下两个成功任务，检查相同 build/input hash/engine。当前版本和赛季来自不可变 build；不同 configuration 的差异由界面说明适用条件。
- WebShell 为两游戏保留独立 Chat 实例，构筑工作台独立；正常退出账号会在 WebApp 卸载整个 WebShell，第二账号登录创建新的工作台。异步 API 回调由 generation/卸载清理隔离，未发现该正常切换路径的旧账号数据写回。
- /poe2 客户端路由注册已完成。主任务提供的本轮证据为前端 289 项、后端 713 项（1 skipped）、真实 API 与浏览器 13 项检查，以及真实 Chat 两次 calculate、三次 job_get、compare 后正确输出 52 生命差异；本评审没有重跑上述套件，测试及业务证据由主任务交付材料绑定具体 Candidate 身份。

## 收尾变更复核

- `_load_profile(allow_poe2=...)` 仅在受信 `game=poe2`、存在 gateway 和 tool context 时预批准 `poe2_import`/`poe2_calculate`，其余能力隔离与 capability 撤销保留；新增测试对比 POE2/WoW 配置。`poe2_import.idempotentHint=false` 与实际新增构筑语义一致。
- `poe2_candidate_runtime` 先验证现有 PGPass 凭据来源再强制独立 DB、8796/18794、新 Cookie/CSRF/heartbeat/jobs/engine lock，清空 QQ 配置；错误输出不含凭据。AppSettings 仅新增准确的 Candidate 数据库名称，没有放开生产 test login。
- 原生表单/按钮样式已改用 `data-poe2-*` 与 `type=button` 属性选择器，JSX 对应属性已齐备。本轮只核对源码匹配；主任务正在执行最终浏览器视觉复验，不能将此静态核对当成视觉验收。
- 未扩大测试或功能范围；没有新增待修复重要问题。Candidate 用户验收、生产发布授权仍由主任务按原约束处理。
