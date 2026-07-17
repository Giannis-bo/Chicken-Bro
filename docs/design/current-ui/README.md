# Current UI Control Plane

本目录只保存当前 14 路由重建所需的设计事实、route 合同和最终验收合同。

## 权威映射

| 问题 | 唯一入口 |
| --- | --- |
| 14 路由分别对应哪张目标图 | `target-registry.json` |
| 目标图的可见结构与几何是什么 | route 下的 `target-inventory.json`、`target-geometry.json` |
| 目标内容如何映射真实业务 | route 下的 `truth-adaptation.json` |
| 哪个共享组件或素材槽负责实现 | route 下的 `component-contract.json`、`asset-contract.json` |
| 当前按什么顺序执行 | `docs/plans/ui-reconstruction.md` |
| 共享架构是否仍满足 14 路由合同 | `npm run audit:ui-architecture` |
| 微信三基线的结构几何是否稳定 | `npm run verify:ui-baselines` |
| 最终微信验收必须记录什么 | `runtime-review-contract.json` |
| 每条路由必须验证哪个核心交互 | `core-interaction-contract.json` |
| 如何把隔离缓存晋级为不可变运行态 artifact | `npm run promote:ui-review-cache` |

`artifacts/ui-visual-targets/current/` 保存 canonical target 本体。目录存在、源码可编译、DOM/AX 元素存在和单元测试通过只证明对应工程事实；视觉状态由 target/runtime 微信复核决定。

交付顺序、批次边界和验证节奏统一由 `docs/plans/ui-reconstruction.md` 维护，本目录不重复叙述执行流程。

目标图载荷只进入一次性隔离上下文；主项目会话只接收路径、尺寸、hash、结构化边界、差异和状态。

真实微信截图先由 `UI_REVIEW_ROUTES=<route,...> npm run capture:ui-review-cache` 写入仓库外缓存。只有显式提供 `UI_REVIEW_MANIFEST=<absolute manifest path>` 和 `UI_REVIEW_ROUTES=<route,...>` 后，`npm run promote:ui-review-cache` 才会重新核验 PNG 尺寸、字节数和 SHA-256，并复制到 `artifacts/ui-runtime-reviews/<commit>/<viewport>/<sha256>/`。晋级使用不可覆盖写入并生成内容寻址 receipt；它只建立可审计 artifact，不会自动把路由标为 `PASS`。

架构审计与几何预检不是视觉通过。缺少 target/runtime 像素复核时，路由状态仍为 `UNVERIFIED`。

14 路由的当前结论只记录在 `runtime-review-status.json`。该文件必须与 target registry、核心交互合同和 route contract 根目录一致；没有路径包含自身完整 SHA-256 的微信运行态 artifact、全部通过且字段完整的区域与素材语义差异、零 P0/P1/碰撞/裁切/重叠指标、真实核心交互结果和带 UTC 时间的具名人工确认时，不得把任何路由标为 `PASS`。

`core-interaction-contract.json` 的总状态由 14 条逐路由结果推导：存在未验证项时为 `active_unverified`，任一失败时为 `active_failed`，全部真实通过后才可为 `verified`。路由视觉状态不得在对应核心交互仍未通过时晋级 `PASS`。

## 运行素材根

默认微信构建把登记素材复制到 `/assets/ui-v2`，用于本地开发和未配置远端资源的候选构建。只有显式设置合法 HTTPS 根路径时，构建才切换到远端素材并停止复制本地素材：

```bash
WOW_ASSET_RUNTIME_ROOT=https://cdn.example.com/wow-assets/releases/2026-07-18-ui-v2 npm run build:weapp
```

远端根目录必须保持 `packages/design-system/assets/` 下的相对目录结构，并以 `/releases/<release-id>` 结尾；`release-id` 至少 8 个字符且只能使用字母、数字、点、下划线和连字符。未版本化根、`latest`、查询参数、HTTP 或其他协议会在构建阶段失败。该开关只建立可验证的交付路径，不代表 CDN 已获准上线；在真实候选构建启用前，仍须确认完整资产上传与 hash、HTTPS 可用性、微信 request/download 合法域名和恢复默认本地素材构建的方式。
