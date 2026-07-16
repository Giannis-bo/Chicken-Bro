# Current UI Control Plane

本目录只保存当前 14 路由重建所需的设计事实、route 合同和最终验收合同。

## 权威映射

| 问题 | 唯一入口 |
| --- | --- |
| 14 路由分别对应哪张目标图 | `target-registry.json` |
| 目标图的可见结构与几何是什么 | route 下的 `target-inventory.json`、`target-geometry.json` |
| 目标内容如何映射真实业务 | route 下的 `truth-adaptation.json` |
| 哪个共享组件或素材槽负责实现 | route 下的 `component-contract.json`、`asset-contract.json` |
| 当前按什么顺序执行 | `docs/plans/2026-07-14-target-first-14-route-rebuild.md` |
| 共享架构是否仍满足 14 路由合同 | `npm run audit:ui-architecture` |
| 微信三基线的结构几何是否稳定 | `npm run verify:ui-baselines` |
| 最终微信验收必须记录什么 | `runtime-review-contract.json` |
| 本轮无人值守交付边界 | `delivery-goal.md` |

`artifacts/ui-visual-targets/current/` 保存 canonical target 本体。目录存在、源码可编译、DOM/AX 元素存在和单元测试通过只证明对应工程事实；视觉状态由 target/runtime 微信复核决定。

## 交付链

1. 14 路由 registry 与 target-only inventory/geometry 完整。
2. 全量目标共同推导设计语言、共享 owner 和素材槽合同。
3. 共享实现先服务 `news_home`、`simulator_home`、`news_detail` 三个代表性基线；结构门禁与微信几何预检通过后再进入视觉复核。
4. 三基线稳定后按 news、builds、simulation/profile 固定批次传播。
5. 每个路由只保留一份最终微信运行态结论和一个核心交互记录。

目标图载荷只进入一次性隔离上下文；主项目会话只接收路径、尺寸、hash、结构化边界、差异和状态。

架构审计与几何预检不是视觉通过。缺少 target/runtime 像素复核时，路由状态仍为 `UNVERIFIED`。
