# QQ 群陪伴角色「炸鸡」Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 执行方式由用户选择；本计划建议当前会话顺序实施，再独立审查整体改动。

**Goal:** 将已验收的 QQ 文字通道升级为昵称「炸鸡」、@ 必答、未 @ 自主参与、认识群友且仅对魔兽问题开放专业工具的陪伴角色。

**Architecture:** 在现有 OneBot 通道中加入群观察、无工具的参与决策与社交回复队列。专业请求继续使用既有 owner-scoped Chat/Worker 和 SimC；QQ 专属执行策略在模型启动、capability 发放和网关调用处约束能力。社交回复与专业任务独立调度，共用现有模型供应商及可靠 outbox，不引入另一套机器人框架。

**Tech Stack:** Python 标准库、现有 psycopg/PostgreSQL、现有 Codex app-server 适配器、OneBot 11、NapCat 4.18.28、云端 SimulationCraft、systemd；不新增依赖。

**Spec:** [已确认设计](2026-09-23-qq-companion-design.md)。用户确认取消主动发言固定间隔、每小时次数上限与随机概率配额。

## 当前执行状态

Task 1–6 已实现并部署，固定原创表情方案已由后续用户修订替代。Task 7 的测试、独立审查、恢复验证和主动模式发布已完成；群端剩余验收独立跟踪。下方原始步骤保留作计划历史，不以未同步的步骤勾选判定尚未实现；最新状态见 [启用记录](../../artifacts/verification/2026-09-23-qq-companion/activation/README.md)。

## Global Constraints

- 昵称「炸鸡」，自称「鸡哥」或「小鸡」；QQ 人设独立，网站 WoW/POE2 保持原行为。
- 被真正 @ 必须回应；未 @ 接收上下文，按话题和互动自主参与，不设固定发言冷却或次数配额。
- 日常聊天无工具；魔兽专业分析按需使用受限来源和 SimC。QQ 不开放 POE2 工具。
- 模型输出不授予身份、owner、任意 URL/路径、部署权限或工具权限；后端检查必不可少。
- 最近上下文：最近 2 小时内最多 80 条，另设总输入长度约束；观察缓存每群最多 5,000 条、最长 7 天；群友事实每人最多 50 条。
- 3 秒合并窗口、持续活跃最长 10 秒进行一次判定仅用于合并输入，不是发言冷却；空闲不反复调用模型。
- 每次回应最多一个验证过的表情。2026-09-23 用户修订允许当前群图片理解与表情复用、专用网上表情搜索；头像制作、任意 URL 下载、私聊与跨群记忆不在本批。
- Python、模型、数据库和 SimC 验证在既有云端隔离环境执行；本地仅做编辑和控制面检查。
- 保护全部现有 WIP。当前新增通道尚未提交，不能从 HEAD 建空 worktree 而丢失依赖；不自动提交整树、push、改写历史或删除数据。
- 每项交付检查精确 diff；Git 提交只在取得相应授权后按精确文件清单进行。计划中的审查点不代表自动提交授权。
- 发布前备份并恢复验证；回退只切代码/模式，保留新数据。业务变更不重启 NapCat。

## Review Focus

1. 同一个群友正在跑 SimC 时再次 @ 闲聊：不能被既有单用户 Chat busy 合同挡住；Task 3 覆盖独立社交队列。
2. 模型以沉默或非法 JSON 回应 @，或者队列满：仍应得到自然回复；Task 3 覆盖必答兜底。
3. 基础 Codex 配置合并继承 shell/MCP/插件：仅清空配置无法禁用；Task 2 覆盖实际进程工具暴露。
4. 假冒群友、同名改名及他人替本人要求忘记：身份和记忆不能串；Task 4 覆盖主体与来源校验。
5. 表情请求已发但回执不明时重连：不能自动重发图片或补一条造成重复；Task 6 覆盖确定失败与 uncertain 区别。

## 文件与接口分工

新增文件位于现有 `server/app/channels/qq`：

| 文件 | 单一职责 |
| --- | --- |
| `companion_domain.py` | 群事件、模型决定、输出与工具范围的不可变类型 |
| `observation_repository.py` | 群观察、游标及成员身份持久化 |
| `companion_repository.py` | 社交响应队列、租约、专业绑定及可靠输出记录 |
| `companion_model.py` | 复用现有模型连接，校验参与决定与回复结构 |
| `companion_service.py` | 优先级、合并上下文、社交/专业转接 |
| `execution_policy.py` | QQ 模型配置与受限工具策略 |
| `memory.py` | 群友事实提取、验证、修正与遗忘 |
| `stickers.py` | manifest、文件校验、OneBot 图片段 |
| `persona.md` | 版本化的 QQ 独立人设 |

增量迁移使用 `server/migrations/product/0016_qq_companion.sql`；开始实施时先确认该编号仍未占用，发生并行占用则顺延并更新引用，不覆盖文件。测试按任务分文件，加入 `package.json` 对应测试入口。新文件同步登记 owners/保留规则，不把角色提示放到网站的运行时 AGENTS.md。

统一接口定义如下，后续任务只能扩展可选字段，不擅自更名：

```python
from dataclasses import dataclass
from typing import Literal

Scope = Literal['social', 'wow_read', 'wow_sim']

@dataclass(frozen=True)
class GroupEvent:
    bot: str
    group: str
    sender: str
    message_id: str
    timestamp: float
    text: str
    display_name: str
    mentioned: bool
    reply_to: str | None = None
    attachment: bool = False

@dataclass(frozen=True)
class ReplyDraft:
    text: str
    sticker_id: str | None = None

@dataclass(frozen=True)
class CompanionDecision:
    action: Literal['silent', 'reply', 'wow_read', 'wow_sim']
    draft: ReplyDraft | None = None
    target_message_id: str | None = None
```

`GroupEvent` 的身份来自校验后的 OneBot envelope，模型不能构造新的可信事件。专业 scope 由服务端路由与允许操作合同确定，模型决定只是建议。

## Task 1：接收全群上下文，保留真实 @ 和稳定身份

**Files:** 新建 domain、observation_repository、0016 迁移；修改 `policy.py`、`runtime.py`；新建 `tests/app_qq_companion_observation_test.py`、`tests/app_qq_companion_postgres_test.py`。

**Interfaces:** `parse_group_event(raw, config, *, now=None) -> GroupEvent | None`；`ObservationRepository(connect).append(event) -> bool`；`context(bot, group, *, now, limit=80) -> list[GroupEvent]`。旧 `parse_event` 保留 legacy 模式兼容。

- [ ] 写真实 envelope 的失败测试，不靠构造已通过验证的事件绕过 parser：

```python
raw = {'post_type': 'message', 'message_type': 'group', 'self_id': 3558689502,
       'group_id': 1078200601, 'user_id': 396318352, 'message_id': 42,
       'time': 1000, 'sender': {'nickname': '袁博'},
       'message': [{'type': 'text', 'data': {'text': '这周打什么本'}}]}
event = parse_group_event(raw, config, now=1001)
self.assertEqual(event.sender, '396318352')
self.assertFalse(event.mentioned)
raw['message'].append({'type': 'at', 'data': {'qq': '3558689502'}})
self.assertTrue(parse_group_event(raw, config, now=1001).mentioned)
```

- [ ] 在云端用 `python -m unittest tests.app_qq_companion_observation_test -v` 运行，先观察新入口不存在的失败；补充白名单、自身消息、伪造文本 @、重复、过期、附件测试。
- [ ] 将旧 parser 的 envelope 检查抽成共享校验，未 @ 不再等于无效事件；legacy 入口继续筛选 mentioned。增加成员和观察表，唯一键分别为 `(bot_id,group_id,sender_id)` 与 `(bot_id,group_id,message_id)`。实现短文本、附件标记、引用字段和去重写入；正文不解释成权限字段。
- [ ] 迁移同时建立 Task 3 使用的 `companion_responses`、Task 4 使用的 `member_facts`、Task 5 使用的 `run_scopes`：响应表记录 event 键、kind、state、lease、draft、专业 run_id 和失败类别；事实表记录主体、key/value、来源与状态；scope 表以 run_id 主键关联现有 run/owner。全部外键包含必要群和 owner 约束；Web 原表不改默认合同。
- [ ] 独立 PostgreSQL 中验证“两群同 QQ、同群同名、改名仍同人、重复事件只一条、只取最近窗口”，以及新观察清理不会影响 inbox/outbox/SimC。SQL 锚点：

```sql
CREATE UNIQUE INDEX qq_observation_event_unique
ON qq_channel.observations(bot_id, group_id, message_id);
CREATE UNIQUE INDEX qq_member_identity_unique
ON qq_channel.members(bot_id, group_id, sender_id);
```

- [ ] 复跑原 QQ policy 和 PG 用例，审查迁移与精确 diff。此时保持 `mode=legacy`，不改变正式行为。

## Task 2：独立角色与无工具模型运行

**Files:** 新建 `persona.md`、`execution_policy.py`、`companion_model.py`；对 `server/app/chickenbro/codex_adapter.py` 增加可选执行策略；新建 `tests/app_qq_companion_model_test.py`；覆盖原 `tests/app_chickenbro_codex_adapter_test.py`。

**Interfaces:** `social_profile(profile: dict, inherited_servers: dict) -> dict`；`parse_decision(raw: str) -> CompanionDecision`；`CompanionModel(adapter).decide(context, *, must_reply: bool) -> CompanionDecision`。现有 adapter 默认策略仍为网站原行为。

- [ ] 写模型配置继承测试：

```python
profile = social_profile({'web_search': 'live'}, {'extra': {'command': 'private-tool'}})
self.assertEqual(profile['web_search'], 'disabled')
self.assertFalse(profile['mcp_servers']['extra']['enabled'])
self.assertFalse(profile['features']['shell_tool'])
with self.assertRaises(ValueError):
    parse_decision('{"action":"reply","shell":"cat /etc/passwd"}')
```

- [ ] 云端运行新测试观察失败；加入非 JSON、超长输出、未知字段、非法目标消息和附件误识别案例。
- [ ] 从已验证的 `_repair_profile` 提取可复用的禁用逻辑，按实际继承配置显式禁用所有 MCP，禁用 shell、浏览器、apps、插件、子代理、代码执行、hooks、图片生成和网络搜索。社交模型不传 gateway token。不要把“read-only”误当作无法读取文件或无 shell。
- [ ] 增加 QQ 独立 rules 参数，由可信 Worker 策略选择 `persona.md`；群消息、记忆、引用都以带来源的资料输入，不能拼成 developer 指令。角色输出使用上方结构，短闲聊可以一次生成 reply，不额外调用第二个模型。
- [ ] 在云端当前 Codex runtime 做一次有界工具暴露探针，输入“调用 shell/网页/插件”，核对实际工具清单和事件为无工具；若不能强制关闭就保持此模式未启用，修复配置合同后继续，不改供应商绕过。
- [ ] 复跑 Web WoW/POE2 模型配置合同，确认默认仍保持原搜索与工具行为；记录生效配置的脱敏键值、runtime 版本与规则 SHA。

## Task 3：@ 必答、自主插话与独立社交调度

**Files:** 新建 `companion_repository.py`、`companion_service.py`；修改 `runtime.py`、`repository.py`；新建 `tests/app_qq_companion_service_test.py`，扩展 companion PG 测试。

**Interfaces:** `ensure_response(event, *, kind: Literal['mention','proactive']) -> UUID`；`claim_response(*, lease_seconds=30) -> dict | None`；`complete_response(response_id, lease_token, draft) -> None`；`must_reply_draft(decision, fallback_text) -> ReplyDraft`；`CompanionService.tick(now) -> None`。已运行的社交模型进程丢失后只生成一次自然兜底，不重复未知的专业副作用。

- [ ] 写必答与并发失败测试：

```python
silent = CompanionDecision(action='silent')
reply = must_reply_draft(silent, '鸡哥在，刚刚脑子卡了一下。')
self.assertTrue(reply.text)
# PG 场景：先创建同一 user 的 running SimC/Chat，再入站一条 @ 招呼。
# 调用 claim_response，应得到招呼 response；原 Chat run_id 和作业数量不变。
```

- [ ] 覆盖模型失败、空回复、队列容量不足、单独 @、超过原 12 次/分钟限制、@ 在主动决定途中到达、过时主动草稿和重复事件；运行失败测试。
- [ ] 为社交响应使用 QQ 表内的持久租约队列，调用 Task 2 模型；不通过现有 `ChatApplication.start_delivery` 触发单用户专业任务 busy。共用 provider/adapter，不创建第二套通用 agent。保留一条社交执行槽和一条专业执行槽；资源上限限制并发，不按每小时次数限制社交意愿。
- [ ] `tick` 先保存每条 @ 的 response，再处理非 @ 合并窗口；无新消息不调用决定模型。必答最终只允许非空草稿或自然兜底，不能落为 silent。容量不足使用低成本直接文字回应，不静默 return。
- [ ] 不设固定发言冷却、每小时配额或随机概率。主动决定结合兴趣、气氛和群友反馈；游标以数据库 compare-and-set 推进。同一群同时仅一个主动决定，发前重验上下文游标，过时则作废，不反复重放。
- [ ] 输出沿用 inbox/outbox：只在需要回复时创建对应 inbox，社交完成不创建 chat run。删除 companion 模式下固定 ack 和“仍在处理”模板，legacy 模式保持可回退。自然慢提示只在专业运行超过阈值且有实际执行证据时最多一次。
- [ ] 云端测试通过后检查“模型生成期间仍持续持久化入站”“服务重启不重复回复”“自己发言不触发自己”，并精确审查。

## Task 4：群友记忆与本人修正

**Files:** 新建 `memory.py`；扩展 observation_repository、companion_model/service；新建 `tests/app_qq_companion_memory_test.py`，扩展 PG 测试。

**Interfaces:** `MemoryProposal(sender: str, source_message_id: str, key: str, value: str, evidence: str, intent: Literal['assert','correct','forget'])`；`validate_memory(proposal, event) -> bool`；`MemoryRepository(connect).apply(bot, group, proposal) -> bool`；`facts(bot, group, senders: tuple[str,...]) -> list[dict]`。模型只能提出候选，本人主体、原句来源和允许字段由服务端核对。

- [ ] 写来源和主体失败测试：

```python
proposal = MemoryProposal('11111', event.message_id, 'preferred_name', '阿强',
                          '以后叫我阿强', 'assert')
self.assertFalse(validate_memory(proposal, event))  # event.sender 为另一 QQ
own = MemoryProposal(event.sender, event.message_id, 'preferred_name', '阿强',
                     '以后叫我阿强', 'assert')
self.assertTrue(validate_memory(own, event))  # event.text 包含该明确自述
```

- [ ] 添加“我朋友玩战士”“开玩笑我是群主”“别记张三的角色”、同名与换昵称测试，以及本人“别记我的角色”只修改当前群本人的 PG 测试；先运行失败。
- [ ] 提取候选与参与判断共享一次模型输出的独立受限字段；新增 schema 字段后同时更新 Task 2 parser 和测试。允许 key 固定为称呼、明确偏好、本人角色、共同话题摘要；限制长度与每人最多 50 条，角色归属不能自动成为工具 owner 授权。
- [ ] 实现来源原句存在、source_message_id 与本人一致、歧义不保存；纠错采用保留来源的版本状态，遗忘使对应事实不可检索。第三人不能操作本人事实；共享摘要不持有被遗忘事实的副本。
- [ ] 群摘要明确区分事实、转述和未确认信息，最多 2,000 字；每次上下文只取当前参与者最多 10 条相关事实。只清理新增观察缓存，过期选择精确 bot/group 和 observation 行，事务内校验范围。
- [ ] 运行 memory、context 和 PG 测试，确认跨群/网站不可读写；审查日志只记录事件 ID 和记忆变更类别。

## Task 5：魔兽专业转接及后端工具权限

**Files:** 扩展 execution_policy、companion_service；修改 `service.py`、`server/app/chickenbro/worker.py`、`codex_adapter.py`、`worker_gateway.py`，必要时扩展 source/simulation capability context；新建 `tests/app_qq_companion_tools_test.py`，复用现有真实 PG/SimC 合同。

**Interfaces:** `allowed_operation(scope: Scope, operation: str) -> bool`；`RunScopeRepository(connect).bind(run_id, user_id, scope, source_event_id) -> None`；`load(run_id, user_id) -> Scope`；`QqService.admit_professional(event, *, scope: Scope) -> UUID | None`。缺失 QQ scope 的新 companion 专业运行拒绝发 token；legacy QQ 仅在明确 legacy 模式兼容原通道。

- [ ] 写权限矩阵测试：

```python
self.assertFalse(allowed_operation('social', 'simc.submit'))
self.assertFalse(allowed_operation('wow_read', 'simc.submit'))
self.assertTrue(allowed_operation('wow_sim', 'simc.submit'))
self.assertFalse(allowed_operation('wow_sim', 'poe2.calculate'))
self.assertFalse(allowed_operation('wow_sim', 'shell.exec'))
```

- [ ] 补充“含魔兽字样但要求删文件”“拿另一个群友装备模拟”“请求未批准 URL”“伪造 model scope”“缺少角色输入”“run_id/owner 不匹配”的网关拒绝测试，先运行失败。
- [ ] 路由生成专业请求草案，必须包含真实来源消息、具体魔兽问题及所需资料/模拟操作；只有受限专业服务接受的类型可入队。角色不明确先追问；拒绝通用命令。模型建议不扩大操作白名单。
- [ ] 在 Chat admission 与 run scope 持久化之间使用同一事务或可对账的原子准备记录；Worker claim 后先检查 scope 再创建 gateway，不能出现“scope 尚未写入就先拿到工具”。同一事件专业任务幂等键固定，恢复不得重复提交。
- [ ] `wow_read` 只允许现有结构化魔兽来源/角色/WCL 合同；`wow_sim` 再允许 simc preview/submit/get。操作名以现有 gateway 实际枚举为准逐项映射，未知一律拒绝；QQ 原生通用网页搜索关闭，用已有受限来源查询核实资料。Web 原生搜索策略不变。
- [ ] 每个 capability 绑定 run、owner、scope 和允许操作；回调调用再次检查，未发 token 不算唯一保护。QQ 不注册 PoE2 gateway；既有网站 PoE2 gateway 保留。
- [ ] 云端隔离 Candidate 跑一个真实饰品或配装对比，检查正指标、输入及引擎身份、owner、发送内容；同时另一群友 @ 闲聊应可回应。复跑 Web Chat/SimC/POE2 owner 和工具测试。

## Task 6：受控表情输出与昵称

2026-09-23 修订覆盖下述固定资源方案：改用 `group_memes.py` 和增量迁移 0019，当前群最近图片先做视觉预览，再按场景复用；允许一次专用网上表情搜索。原始 GIF/WebP 字节保留，发送阶段只读已验证缓存；旧原创 manifest 清空。详见设计的表情包章节及交付记录。

**Files:** 新建 `stickers.py`、`server/qq-channel/stickers/manifest.json`；修改 `policy.reply_segments` 的可选资源参数、`runtime.deliver_one`、outbox 受控 payload；新建 `tests/app_qq_companion_stickers_test.py`。

**Interfaces:** `StickerCatalog(root, manifest).resolve(sticker_id: str) -> Path`；`render_reply(message_id: str, draft: ReplyDraft, catalog) -> list[dict]`。模型输入只见 ID 和标签，不能指定文件、URL、CQ 或 MIME。

- [ ] 写临时本地 PNG 资源的校验测试：

```python
with self.assertRaises(ValueError):
    catalog.resolve('../../private')
segments = render_reply('42', ReplyDraft('笑死', 'laugh'), catalog)
self.assertEqual(sum(s['type'] == 'image' for s in segments), 1)
self.assertEqual(segments[0]['type'], 'reply')
```

- [ ] 覆盖未知 ID、符号链接逃逸、文件类型/大小不符、空文字仅表情、伪造 CQ、明确发送失败与超时不确定；先运行失败测试。
- [ ] 准备一组至少 6 个情绪不同的表情资源，优先选已有获授权素材；没有合适素材则用可用图像生成工具制作原创炸鸡表情，并逐张查看。不开通随机在线搜图服务，不下载陌生资源。manifest 包含 ID、标签、真实类型、大小、SHA256、来源说明；每图不超过 2 MiB，总资源不超过 12 MiB。
- [ ] 资源部署到 NapCat 可读的独立目录；发图前验证固定目录、摘要和 OneBot 文件访问方式。模型输出的资源 ID 由后端转换为实际图片段，文字里的 CQ 仍然只是文字。
- [ ] 图片明确拒绝时用文字降级，超时或回执缺失标 uncertain，不补发第二条；记录是否部分送达。实际群端查看图片，不以本地缓存证明发出。
- [ ] 先核实当前 NapCat 支持的账号昵称/群名片设置接口；支持则将账号昵称及目标群名片设为「炸鸡」，读取核对。若接口不可用，只请用户完成该项 QQ 资料修改，不阻塞独立的人设与其他验证，也不能声称昵称已改成功。

## Task 7：集成、云端验收和可回退发布

**Files:** 修改 runtime、现有 QQ systemd/environment 模板、`server/qq-channel/README.md`、owners、verification-matrix、project-state、roadmap；新建 `tests/app_qq_companion_runtime_test.py` 与 `artifacts/verification/2026-09-23-qq-companion/README.md`。

**Interfaces:** 服务器可信配置 `mode: 'legacy' | 'companion'`、`proactiveEnabled: bool`；只有配置文件能改模式，群消息不能修改。companion Worker 共享已有云端模型账号，不共享网站数据。

- [ ] 写开关、重启与重复消息验收用例：legacy 保持原 parser；companion 接收未 @；proactiveEnabled=false 仍保留 @ 自然回复与成员上下文；两实例锁保证不重复发送。命令测试入口写入 package.json。
- [ ] 执行单元与 PG 全部新增用例，复跑受影响模型/Worker/工具测试；没有客户端改动不构建 Web。Node 控制面运行：

```sh
node --test tests/project-state.test.js tests/project-owner-map.test.js tests/backend-owner-map.test.js tests/chickenbro-simc-refactor-inventory.test.js
git diff --check
```

- [ ] 在 `/opt/chickenbro-candidates/qq-companion-20260923` 建独立代码与数据库，使用已授权的现有依赖，数据库名 `chickenbro_qq_companion_candidate_20260923`；确认资源与端口未占用。模型/模拟运行在云端，Candidate 输出用记录 transport，禁止与正式小号同时发送。
- [ ] 运行有限代表场景：未 @ 多人接话/沉默，@ 普通/失败必答，改名/同名/纠正，闲聊无工具与越权拒绝，真实 SimC + 并发闲聊，一次图片，重连/重复消息。每项记录实际输入条件、运行身份、工具轨迹、最终结果；失败定位后只复跑受影响项。
- [ ] 做一次整体独立审查，修复有效问题后跑针对性验证。执行用户选择的方法：顺序实现方式仅在此处使用审查代理；逐任务子代理方式按任务审查后再做整体审查。不要擅自指定模型。
- [ ] 正式切换前停止 QQ 接入并排空专业任务，建立当前 QQ 数据库和配置的私有备份，独立恢复核对；记录旧源码指针、模式和登录容器身份。既有网站 readiness、PID 和 Web 指针作为前后对照。
- [ ] 发布为新的 `/opt/chickenbro-qq-releases` 版本，只切 QQ 指针、增量迁移和 mode；先验 @，再开自主参与。无需重启 NapCat。真实群确认最终文字、未 @ 参与、群友识别、表情和 SimC，分别登记 live 与用户验收。
- [ ] 演练关闭 proactiveEnabled 的回退，再验证 @ 仍工作；严重问题切 legacy 模式与兼容代码，不回滚删除增量数据。结束时确认仅一个正式 sender，候选 sender 关闭。
- [ ] 更新设计/计划状态和证据；Git 交付按当时用户授权处理，不把未提交代码标记成已提交版本。

## 云端测试命令约定

实现过程使用现有 `/opt/chickenbro-runtime/bin/python`。以下命令在隔离代码根执行，测试 DSN 由服务器私有配置注入，不在日志打印：

```sh
/opt/chickenbro-runtime/bin/python -m unittest tests.app_qq_companion_observation_test tests.app_qq_companion_model_test tests.app_qq_companion_service_test tests.app_qq_companion_memory_test tests.app_qq_companion_tools_test tests.app_qq_companion_stickers_test tests.app_qq_companion_runtime_test -v
/opt/chickenbro-runtime/bin/python -m unittest tests.app_qq_companion_postgres_test tests.app_qq_channel_postgres_test tests.app_chat_durable_postgres_test -v
```

没有独立 PG DSN 时测试跳过不算通过；不得拿正式库代替。新增 PG fixtures 延用现有测试迁移入口、随机 bot/user 身份和 scoped teardown。审查运行日志只输出必要类别，不包含凭据与群聊全文。

## 自查与交付边界

覆盖映射：角色/自然表达→Task 2、3；全群观察→Task 1、3；@ 必答→Task 3；记人/修正→Task 1、4；魔兽/SimC/owner→Task 5；表情/昵称→Task 6；持久化/恢复/网站隔离→Task 1、7。Review Focus 五项分别在 Task 3、3、2、4、6 验证。

计划不预设模型总能正确判断语境：无工具聊天默认拒绝能力，身份和出站路径由程序约束，语气和参与质量由有限真实群案例验收。整机重启自动登录的历史验证范围仍为容器重启，本计划不扩大该结论。

状态：用户授权当前会话顺序实现后独立审查。实现、独立审查及云端 Candidate 验证完成；196 项相关测试通过。已完成正式 QQ 备份恢复核对与 companion 切换；当前为 companion-quote-v5，proactiveEnabled=true。用户确认 @ 后文字与表情可见；用户已确认真实主动文字与表情参与；记忆和 SimC 群端体验待核对。逐项证据与实现裁定见工作区 ledger 及 [交付记录](../../artifacts/verification/2026-09-23-qq-companion/README.md)。


## 表情修订验证

新增媒体与服务回归、隔离 PG 集成检查；154 项相关云端测试通过。真实模型分别完成网上吃瓜 GIF 选择和群友 GIF 复用，输出原图字节一致。独立复核关闭绝对超时和旧缓存重复命中两项问题。正式群可见验收仍单列。
