### Spec Compliance

- ✅ Fix round 2：R1–R4 均 addressed；Task3 静态/合同审查 gate 通过，Task quality：Approved。以下前轮记录保留为历史，当前结论见末尾复审；最终真实页面端到端验证仍由 Task6 完成。
- ✅ 文件范围与接口符合本任务：`server/app/poe2/imports/sources/wegame.py:15-56` 提供 collect/collect_wegame 与有限错误码；专用 unit/socket/resolver、两类合同测试均在 diff 中。没有 worker、数据库或生产装配改动。
- ⚠️ 实际内核隔离与线上进程身份不能由 diff 独立证明。本审查采用报告所列同 cgroup 内网拒绝、真实 Chromium 公网采集、IPC 权限和部署 hash 作为实现者报告证据，未重新执行其验证。源码策略位于 `server/poe2-source-browser/chickenbro-poe2-source-browser.service:8-47`；Task6 应将最终代码及 unit 的实际部署身份与业务采集证据绑定。

### Strengths

- `server/poe2_source_browser.cjs:15-35,122-148` 以精确站点及路径过滤自然请求，在 Request/Response 阶段检查，重定向目标会再次进入 Request 检查；没有主动重放 API。CDP 流式读取在存入 chunks 前累计字节，避免先无界读取完整正文。
- `server/poe2-source-browser/chickenbro-poe2-source-browser.service:8-47` 的独立 DynamicUser、私有文件视图、公网 resolver、cgroup IPAddressDeny 与整个服务 KillMode 构成实际部署边界；`server/poe2_source_browser.cjs:110,183` 分别显式构造浏览器和任务环境，不转发应用 DB/QQ 凭据。
- `server/poe2_source_browser.cjs:45-52,194-220` 与 `server/poe2-source-browser/chickenbro-poe2-source-browser.socket:5-10` 提供 owner=1/global=2、严格 IPC 请求字段、0600 socket 和关闭开关；`server/app/poe2/imports/sources/wegame.py:20-23` 对服务端 owner UUID 生成稳定 key。
- `server/poe2_source_browser.cjs:94-103` 明确保留 missing jewels、未知条目/schema gaps 及不含采集时钟的 snapshot hash。缺失珠宝不伪造完整空数组。

### Issues

#### Critical (Must Fix)

- 无。

#### Important (Should Fix)

- **R1 / P1 — JSON 字符串形式的珠宝在收集敏感值后才展开，净化值复现会漏出。** `server/poe2_source_browser.cjs:86,95-97`。触发：GetJewels.jewel_data 为 JSON 字符串，解析结果含 `[{"jewel":{"openid":"PRIVATE_VALUE_123","name":"PRIVATE_VALUE_123"}}]`，且该敏感值仅存在于此字符串内。secretValues(capture) 不解析该字符串；随后 scrub 删除 openid key，却保留 name 的相同值。该值进入公开 snapshot 及后续输出，违反所有递归公共值不得包含 openid 等敏感标识的明确合同。修复：在任何输出字段净化之前解析所有明确支持的嵌套 JSON 结构，合并其敏感值集合，然后统一净化整个 snapshot。云端增加上述最小 fixture，并让同一值同时出现在 role/equipment 的合法字符串字段，确保跨字段复现也被清理。现有敏感值测试只有已展开的 capture 对象，未覆盖此路径。

- **R2 / P1 — worker 已退出时按 PPid 扫描无法回收其已重归属的 detached 子孙。** `server/poe2_source_browser.cjs:161-178,185-189`。触发：任务 Node 在 Chromium 存活时被 SIGKILL、崩溃或先退出，父进程随后收到 exit；Chromium 的 PPid 已变为 init/subreaper，descendants(child.pid) 不再包含它，killTree 只尝试已退出 worker 的 PID/进程组。Chromium 自身有独立进程组，服务主进程继续运行，KillMode=control-group 此时也不会触发。结果是旧浏览器残留超过 60 秒、并发 gate 释放后仍占资源并可继续运行。修复：采用能在任务父进程死亡后保留身份的每任务 cgroup/监督器，或可靠跟踪并回收任务所属浏览器进程组；不得通过杀整个共享 collector cgroup 影响另一任务。云端定向测试让 detached 子孙先启动、worker 随即主动退出，断言子孙被回收；现有 deadline 测试只覆盖父进程仍存活的超时路径。

- **R3 / P2 — 最后 500ms 等待期间发生的采集错误仍可返回成功。** `server/poe2_source_browser.cjs:149,154-157`。触发：五个必需响应已齐，进入可选自然响应等待，BtGetBase 或重复必需响应在该窗口出现超大正文、累计 8MiB 超限、429 等错误。处理器只写 failed，而等待后直接 normalizeCapture，不再读取 failed。流本身会中止，但调用方收到 ok snapshot，丢失任务要求的明确 INCOMPLETE/RATE_LIMITED 状态；可选数据也可能默认为空。修复：完成等待并停止接纳请求后统一收束在途 handler，重新检查 failed 再返回；至少补上等待后的失败检查。增加单个定向测试使错误发生于最后等待窗口，断言不返回成功。

#### Minor (Nice to Have)

- 无额外范围建议。

### Evidence and Task6 Boundary

- ⚠️ `docs/plans/2026-09-20-poe2-link-task3-report.md` 明确说明真实分享成功发生在最后加固前；最终 tests 与 hash 对应增加 schema_gaps、禁 Worker/SharedWorker、子孙回收后的代码。因此真实页证据证明早一版的自然页面可达、数据计数和当时隔离效果，不能证明最终版浏览器兼容性或最终 schema 的端到端输出。
- ⚠️ 这一差异本身可作为 Task3 的显式未验证项交接到 Task6，无需仅为审查重复访问真实分享；但 R1–R3 是代码缺陷，仍须先修复才能通过 Task3 gate。修复后的定向测试只证明对应合同，不代替 Task6 集成验收。
- ⚠️ Task6 必须使用最终部署 collector，经真实 owner 注入的 worker 路径自然打开授权分享，记录精确代码/unit 身份、净化输出 schema 与 gaps、缺 jewels/base_info 导致的 needs_input 结果及任务后进程回收。角色属性允许变化；不得用历史快照或其离线重新净化产物代替这次端到端证据。公开使用规范未确认，保持 Candidate。
- 检查范围：读取 brief、report、指定完整 diff；仅为准确行号对 diff 做行号映射，没有重读变更源文件、范围外源码、运行本地程序、重跑测试、部署或创建子代理。未发起新的云端验证；上述三个具体云端定向用例交实现者修复时执行。

### Assessment

**Task quality: Needs fixes.**

隔离边界、自然请求白名单及有限 IPC 装配清晰；净化顺序和异常进程生命周期存在实质缺口，完成窗口还会吞掉失败。修复 R1–R3 后按定向证据重新审查，最终真实页面集成验证保留给 Task6。

### Fix Round 1 — Scoped Re-review

- **Spec Compliance：❌ Issues found；Task quality：Needs fixes。** R1–R3 已修复；R4 为本轮监督器新增的成功响应丢失风险。
- **R1 addressed** — `server/poe2_source_browser.cjs:86-91` 在任何输出字段净化前解析 jewel_data 并合并敏感值；新增测试覆盖 jewel、role、equipment 三处同值。顺序满足原要求。
- **R2 addressed** — `server/poe2_source_supervisor.py:12-28,31-45,76-78` 在启动 Node 前启用每任务 subreaper，并在退出前杀死/回收该任务所收养的子孙；broker 改为等 supervisor close 后才完成任务。新增退出测试检查原 detached 子孙 PID 消失且另一任务成功，覆盖初审漏回收场景。
- **R3 addressed** — `server/poe2_source_browser.cjs:110-115` 的 finishCapture 停止接收、等待 pending handlers 并重新检查 failed；事件入口将异常转换为失败状态。新增晚到失败用例与该顺序一致。
- **R4 / P2 open — worker 退出不能代表 stdout 已排空。** `server/poe2_source_supervisor.py:63-75` 每轮仅 os.read 65536 字节，随后只要 process.poll() 非 None 就退出循环。Node 成功写完并退出时，pipe 中可能仍有尚未读取的尾部 JSON 和换行；例如父进程刚读出一块，子进程随即写入能装进 pipe 的最后一块并退出，父进程 poll 先观察到退出便丢弃尾部。result 仍为默认 SOURCE_UNAVAILABLE/retryable，合法采集被判失败。该问题与已报告约 227KB 的真实快照直接相关，现有 sibling/supervisor smoke 的短 JSON 不覆盖。修复：记录退出状态但继续按 deadline 排空 stdout 到换行/EOF，只有管道 EOF 后才能判无完整响应；不要以 poll 提前替代读取完成。增加单个云端定向用例覆盖多块成功 JSON、worker 已退出而 pipe 仍可读的状态，最好通过受控时序确定性复现。
- **本轮证据范围** — 仅读取指定 fix diff 和 report 修复追加段，没有重跑已有测试、产品改动、部署或范围外读取。报告给出的 11 JS + 2 Python 通过、旧 R2 实际复现及私有 mount namespace 下 supervisor 短任务成功，支持 R1–R3 修复与监督器可启动；这些证据未覆盖 R4 的管道尾部情况。
- **当前身份与 Task6** — 报告记录 collector `e1907581fca5bf83cbbf63fad9fe106c912b1c28b2e3a74939e2be16f47da1c4`、supervisor `e4f9176537c4c3e46687a3394f1e64ab9548654d69f16280b6849c5fb7b81b8b`、service `01d89279c2e09c554e4af6553b6521ef152f980b9cfdb7eee1de181e83534ca0`。最终真实页仍需 Task6 绑定实际修复后身份、owner 注入、schema/gaps/needs_input 及任务回收；本轮离线 smoke 和历史真实快照均不替代该验证。

### Fix Round 2 — Final Scoped Verdict

- **Spec Compliance：✅ 本任务静态/合同范围通过；Task quality：Approved。** R1–R4 均 addressed，本轮无新增 open finding。
- **R4 addressed** — `server/poe2_source_supervisor.py:63-75` 删除 process.poll() 提前退出条件，保留完整换行、EOF、大小上限和原 deadline/停止条件。worker 退出后的可读尾部继续进入同一缓冲区解析；finally 中的任务子孙回收顺序不变。修复直接消除了初审指出的竞态。
- **定向证据匹配缺陷** — `tests/poe2_source_supervisor_test.py:11-43` 使用真实 Node 子进程输出 227303 字符和尾部标记，并缩小/减慢管道读取形成退出后尾部待排空的时序，验证完整正文与结尾。报告记录该同一用例旧实现失败、新实现通过，另有 R2 与 deadline 两项回归通过；没有用短 stdout smoke 替代大响应验证。
- **最终部署身份** — 报告记录 source、宿主部署路径及服务 mount namespace 内 supervisor 均为 `b2dadd3c8d898eac0e0fb509dd26f30e8925ffcec9a97b0bc392cf13b1fa3d31`。collector JS 与 service hash 沿用上一轮；本审查未独立重新查询运行环境。
- **Task6 仍待验证** — 最终修复版本真实页面尚未重采。Task6 需将实际最终身份与真实 owner 注入、自然分享采集、schema/gaps、missing jewels/base_info 的业务结果及任务结束回收绑定。Task3 审查通过不代表该端到端证据已取得，也不构成生产发布授权。
- **本轮检查范围** — 仅指定 fix2 diff 与 report 末尾修复证据，未重复测试、扩大旧范围、修改产品、部署或派发代理。
