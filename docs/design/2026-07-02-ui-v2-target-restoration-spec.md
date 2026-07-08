# UI v2 Target Restoration Spec

## Goal

将三张已确认的 imagegen 目标图拆成真实小程序 UI，而不是继续产出静态效果图。v2 优先解决 v1 与目标图的落差：App 壳感、暗铁材质、主视觉层、徽章底座、模块纵深、光影和空间层级。

## Scope

- `pages/news/news`
- `pages/builds/builds`
- `pages/builds/workbench`

## Material Rules

- `assets/generated/ui-v2-restoration/20260702/` 只存放低语义材质：暗铁面板、氛围图、模糊 dock、判定卡氛围和底部装饰。
- 这些素材不得作为职业、专精、天赋、装备、来源、文章事实、readiness、DPS、评分或提升结论。
- 真实 WoW 对象图标必须来自接口 `gameAsset.iconUrl`，或来自仓库内已经验证的官方 icon-name 映射。
- 图文内容、状态、阻断、模板数量、覆盖率、checkedAt 和动作路径仍由真实数据渲染。

## Component Mapping

- App shell：页面使用暗边、顶部光晕、低透明材质，形成统一原生 App 感。
- Object card：职业/专精、当前工作台对象使用真实专精图标加金属徽章底座。
- Hero visual：资讯首屏恢复大主视觉槽；有真实文章图时优先显示真实图，没有时只显示低语义氛围材质和文字 fallback。
- Module dock：四模块状态使用同一套徽章底座、状态点和短指标，保持首屏快速扫读。
- Verdict slab：阻断/部分/可提交状态使用强状态色、明确下一步和可点击主按钮，不输出无证据强结论。
- Evidence ledger：证据区保持高密度行，展开后显示来源、覆盖率、blockers、模板和检查时间。

## Acceptance

- 生成现状 / 目标图 / v1 实现 / v2 实现四列对比图。
- v2 页面截图必须来自已打开的微信开发者工具和真实 AppID 项目，不使用 Web preview 替代。
- 页面不出现 `DPS`、`综合评分`、`S 级`、`A 级`、`提升优先级` 等无证据强结论。
- `assets/generated/ui-v2-restoration` 可通过 `surface-material` 装饰图层进入 WXML，避免小程序 WXSS 本地背景图不渲染；不得放进真实对象图标槽或事实内容区域。
- 不关闭、不重启当前微信开发者工具。
