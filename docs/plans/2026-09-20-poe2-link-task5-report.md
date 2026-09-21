# Task 5 — 两来源 Web、API client 与 Chat 接线

2026-09-20。实现与云端定向测试完成，交 root 独立审查。没有提交、推送、合入、服务重启、发布或生产切换。本地仅文件读写/git检查/rsync；全部测试、类型检查、lint 和 H5 构建在 `ssh wow-lighthouse`，使用已安装依赖。未改 mapper、collector 或后端状态机。

## 文件清单

新增：
- `apps/mini-taro/src/web/Poe2CharacterImport.tsx`
- `apps/mini-taro/src/web/poe2-character-import.test.tsx`
- `packages/api-client/src/poe2-import.test.ts`
- `tests/app_poe2_character_tools_test.py`
- 本报告。

修改（相对 root 保留的 Task5 baseline）：
- `apps/mini-taro/src/web/WebPoe2.tsx`
- `apps/mini-taro/src/web/WebPoe2.module.scss`
- `apps/mini-taro/src/web/web-poe2.test.tsx`
- `packages/api-client/src/poe2.ts`
- `vitest.config.ts`
- `server/app/poe2/tools.py`
- `server/app/chickenbro/worker.py`
- `server/app/chickenbro/codex_adapter.py`
- `server/chickenbro_native_mcp.py`
- `server/app/chickenbro/agent/POE2.md`
- `server/app/chickenbro/agent/skills/poe2-build-analysis.md`
- `tests/app_chickenbro_codex_adapter_test.py`

仅这些实现/测试文件按相对路径 rsync 到 Candidate source；报告保留本地。未覆盖运行中 web 或 root 的产物。

## Web 与 API 合同

`Poe2CharacterImport({auth,onReady})`，onReady(buildId,baselineJobId)，可返回 Promise。国服 WeGame 与国际服 poe.ninja 独立来源按钮/链接校验，显式发送 provider。格式示例只放 placeholder；不预填真实角色。国际服明确 Copy PoB 操作与 user_supplied/未核验同角色；国服明确有限覆盖与缺项。

API client 复用 `isPoe2Import` 严格响应合同、既有 structured-problem transport、web auth/CSRF 和 Candidate prefix：

| 方法 | 请求 |
| --- | --- |
| createImport(body,auth) | POST `/poe2/imports`，provider/url/idempotencyKey |
| getImport(id,auth) | GET `/poe2/imports/{id}` |
| supplyImportSource(id,body,auth) | POST `/poe2/imports/{id}/source`，source/idempotencyKey |
| retryImport(id,body,auth) | POST `/poe2/imports/{id}/retry`，idempotencyKey |
| cancelImport(id,auth) | POST `/poe2/imports/{id}/cancel`，空对象 |

原始链接、PoB/XML、角色预览只在内存。sessionStorage key=`poe2-import:<SHA256(csrfToken)>`，value 仅 importId。只恢复同一登录会话；新登录不会跨会话恢复。WebCrypto/storage不可用明确提示，停止自动恢复；不降级共用缓存。服务端 GET 继续做最终 owner 检查。

generation 守卫覆盖恢复、轮询、提交、来源切换、auth变更与onReady返回。来源切换清空输入/预览；已知进行中的旧来源任务取消，迟到的同会话待处理提交也发取消；旧账号不会自动发后续取消。取消失败显示恢复/取消指引。完成加载期间来源按钮禁用并显示原因。

保留旧三步。初始构筑列表不再自动跳第二步，确保有历史构筑时仍能恢复待完成角色导入；用户可点击第二步或侧栏已存构筑。ready 读取已有 getBuild/getJob，验证 ID 对应、succeeded、result 和空 changes，然后进入第二步，不调用 calculate。手动PoB/XML、官方项目/下载与教学示例合并在第一步次级折叠入口。旧文件 file.text()/旧账号异步回调有守卫，auth变更清空来源与相关输入。

预览只展示白名单标量字段：角色、来源/区服、赛季、等级、职业、升华、读取时间、来源更新时间、完整性。缺项按珠宝、技能、装备/词缀、版本/任务、其他分类计数；默认折叠详情，展开列表限高滚动，所有 path/message 通过 React 文本渲染。补充完整 PoB 文本与确认框直接显示；blocked/failed 同样可补充。cancelled 为终态，提示重新读取，不调用不合法 retry。

手机布局采用已有760/480px断点，新增来源按钮自动换行、预览自适应列、长文字换行和详情限高。实际移动浏览器交互尚待 Task6。

## Chat 与能力边界

新增 `poe2_character_create/get/source/retry/cancel`，operation对应 character_create/get/source/retry/cancel。MCP schema 不允许额外字段；gateway再次核对这些操作的完整参数集合，拒绝 owner/userId 注入。共享 ImportApplication/PostgresImportRepository；Chat worker显式传同一个connect装配，API进程既有Poe2ToolGateway装配从同一POE2 repository的connect构造import app。未另建状态机。

principal 仅取 capability 的可信上下文，issue_capability要求game=poe2。WoW tools/list不展示、tools/call不能派发；capability撤销后调用拒绝。来源/代码/重试/取消通过 ImportApplication 的 owner 与动作幂等校验。

新增预授权写工具精确为 `poe2_character_create`、`poe2_character_source`、`poe2_character_retry`、`poe2_character_cancel`；与已有poe2_import/poe2_calculate同属可信POE2能力范围。get为只读，不新增预授权设置。测试验证POE2名单、WoW无tools覆盖、owner从principal注入、额外owner拒绝、跨owner读取404、撤销失效及MCP schema/operation与gateway allowlist一致。

运行规则与技能明确：长PoB超过Chat 4000字引导Web，不拆分消息；needs_input只解释预览和缺口；ready复用已有成功基线。旧poe2_import分享码/XML行为保留。

## 云端验证

工作目录 `/opt/chickenbro-candidates/poe2-20260918/source`。
Node PATH前缀 `/opt/chickenbro-candidates/poe2-20260918/runtime/node-v22.19.0-linux-x64/bin`；Python `/opt/chickenbro-runtime/bin/python`。

首次结果与修复：
- 首轮typecheck通过，Web/API 10项通过。
- Python首轮78项中77通过、旧预授权名单断言1失败；更新名单断言并保留WoW无权限断言后78项全部通过。
- 相关lint首次2条失败（URL正则control字符与多余escape）；改为显式charCode范围检查后通过。
- 扩展Vitest首轮18项中16通过、2失败：测试遗留未消费的mockImplementationOnce污染后续测试；beforeEach改resetAllMocks后18项通过。
- 对照状态机修正cancelled无retry；保留已有构筑时的刷新恢复入口。最终再次定向验证与构建。

最终命令：

```sh
npm run typecheck
node node_modules/eslint/bin/eslint.js \
 apps/mini-taro/src/web/Poe2CharacterImport.tsx \
 apps/mini-taro/src/web/poe2-character-import.test.tsx \
 apps/mini-taro/src/web/web-poe2.test.tsx \
 apps/mini-taro/src/web/WebPoe2.tsx \
 packages/api-client/src/poe2.ts packages/api-client/src/poe2-import.test.ts \
 vitest.config.ts --max-warnings=0
npm run test:taro -- packages/api-client/src/poe2-import.test.ts \
 apps/mini-taro/src/web/poe2-character-import.test.tsx \
 apps/mini-taro/src/web/web-poe2.test.tsx \
 packages/domain/src/poe2-import.test.ts packages/api-client/src/poe2.test.ts
/opt/chickenbro-runtime/bin/python -m unittest \
 tests.app_poe2_character_tools_test tests.app_poe2_chat_isolation_test \
 tests.app_poe2_jobs_unit_test tests.app_chickenbro_codex_adapter_test -v
```

最终typecheck、定向lint通过；Vitest 5文件18项通过，3.12秒；Python78项通过，0.528秒。正常Vitest include新增API合同测试，Web glob自动收录组件/流程测试。日志：`evidence/link-research/task5-vitest.log`、`task5-python.log`。覆盖两来源误配、ninja确认、国服多类缺口、取消、刷新、A/B迟到、轮询重试、ready复用、旧文件异步隔离、API响应合同及Chat能力。

H5构建参数：

```sh
WOW_APP_ENV=test WOW_TEST_LOGIN_UI=1 \
WOW_H5_PUBLIC_PATH=/poe2-candidate/ \
WOW_API_V2_PREFIX=/poe2-candidate/api/v2 \
WOW_WEB_AUTH_API_PREFIX=/poe2-candidate/api/v2 \
WOW_WEB_CSRF_COOKIE_NAME=__Host-chickenbro-poe2-candidate-csrf \
WOW_BACKEND_API_BASE_URL=https://www.chickenbro.cloud \
WOW_TARO_ISOLATED_BUILD=1 \
WOW_TARO_OUTPUT_ROOT=/opt/chickenbro-candidates/poe2-20260918/task5-web-build \
npm run build:h5
```

H5输出独立目录 `/opt/chickenbro-candidates/poe2-20260918/task5-web-build`，没有覆盖当前Candidate web。日志 `evidence/link-research/task5-build.log`。构建的webpack体积告警不作为运行验收。
最终构建成功，webpack 5.91.0耗时28755ms、2条体积告警；index.html SHA256=`4d75949e72bfad7040013d1f643e78d7b73ad309ccb94e4508c3d4c5560c4fe3`，已读取确认实际输出含index.html/js/css/chunk。

本地 `git diff --check` 通过。未进行服务进程更新、真实Cookie握手、完整三步浏览器/移动端或真实国服业务验收；这些由root Task6集成。真实国服当前仍needs_input，有限映射、珠宝、版本与任务等缺口保持未完成，不把合成/组件测试记作完整国服成功。

## 独立审查修复 round 1（R1 / R2 / R3）

本轮仅修改 `Poe2CharacterImport.tsx`、`WebPoe2.tsx`、`poe2-character-import.test.tsx`、`web-poe2.test.tsx` 和本报告。没有后端、API client、Chat或样式改动；仅传输这4个实现/测试文件，没有重启/发布/提交。

- R1：分离auth生命周期计数和操作epoch。每次显式操作或切源递增操作epoch；轮询cleanup撤销已发出的GET回写，回写同时核对当前importId。恢复GET也绑定开始时epoch及requested id，所以取消/新建后的旧响应不会改packet、sessionStorage或触发onReady。指纹计算仅绑定auth生命周期，操作开始不打断hash；hash稍晚完成时持久化当前已接受的importId，不恢复旧id。
- R2：WebPoe2初始化listBuilds绑定selectionEpoch，手动导入或ready成功装入构筑/基线后使旧初始化结果失效，保留当前选择与真实成功结果。
- R3：废弃任务取消统一经result检查，并核对返回id/status=cancelled；fallback或异常保留id，显示“上一个来源任务未能取消”及“恢复未取消任务”按钮。恢复后回到该来源并可显式取消。无当前任务时还保存该id供同会话刷新；有当前任务时保留当前持久id，废弃id作为同账号内存恢复入口。账号变化/卸载撤销旧生命周期，旧create迟到不续发cancel，旧取消回调也不进入新账号UI。

新增7个受控deferred时序用例：旧poll在取消→同来源新建之后返回；旧restore ready在新建之后返回；初始listBuilds在ready先完成后返回旧快照；迟到create自动取消的fallback与rejection两种失败均可恢复；账号切换后旧create不续发取消；hash迟到仍保存当前id且不保存来源资料。

先仅上传新测试对未修复的云端实现运行：20项中14通过、6失败，准确复现R1两项、R2一项、R3两项和hash完成前新任务无法持久化一项。证据：`evidence/link-research/task5-fix1-red.log`。随后上传两个组件修复：

```sh
npm run typecheck
node node_modules/eslint/bin/eslint.js \
 apps/mini-taro/src/web/Poe2CharacterImport.tsx \
 apps/mini-taro/src/web/poe2-character-import.test.tsx \
 apps/mini-taro/src/web/WebPoe2.tsx \
 apps/mini-taro/src/web/web-poe2.test.tsx --max-warnings=0
npm run test:taro -- apps/mini-taro/src/web/poe2-character-import.test.tsx \
 apps/mini-taro/src/web/web-poe2.test.tsx packages/api-client/src/poe2-import.test.ts \
 packages/domain/src/poe2-import.test.ts packages/api-client/src/poe2.test.ts
```

最终typecheck与相关lint通过；Vitest 5文件25项全部通过，2.20秒，日志 `evidence/link-research/task5-fix1-tests.log`。本轮没有重新运行未修改的Python/Chat测试。`git diff --check`通过。H5使用上文完全相同环境、命令与独立输出目录重新构建，最新日志为 `evidence/link-research/task5-fix1-build.log`。

修复后最终H5构建成功，28166ms、2条webpack体积告警。index.html hash未变（壳文件引用稳定文件名）；完整输出文件SHA256清单为 `evidence/link-research/task5-fix1-web-sha256.txt`，该清单本身SHA256=`a254edef293abdf45f43786390628d2fbf2b8ee95cfdcd4e6c03a6a09ec6e263`。最新构建仍位于 `/opt/chickenbro-candidates/poe2-20260918/task5-web-build`；root可在scoped复审通过后用于Task6。
