# POE2 角色链接导入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking. 用户禁止提交，所有 commit 步骤替换为未提交 diff 审查及源码清单。

**Goal:** 以角色链接为 POE2 导入主入口，完成 ninja 用户辅助导入及 WeGame 版本化转换，向用户交付真实可测的独立 Candidate。

**Architecture:** 来源任务负责受限网络读取、数据映射和完整性检查，原有 PoB 进程继续无网络计算。两来源统一汇入 owner-scoped 构筑及基线任务，三步 Web 流程复用已有对比和导出。

**Tech Stack:** FastAPI、PostgreSQL、Python、隔离云端 Chromium、既有 LuaJIT/PoB 2、Taro React、typed domain/API-client。

**Spec:** [已确认设计](2026-09-20-poe2-character-link-design.md)。状态：用户已确认子代理实施及审查；本文件不宣称功能已完成。

## Global Constraints

- 所有下载、依赖、浏览器、引擎、测试及构建仅在云端。工作区 `.worktrees/poe2-20260918`；云端 `/opt/chickenbro-candidates/poe2-20260918`。
- 不提交、推送、合入、切换生产、清理其他任务文件。保护既有 WIP；按新增文件及修改范围做差异审查。
- ninja 不发起后台角色请求，不调用其内部 API；用户粘贴官方导出码后才计算。
- WeGame 仅打开主动提交的公开分享、读取页面自然请求的必要响应；遇登录、验证码或访问限制结束采集。
- 网络采集与无网络 PoB 分开；浏览器使用独立无凭据账户与受限出口，不复用当前研究脚本的宽松执行方式。
- 链接不是角色所有权证明；owner 永远来自 Principal。所有状态、快照、补充和结果按 owner 隔离。
- 未识别词缀、珠宝缺失与版本未知不得默默省略；缺口解决前不得宣布完整转换或显示可靠提升百分比。
- 导入成功要求合法 XML、真实基线任务成功及可追溯版本；面板 DPS 不得写成引擎计算值。
- 每用户同时 1 个采集任务、全局 2 个；采集 60 秒超时。保留资料完整的国服真实样本验收门槛。

## Review Focus

1. URL 中中文、百分号编码及 WeGame fragment：规范化一次，保留角色名；伪装域名与私网跳转拒绝（Task 1）。
2. 补充上传、取消与过期 worker 同时发生：旧 attempt 不能提交新状态或重复构筑（Task 2）。
3. 同名不同阶辅助、两套武器、嵌套符文：映射保留结构和 flags，未知值可定位（Task 4）。
4. 来源局部成功但珠宝为空、版本不明：展示已读角色和精确缺口，不变成空珠宝完整构筑（Task 3/4）。
5. 切换账号/新导入后旧响应迟到、刷新后任务继续：UI 不混入其他任务或账号的结果（Task 5）。

## 文件边界与测试运行

新增 `server/app/poe2/imports/`：domain（合同）、urls（URL）、repository（持久化）、application（owner/状态）、worker（编排）、sources/wegame（采集）、sources/ninja（用户动作）、mapping（版本转换）、data（映射表）。
新增 `server/app/poe2/character_bridge.lua`：标准角色 JSON → PoB 原生导入 → XML；现有 engine 负责最终计算。新增 `server/poe2_source_browser.cjs`：无凭据采集进程。
Web 抽出 `Poe2CharacterImport.tsx`，避免继续堆大 `WebPoe2.tsx`。

以下 Python/Node 命令均在云端 source 目录执行；Python 为 `/opt/chickenbro-runtime/bin/python`，Node PATH 使用已有 `runtime/node-v22.19.0-linux-x64/bin`。不新增本地依赖。

### Task 1: 来源识别与合同

**Files:** 新增 `server/app/poe2/imports/{__init__,domain,urls}.py`、`tests/app_poe2_import_urls_test.py`；修改 `packages/domain/src/poe2.ts`，新增 `packages/domain/src/poe2-import.test.ts`。

**Interfaces:** `parse_character_url(value: str) -> SourceRef`。SourceRef 含 provider、canonical_url、account、league、character、share_id（后四项可空）。ImportStatus 为设计中的九种状态；Issue 包含 code、path、severity、message；状态响应包含 id、status、provider、preview、issues、nextAction、buildId、baselineJobId、attempt、updatedAt。

- [ ] 编写失败测试，覆盖给定两链接、中文编码、尾部空白、伪装域名、用户信息段、端口、fragment 错位及双重编码。

```python
def test_ninja_unicode_identity(self):
    ref = parse_character_url('https://poe.ninja/poe2/profile/wuba-4006/forbiddenrites/character/玩個那個破大錘')
    self.assertEqual(ref.provider, 'ninja')
    self.assertEqual(ref.character, '玩個那個破大錘')
def test_deceptive_host(self):
    with self.assertRaises(ValueError):
        parse_character_url('https://poe.ninja.evil.example/poe2/profile/a/b/character/c')
```

- [ ] 云端运行 `python -m unittest tests.app_poe2_import_urls_test -v`，确认缺模块/缺逻辑的失败。
- [ ] 用 urllib.parse 分离 host/path/fragment；严格匹配 WeGame `www.wegame.com.cn/helper/poe2/#/share/<token>` 与 ninja 已知角色路径；禁止 credentials、非 443 端口、额外查询参数和重复解码。返回显式 provider，不通过子串猜来源。

```python
parts = urlsplit(value.strip())
if parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None, 443):
    raise ValueError('POE2_SOURCE_URL_INVALID')
```

- [ ] typed 响应验证器逐项接受 nullable ID，拒绝未知 status；运行 Python 测试与 `npx vitest run packages/domain/src/poe2-import.test.ts`。审查 diff，保存证据。

### Task 2: 持久化导入任务与 ninja 辅助导入

**Files:** 新增 `server/migrations/product/0013_poe2_character_imports.sql`、`imports/{repository,application,worker}.py`、`imports/sources/{__init__,ninja}.py`、`tests/app_poe2_import_application_test.py`、`tests/app_poe2_import_postgres_test.py`；修改 API routes/poe2.py、dependencies.py、worker/main.py。

**Interfaces:** `ImportApplication.create(principal,provider,url,key)`、`read(principal,id)`、`supply_source(principal,id,source,key)`、`retry(principal,id,key)`、`cancel(principal,id)`；`ImportWorker.run_once() -> bool`。repository claim/complete 接受 lease_owner、attempt，complete 通过 CAS 校验；ninja 的 nextAction 为 supply_pob，携带已验证站点链接。

- [ ] 写失败测试：ninja 创建直接 needs_input 且网络 spy 零调用；给定 XML 完成真实基线；owner B 的五项操作均 404；相同 key 不重复；相同 key 不同内容 409；取消后旧 worker 不可完成。

```python
def test_cancel_fences_old_worker(self):
    row = self.app.create(self.a, 'wegame', self.wegame_url, 'first')
    claim = self.repo.claim('worker-a')
    self.app.cancel(self.a, row.id)
    self.assertFalse(self.repo.complete(claim.id, 'worker-a', claim.attempt, {'status': 'ready'}))
    self.assertEqual(self.app.read(self.a, row.id).status, 'cancelled')
```

- [ ] 云端运行这两个新 unittest 模块，确认失败；迁移添加 imports 表、owner FK、唯一幂等索引、attempt/lease、最小快照字段、expires_at、stage、result IDs，并授予实际 wow_app 所需权限。
- [ ] 实现 CAS 状态机及每 owner 活跃任务约束；最多 2 次可重试基础设施失败，登录/限流/映射错误不自动重试；worker 重启可恢复。
- [ ] supply_source 创建新 attempt 并验证 XML，调用既有 PoB/构筑和基线任务合同。持久化 source relation=user_supplied；构筑记录与完成引用用事务/确定性唯一键避免崩溃后重复。ready 必须同时有成功 job 和 build ID。

```python
if job.status == 'succeeded' and build is not None:
    repo.complete(import_id, lease_owner, attempt,
                  {'status': 'ready', 'buildId': str(build.id), 'baselineJobId': str(job.id)})
```

- [ ] API 实现设计中五路由，source/retry 添加幂等 key；使用既有 Principal、CSRF、ApiProblem。只返回净化 preview/issues，不返回快照原文和分享凭据。
- [ ] 云端普通单测、SET ROLE wow_app PG 用例、真实 ninja XML 基线执行；保存 owner、重试/取消及基础指标证据。未成功快照只读取未过期记录；TTL 清理接入受限 worker 的任务级行为，保留成功构筑资料，不扩大到旧数据。

### Task 3: WeGame 公开分享采集与隔离

**Files:** 新增 `imports/sources/wegame.py`、`server/poe2_source_browser.cjs`、`tests/app_poe2_wegame_source_test.py`、`tests/poe2_source_browser_test.cjs`；修改 Candidate runtime/deploy 配置。

**Interfaces:** `collect_wegame(ref: SourceRef) -> dict`，返回只包含 role、equipment、skills、passives、jewels、source timestamps 的净化快照；失败返回确定性的 SOURCE_UNAVAILABLE/AUTH_REQUIRED/RATE_LIMITED/INCOMPLETE。

- [ ] 写浏览器适配器合同测试：任一请求转私网/元数据地址即拒绝；60 秒退出；单响应 2 MiB/必要响应总量 8 MiB；缺必需资源是 INCOMPLETE；缺珠宝内容保留 missing，不补空数组代表完整。

```python
def test_missing_jewels_stays_missing(self):
    snapshot = normalize_capture(self.capture_with_empty_jewels)
    self.assertEqual(snapshot['jewels']['status'], 'missing')
    self.assertNotIn('openid', snapshot['role'])
```

- [ ] 云端失败测试后实现新独立浏览器账户/进程，最小环境、无宿主凭据、无外部 remote debugging；采集 allowlist 精确到必要站点及路径，阻断广告/遥测。通过网络命名空间/出口代理或等效实际内核策略拒绝内网，单靠 URL 字符串过滤不计通过。
- [ ] 浏览器只打开 canonical_url 并观察页面自然响应；不重放额外 API、无登录、无验证码绕过。采集器强制域名/重定向/响应体/总时限；返回明确状态并关闭上下文。
- [ ] 全局并发 2、owner 并发 1、关闭开关；云端验证拒绝内网连接、并发超额与退出回收。
- [ ] 实际打开用户给定 WeGame 分享，保存净化后的 schema、条目数量和字段缺口，与前次样本作字段层比较；来源改变只报差异，不固定断言角色永久不变。公开使用规范未确认时保持 Candidate 范围。

### Task 4: 国服映射与真实 PoB 转换

**Files:** 新增 `imports/mapping.py`、`imports/data/zhCN-0_5.json`、`server/app/poe2/character_bridge.lua`、`tests/app_poe2_mapping_test.py`、`tests/app_poe2_character_bridge_live_test.py`。

**Interfaces:** `map_snapshot(snapshot: dict, dictionary: dict) -> MappingResult`；MappingResult 含 character（标准 PoB 角色 JSON）、issues、mappingVersion、sourceHash、gameDataVersion；`convert_character(character: dict) -> str` 返回 PoB XML。未知关键字段存在时不调用 convert。

- [ ] 建立带来源及许可标记的字典，单独记录 classes、bases、uniques、gems（含阶级）、modifier templates、quest rewards；执行时先核对上游公开资料和固定引擎数据，不用图片名猜身份。
- [ ] 写失败测试：中英标记数值、词缀 flags、同名 II/III 辅助、两套武器、属性选择、珠宝缺口、未知版本。

```python
def test_unmapped_modifier_blocks_conversion(self):
    snapshot = self.valid_snapshot()
    snapshot['equipment'][0]['explicitMods'].append({'description': '未登记测试词缀'})
    mapped = map_snapshot(snapshot, self.dictionary)
    self.assertTrue(any(i.code == 'MOD_UNMAPPED' for i in mapped.issues))
    self.assertIsNone(mapped.character)
```

- [ ] 云端单测确认失败后，按类型逐项实现映射；每一原始节点/词缀/宝石必须进入已映射清单或问题清单，清单数量可核对。quest/skill_overrides 不走模糊文本匹配。
- [ ] 桥接复用上游 `ImportPassiveTreeAndJewels` / `ImportItemsAndSkills`，输入和文件路径均由服务器控制；继承现有进程内存、时间、网络限制。由 PoB 保存 XML，再通过既有引擎计算及 export roundtrip。

```lua
build.importTab:ImportPassiveTreeAndJewels(character)
build.importTab:ImportItemsAndSkills(character)
build.buildFlag = true
runCallback('OnFrame')
local xml = assert(build:SaveDB('code'))
```

- [ ] 给定 WeGame 样本逐项核对天赋/武器专精、技能辅助、装备与任务奖励。珠宝为空保留 needs_input，完整 PoB 上传可补齐；不将其记作完整国服自动转换成功。
- [ ] 在当前公开分享数据中尝试取得完整的珠宝资料；页面未提供则停止该方向，向用户请求同角色完整导出或另一个资料完整的公开国服样本，继续其他独立任务。
- [ ] 至少一份资料完整的真实国服样本，通过源数据清单、PoB 导出重导入、生命/属性/抗性对齐和特定主技能配置核对。未取得完整样本时记录具体阻塞，整体“国服完整打通”不得标完成。

### Task 5: 三步 Web 与 Chat 接入

**Files:** 新增 `apps/mini-taro/src/web/{Poe2CharacterImport.tsx,poe2-character-import.test.tsx}`、`packages/api-client/src/poe2-import.test.ts`；修改 WebPoe2.tsx/样式、packages/api-client/src/poe2.ts、Chat POE2 skill/tools 及相应合同测试。

**Interfaces:** `Poe2CharacterImport({auth,onReady})`；`onReady(buildId,baselineJobId)` 更新既有构筑与 jobs。API client 暴露 createImport/getImport/supplyImportSource/retryImport/cancelImport，严格 typed responses。

- [ ] 写失败组件测试：链接入口先出现；ninja 显示打开原页+粘贴码；WeGame 显示阶段和缺口；ready 自动进入第二步且不重复计算；取消/刷新可恢复；A 的迟到结果不出现在 B 页面。

```tsx
expect(screen.getByLabelText('角色链接')).toBeTruthy()
expect(screen.queryByText('导入完成')).toBeNull()
// mocked needs_input response
expect(screen.getByText('打开角色页面，复制 PoB 代码')).toBeTruthy()
```

- [ ] 实现国服/国际服独立链接输入与受控格式示例；不把真实玩家私人标识作为默认填充值。保留折叠的 PoB/XML/示例入口及官方链接。
- [ ] 导入状态轮询使用 generation/abort 守卫；取消旧轮询，按 importId 恢复。仅成功后调用 onReady；异步失败保留输入，重试复用幂等状态。
- [ ] 角色卡显示来源、更新时间和完整性；展示 source relation=user_supplied 的用户确认；缺口明确到物品/技能/珠宝位置，不堆 raw JSON。
- [ ] Chat 可创建、查询本人导入任务；needs_input 时解释如何补充，不声称已经读取 ninja 角色。工具加载仍固定 game=poe2。
- [ ] 云端运行对应 vitest、Python Chat 合同测试、typecheck、lint 和 H5 build；检查手机布局、焦点、状态消息及禁用按钮说明。

### Task 6: Candidate 业务验收与交付

**Files:** 新增 `tests/poe2_character_import_smoke.py`、`tests/poe2_character_import_browser.cjs`、`artifacts/verification/2026-09-20-poe2-character-import/README.md`；修改项目状态、路线图、owner maps、验证矩阵及部署说明。

- [ ] 独立审查整个增量，重点检查来源出口隔离、owner/lease CAS、未知映射及 partial→ready 错误转换；重要问题修复后定向复验。
- [ ] 云端应用 Candidate-only 迁移及 worker 部署；保留部署前身份/Web 备份；验证真实 wow_app 权限、服务和恢复入口。
- [ ] smoke 覆盖 ninja 粘贴样本的真实基线、WeGame 缺口路径、完整国服样本、第二用户隔离、重试、取消、刷新与旧构筑兼容。
- [ ] 云端真实浏览器逐步执行用户流程，记录结果 ID、引擎/映射/源快照身份；PoB 比较必须来自实际成功结果。
- [ ] 对公网 Web 文件逐项 hash 核对，验证生产入口及已有魔兽路径未变；只跑受影响回归，不扩展历史迁移测试。
- [ ] 交付入口、截图、完整性清单、真实验证和未完成事项。任何完整国服样本门槛未满足时明确保留该项，不能称整项完成。全部代码保持未提交，等待用户测试。

## 自检结果与执行建议

合同/状态/来源差异/映射/出口隔离/保留期/Chat/Web/业务验收分别落在 Task 1–6，五项 Review Focus 均有所属测试。Task 2、3、4 通过 SourceRef、净化快照和 MappingResult 接口衔接，避免各自定义不同的成功条件。

已选择 Subagent-driven：由子代理逐项实施，独立审查各任务及最终增量。各阶段共享状态机和映射合同，连续执行可减少接口偏差；国服规则不确定性集中在 Task 4，单独保留真实样本验收门槛。
