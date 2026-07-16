# WOW Mini Program Design Contract

状态：`正在推进`

## 权威入口

前端设计与实现只读取：

1. `docs/plans/ui-reconstruction.md`
2. `docs/design/current-ui/target-registry.json`
3. 当前 route 在 `docs/design/current-ui/routes/` 下的合同
4. 当前 Taro、API、domain 和业务源码

目录存在、源码可编译、组件名称、素材数量或 Git 历史都不构成视觉证据。

## 事实优先级

1. Canonical target 决定可见元素数量、顺序、分组、层级、几何、密度和素材角色。
2. 当前 API/domain/route 决定真实值、状态、动作、导航和可信边界。
3. Truth adaptation 明确解决两类事实的差异。
4. 组件、token、资产和测试由前三项推导，不能反向修改 target。

## 视觉语言

- 暗色、高密度、游戏原生且可读。
- 金属与金色表达层级和状态，不做无意义装饰。
- 内容、证据和操作优先于纹理。
- 页面必须有清晰的大区节奏、稳定内边距和跨路由对齐。
- Product TabBar 是四等分产品 chrome；激活态不改变列宽或文字位置。
- 不绘制假的微信状态栏、时间、电量、Wi-Fi 或胶囊。
- 页面不得因 viewport 宽度任意缩放字号；文字、图标和固定格式区域必须有稳定尺寸。

具体颜色、字体、间距、圆角、边框、阴影、材质、图标与布局数值只从 canonical target inventory 固化，并记录到当前 route 合同；不能从现有 CSS 猜测。

## Target-Only 测量

- 每条路由先在一次性隔离视觉上下文中只读取 canonical target。
- 输出 target hash、native width/height、region pixel bounds、normalized bounds、层级、文字、数量、对齐和素材角色。
- 测量合同必须声明 `runtimeInputsUsed=false`。
- Runtime、现有 CSS、review 结果、组件和素材不得参与 target 坐标测量。
- 不确定项保持 `unresolved`，不得用实现现状补齐。

## Truth Adaptation

每个目标槽必须登记：

- 真实字段或确定性派生规则；
- loading、empty、error、stale 与 blocked 表达；
- 点击、切换、收藏、跳转或禁用行为；
- 来源、更新时间和可信状态；
- 缺值时保留结构的 fallback。

任何目标数字、标题、来源、身份或物件图都不能直接当作线上事实。

## 组件规则

- `packages/design-system` 是实现表面，不是完成证明。
- 每个 owner/variant 必须在当前 canonical target 上证明结构和视觉能力。
- 能力不足时扩展或重做组件；不得删除目标内容、压平布局，或把独特结构强行做成 generic card/table。
- 共享缺陷在共享 owner/token 修复；页面只拥有真正独特的 composition。
- 同一语义 owner 在不同路由保持同一 DOM、状态和素材槽合同，route variant 只表达目标中确实存在的差异。

## 素材规则

- Production asset registry 初始为空。
- Runtime utility icon 可以支撑功能，但不能自动充当目标设计素材。
- 每个可见素材槽记录 owner、语义、比例、裁切、密度、状态、fallback 与适配证据。
- 真实 WoW class/spec/talent/item/source 资产只能来自已验证来源或后端映射。
- Imagegen 只生成无事实含义的纹理、材质、框体、socket、氛围和装饰。
- 新素材按共享家族统一生成、切图、压缩和注册，不从 target 随意裁切成线上事实。

## Runtime 规则

- 保留 Taro 4、React、strict TypeScript、typed API/domain、导航、storage、auth、cache 和 fail-closed 行为。
- 微信真实运行态是唯一平台视觉门禁；源码测试只证明逻辑，不授予视觉通过。
- Loading 保持最终页面主要几何，不能出现空白首屏或与已有数据重复渲染。
- Ready、loading、empty、error、stale 至少覆盖当前路由真实需要。
- 微信差异回到共享 Taro 源码修复，不编辑生成后的 WXML/WXSS。
- `AppShell` 是页面顶部和正文底部安全区的唯一 owner：它发布运行时变量并由 `shellBody` 消费；`PageFrame`、route composition 和 route-private CSS 不得再次叠加安全区。
- `PageFrame` 是微信右上菜单胶囊排除区的唯一 header owner；标题、来源、状态和动作控件都必须在胶囊左侧保留至少 8px 间距，route-private CSS 不得自行搬移头部控件。
- 微信 custom TabBar 与页面树隔离，因此 `TabBar` 必须独立读取同一套运行时安全区；外壳贴到真实窗口底边，四列交互内容停在底部安全区上方。
- 四个 Tab 根页必须在单连接微信运行态验证标题起点、header 控件与菜单胶囊无碰撞、TabBar 外壳底边和交互区底边。

## 视觉门禁

- Capture 使用真实 CSS viewport 和 DPR2 原生输出。
- 人工板默认以固有尺寸显示 canonical target 和 DPR2 runtime，`1 source px = 1 CSS px`，禁止 CSS 缩放；对齐、叠加和差异模式可将 target 等比缩到 runtime 的 DPR2 宽度，但必须记录变换与交集裁切，且不能替代默认原生视图。
- Target/runtime 映射必须保持比例并记录裁切；禁止无声明拉伸、填白或错位补齐。
- Geometry gate 只读取 target-only 坐标。
- Pixel/edge 差异用于阻断明显全页漂移，不能以 DOM 数量、构建成功或 owner 存在替代。
- Agent 完成 target/runtime、overlay/diff、大区 geometry、文字和素材自检后，才可提交人工验收。
- 自动门禁和 isolated review 都不能替代用户结论。
- 未通过微信三基线的共享实现不得传播；用户指出的视觉事实必须先回到共享 owner 或 route owner 修复。
- 所有视觉债务必须在最终 14 路由交付前清零或由用户明确接受。

## 图片隔离

- 主 session 不使用 `view_image`，不读取或回传 PNG/base64/data URL，不嵌入 Markdown 图片。
- 主 session 不读取 imagegen task/thread 历史；即使关闭 output inclusion，完成记录仍可能序列化整段 PNG。只用隔离 agent 状态与文件路径、mtime、bytes、hash 判断完成。
- 一次性隔离上下文一次只复核一个 target 或一对 target/runtime。
- 主 session 只接收路径、尺寸、hash、结构化边界、差异和状态。

## 完成

单路由依次达到：

`target_measured -> truth_adapted -> component_asset_ready -> implemented -> isolated_visual_review -> human_review`

全局完成要求 14 个路由全部通过真实微信视觉与核心交互，0 target/truth/component/asset gap，并由用户明确授权 cutover。
