# WOW 小程序 14 路由 Target-First 稳定交付

状态：`正在推进`
当前阶段：`共享架构已收口，待固定批次传播`

## 交付目标

以 `artifacts/ui-visual-targets/current/` 的 14 张 canonical target 为视觉事实，以当前 Taro、API/domain、路由和真实状态为业务事实，交付 14 个可编译、可交互、布局稳定并忠实还原目标设计语言的微信小程序路由。

## 唯一执行链

`全量 canonical target -> 设计语言合同 -> 共享 owner 合同 -> 微信三基线 -> 固定路由批次 -> 单路由最终复核`

每一阶段只向下一阶段传递稳定产物：

| 阶段 | 输入 | 稳定产物 | 通过条件 |
| --- | --- | --- | --- |
| 目标固化 | 14 张 canonical target | registry、route inventory、target geometry | 路由、hash、结构、几何和素材角色完整 |
| 事实适配 | target 合同、API/domain | truth adaptation | 所有目标槽有真实字段、状态、动作与 fallback |
| 设计系统 | 全量 route 合同 | token、共享 owner、素材槽合同 | 共享几何不依赖 route-private chrome |
| 三基线 | 共享实现 | `news_home`、`simulator_home`、`news_detail` 微信运行态 | 根页、深路由、TabBar、滚动和原生控件同时稳定 |
| 批次传播 | 已验证共享实现 | news、builds、simulation/profile 三批路由 | 每批只处理目标独有 composition 与真实状态 |
| 最终复核 | 完整运行态 | 每路由一份最终结论和一个核心交互记录 | 14 路由均完成真实微信视觉与交互验收 |

## 共享 owner 合同

| Owner | 唯一职责 | 必备能力 |
| --- | --- | --- |
| `AppShell` | 页面安全区、设计舞台和纵向滚动 | tab-root / pushed 模式；单一滚动容器；390px 设计舞台；统一 top/bottom inset |
| `PageFrame` | 页面标题区和微信胶囊避让 | root / pushed / pushed-action / chat 四种 chrome；稳定高度与标题槽 |
| `ActionButton` / `ControlButton` | 微信控件的统一尺寸与状态 | block、inline、icon-only、disabled、loading；清除原生默认宽度与伪元素 |
| `ProductTabBar` | 四个根页的产品导航 | 四等分、单选、底部安全区和正文占位 |
| `Surface/Frame` | 锻造边框、纹理、阴影与 fallback | 统一层级和稳定几何 |
| `Glyph/Medallion` | 图标、徽章和素材槽 | 明确 fit、裁切、尺寸、亮度、状态与 fallback |

共享缺陷回到共享 owner 修复；route 样式只拥有 canonical target 中独有的内容 composition。

## 固定传播批次

1. news：`news_home`、`news_list`、`news_detail`
2. builds：`specialization_home/builds_home`、`current_spec_workbench`、`build_intel`、`talent_simulator`、`gear_detail`
3. simulation/profile：`simulator_home`、`simc_submit`、`chickenbro_chat`、`tasks_list`、`task_detail`、`profile/templates`

批次内先静态审计共享规则和 route composition，再集中实现，最后统一进入真实运行态验证。单元测试和静态检查用于阻断逻辑回归；视觉通过只读取微信 target/runtime 结果。

## 微信验证策略

- 复用现有唯一 `npm run dev:weapp` watch。
- Automator 单连接运行；connect、调用和总流程均设置硬超时，并在结束时 disconnect。
- 验证优先覆盖三基线和本批次受影响路由，不在每个小改动后运行全量检查。
- 最终截图在一次性隔离上下文读取，主实现上下文只接收结构化几何与差异。
- 每个路由最终记录：viewport、target/runtime 映射、主要区域边界、文字/素材问题、核心交互和验收状态。

## 固定工程门禁

- `npm run audit:ui-architecture`：检查 14 路由与 route 合同完整性、共享 chrome owner、路由安全区边界、原生 Button owner、数据选择器运行时标记和覆盖预算。
- `npx vitest run packages/design-system/src/components/PageFrame.test.ts apps/mini-taro/src/config/babel-data-selector-markers.test.ts`：只验证页头模式与编译选择器契约。
- `npm run verify:ui-baselines`：以单 Automator 连接复核 `news_home`、`simulator_home`、`news_detail` 的真实微信安全区、头部宽度、根页标题槽与二级返回控件。

三项门禁通过只允许进入批次传播；没有 target/runtime 像素复核时，视觉状态保持 `UNVERIFIED`。

## 当前工作包

1. 已完成：文档控制面与活动计划唯一入口。
2. 已完成：`AppShell`、`PageFrame`、原生 Button、数据选择器标记和素材 fit 的共享边界。
3. 已完成：三基线的真实微信结构几何预检；像素视觉复核仍为 `UNVERIFIED`。
4. 下一步：按三批传播，并在每批末完成一次真实运行态视觉与交互验证。

## 完成条件

14 个路由全部满足：微信可编译；安全区和胶囊避让正确；头部、正文、TabBar 和固定输入区互不覆盖；连续滚动成立；目标结构、材质、图标层级和信息密度可见还原；核心交互可用；真实数据和可信边界保持不变。
