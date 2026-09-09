# 小程序代码与历史数据清理实施计划

**Goal:** 按 2026-09-09 用户新需求，彻底移除小程序执行代码，清理经确认的旧测试数据，并按实际 Web/QQ 实现整理文档。

**Architecture:** 保留 Taro H5、QQ 网站身份、Web HttpOnly 会话和现有 Chat/SimC 所有权；删除 Mini 页面、传输、微信 provider 与扫码业务实现。历史数据库 migration 和已发布证据保留追溯，不重新执行。

**Tech Stack:** TypeScript / React / Taro H5、Python / FastAPI、PostgreSQL；不增加依赖。

**Spec:** 用户当前四项清理要求。此计划取代 QQ 初次发布中“小程序源码可保留”的决定；数据以本轮确认清单为准。

## 约束

- 已有四份文档 WIP 与未跟踪产物保存原状，叠加修改前留存 baseline patch。
- 不新增依赖或下载陌生来源。用户后续明确授权“OK，合入，提交，发布”，授权本轮提交、已知远端同步、推送及后端/Web 发布。
- 新数据删除必须精确列举用户/记录，排除 QQ 和其他 provider 身份，检查引用和活动任务，并独立恢复验证；不复用历史无备份授权。
- 现有目录名 apps/mini-taro 与 @wow-mini 包名保留为内部地址，避免无关全仓路径迁移；它们不代表小程序产品仍存在。

## 执行与验证

- [x] 前端：删除 pages/auth、pages/chickenbro、pages/simc、Mini 组件、tab bar、weapp 实现及构建工具；删除 Mini auth/传输分支，保留 Web SSE、CSRF、超时与隔离测试。运行 npm run test:taro、typecheck、lint、build:h5。
- [x] 后端：移除微信 provider、旧扫码应用/仓储和配置；保留 QQ、Web Cookie 与拒绝旧认证的回归。运行完整后端及受影响 PostgreSQL 检查。
- [x] 数据：只读核对 live provider、表依赖和工作状态，生成精确清单；得到必要范围确认后，备份、独立恢复验证，再事务删除并校验保留数据。
- [x] 文档：重写 README、架构、路线图、文档地图与当前运维入口；将旧双端说明明确归档，项目状态/owners/验证命令与源码一致。
- [x] 自审所有 diff，运行控制面检查，分别报告本地、云端数据、部署和未完成边界。

## 本轮检查结果

447 后端、259 Web、102 数据库、63 控制面、56 Node 运维及 11 Python 运维检查通过；类型、lint、H5 构建与 diff 检查通过。用户随后明确确认 186 个仅微信账号全部按测试数据清理。已新建私有备份并独立恢复、演练，正式事务删除及保留记录核对通过；18 个 QQ、14 个无关联账号及其记录保留。源码随后已按用户授权提交并发布，结果见下文。详见[记录](../../artifacts/verification/2026-09-09-mini-retirement/README.md)。

数据执行的完整外键、触发器与逐表证据见[数据清理记录](../../artifacts/verification/2026-09-09-mini-retirement/data-cleanup/README.md)。仅在事务内临时停用 `trg_simulation_results_immutable` 并立即恢复，外键始终启用；回滚演练副本保持完整。

## 发布授权与执行

用户明确授权提交、合入与发布。绑定本次源码提交、当前生产基底与逐文件清单，先做隔离验证，再空闲门禁切换 API/Worker/Web，保留旧版本及数据恢复副本。此次不重复执行数据删除。发布证据记录于 `artifacts/verification/2026-09-09-mini-retirement/release/`。

发布已完成：源码 `7adcdeffa3566add1cc9fe33325df5b7360e29df` 已合入推送 main，后端/Web 切换成功。Candidate 与公网均完成真实图片识别、SSE 幂等回放、账号隔离、CSRF 与真实 SimC 队列/报告验证。14 个公网 Web 文件逐字节匹配；既有真实 QQ 会话、历史和工作台浏览器读取正常。本轮未重新进行 QQ 交互授权，未新增生产账号，复用专用合成测试身份且撤销临时会话。见[发布记录](../../artifacts/verification/2026-09-09-mini-retirement/release/README.md)。
