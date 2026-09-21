# POE2 角色链接 Task 1 契约报告

日期：2026-09-20  
范围：仅来源 URL、导入领域类型、TypeScript 响应校验器及对应测试。未修改持久化、API、worker、采集器或前端；未提交、推送、部署或重启服务。

## 已实现接口

Python：

- `SourceProvider`: `wegame | ninja`
- `SourceRef(provider, canonical_url, account, league, character, share_id)`
- `parse_character_url(value: str, expected_provider: str) -> SourceRef`
- `ImportStatus`: `queued | fetching | mapping | validating | ready | needs_input | blocked | failed | cancelled`
- `IssueSeverity`: `info | warning | error | blocking`
- `Issue(code, path, severity, message)`；同时导出描述性别名 `ImportIssue`

TypeScript：

- `Poe2ImportProvider`、`Poe2ImportStatus`、`Poe2ImportIssueSeverity`
- `Poe2ImportIssue`、`Poe2Import`、`Poe2CreateImportRequest`
- `isPoe2Import(value)`

`ready` 响应必须同时具有非空 `buildId` 与 `baselineJobId`。其余状态允许这两个 ID 为 null。响应拒绝 owner 字段、未知状态、非法 issue severity、无效 attempt 和时间。

## URL 规则

- 两个入口都必须显式传 `expected_provider`；URL 来源与入口不一致时返回 `POE2_SOURCE_PROVIDER_MISMATCH`。
- ninja 仅接受 `https://poe.ninja/poe2/profile/{account}/{league}/character/{character}`。
- WeGame 仅接受 `https://www.wegame.com.cn/helper/poe2/#/share/{token}`。
- 拒绝 HTTP、用户信息段、非 443 端口、查询参数、伪装域名、额外路径、错位 fragment、编码后的路径分隔符与双重编码。
- ninja 标识只解码一次，保留 Unicode 值；canonical URL 使用 UTF-8 百分号编码。WeGame 分享 token 不写入普通日志的约束由后续调用方落实。

## 云端验证

环境：`wow-lighthouse:/opt/chickenbro-candidates/poe2-20260918/source`；Python `/opt/chickenbro-runtime/bin/python`；Node `runtime/node-v22.19.0-linux-x64/bin`。

RED：

- Python 首次运行因 `server.app.poe2.imports` 不存在而失败，确认测试命中新增接口。
- TypeScript 首次按仓库配置运行时，新文件不在固定 include 中，明确报 `No test files found`。使用云端临时配置运行后发现 ready 测试夹具与“必须有两类结果 ID”的契约冲突；拆分普通状态与 ready 成功态断言后复测。

GREEN：

- `python -m unittest tests.app_poe2_import_urls_test -v`：7/7 通过。
- `python -m py_compile server/app/poe2/imports/{__init__,domain,urls}.py`：通过。
- 临时 Vitest 配置运行 `packages/domain/src/poe2*.test.ts`：2 files、5 tests 全部通过，包含既有 POE2 domain 回归。
- `npx tsc --noEmit -p tsconfig.json`：通过。

临时 Vitest 配置在命令结束时删除，未写入工作区。没有向 ninja 发起 HTTP 请求。

## 独立审查修复

针对 `2026-09-20-poe2-link-contract-review.md` 的两项 finding：

- 新增 Python `ImportPacket` 冻结数据类，完整承载 `id/status/provider/preview/issues/next_action/build_id/baseline_job_id/attempt/updated_at`。构造时验证 UUID、枚举、Issue、非负整数 attempt 及带时区时间，并冻结顶层 preview；`ready` 缺任一结果 ID 时抛出 `POE2_IMPORT_READY_RESULT_REQUIRED`。
- TypeScript `isPoe2Import` 先验证 provider 是字符串，再匹配 `wegame | ninja`，拒绝此前会被 `String(...)` 接受的 `['ninja']`。
- 将 `packages/domain/src/poe2-import.test.ts` 加入仓库正常 Vitest include，回归测试不再依赖临时配置。

审查修复 RED：Python 因缺少 `ImportPacket` 导入失败；TypeScript 对 `provider: ['ninja']` 返回 true，目标断言失败。

审查修复 GREEN：

- `python -m unittest tests.app_poe2_import_urls_test -v`：10/10 通过，其中 3 个 packet 行为测试覆盖合法 `needs_input`、非法/合法 `ready` 与成员验证。
- 标准配置 `npx vitest run packages/domain/src/poe2-import.test.ts`：3/3 通过。
- POE2 domain 回归：2 files、5 tests 通过。
- `python -m py_compile ...` 与 `npx tsc --noEmit -p tsconfig.json`：通过。

本轮审查修复文件：

- `server/app/poe2/imports/__init__.py`
- `server/app/poe2/imports/domain.py`
- `tests/app_poe2_import_urls_test.py`
- `packages/domain/src/poe2.ts`
- `packages/domain/src/poe2-import.test.ts`
- `vitest.config.ts`
- `docs/plans/2026-09-20-poe2-link-contract-report.md`

## 文件清单

- `server/app/poe2/imports/__init__.py`
- `server/app/poe2/imports/domain.py`
- `server/app/poe2/imports/urls.py`
- `tests/app_poe2_import_urls_test.py`
- `packages/domain/src/poe2.ts`
- `packages/domain/src/poe2-import.test.ts`
- `docs/plans/2026-09-20-poe2-link-contract-report.md`
- `vitest.config.ts`
