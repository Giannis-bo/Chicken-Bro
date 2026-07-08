# WoW 小程序 UI v3 Imagegen 素材工作流 Brief

> 本 brief 用于 v3 效果图和后续实现前的素材生产。imagegen 在这里是 App 设计素材工作流的一部分，只负责抽象材质、布局承托和状态氛围，不负责真实 WoW 对象、业务状态或结论。

## 目标

- 为 v3 页面提供可复用的布局素材，而不是整张假 UI 截图。
- 让工作台、资讯、职业 tab、SimC、Chickenbro 使用同一套材质语言。
- 保证每个 imagegen 资产都有用途、边界、压缩版本和 manifest。
- 避免生成假职业、假天赋、假装备、假来源、假数据。

## 输出位置

计划目录：

```text
assets/generated/ui-v3/20260701/
```

每轮生成必须包含：

```text
assets/generated/ui-v3/20260701/manifest.json
```

manifest 必须记录：

- `createdAt`
- `workflow`
- `designBrief`
- `rules`
- `assets[].path`
- `assets[].sourceType`
- `assets[].productionUse`
- `assets[].intendedUse`
- `assets[].forbiddenUse`
- `assets[].realWowObjectInclusion`
- `assets[].derivedFrom`
- `assets[].compression`

## 通用生成规则

所有 prompt 都必须包含：

- no text
- no numbers
- no logos
- no brand marks
- no World of Warcraft UI screenshot
- no class icons
- no talent icons
- no gear icons
- no readable charts
- no fake data table
- no human characters as focal subject

所有生产图都必须：

- 只作为材质、框架、状态氛围或空态背景。
- 保留中间区域文字可读空间。
- 允许裁切为移动端纵向素材。
- 进入代码前压缩，优先 `jpg` 或 `webp`。
- 不覆盖真实 iconUrl、状态文本、阻断原因或来源信息。

## 资产清单

| 资产名 | 生产用途 | 场景 | 规格建议 | 进代码 |
| --- | --- | --- | --- | --- |
| `app-shell-material` | 全局页面底材质 | 全部页面 | source `1536x2732`，mobile `780x1600` | 是 |
| `command-board-material` | 页面 cockpit / 情报头 / 职业控制台头 | 资讯、职业 tab、任务页 | source `1536x1100`，mobile `780x420` | 是 |
| `readiness-slab-material` | 工作台主结论 slab | 工作台首屏 | source `1536x620`，mobile `780x260` | 是 |
| `workflow-rail-material` | 天赋、装备、SimC、队长状态轨或模块舱 | 工作台、职业 tab | source `1536x1200`，mobile `780x720` | 是 |
| `evidence-drawer-material` | 证据展开区 ledger 背景 | 工作台证据展开、队长回答依据 | source `1536x1400`，mobile `780x900` | 是 |
| `source-ledger-material` | 资讯列表和来源账本的低对比底 | 资讯滚动列表 | source `1536x1400`，mobile `780x900` | 视效果 |
| `context-bridge-material` | 从工作台到 SimC / Chickenbro 的上下文桥 | SimC、Chickenbro | source `1536x800`，mobile `780x360` | 是 |
| `task-tabletop-material` | 任务和模板的辅助台面 | 任务列表、个人模板 | source `1536x1200`，mobile `780x720` | 视效果 |
| `empty-state-material` | 空态和 blocked 的抽象占位 | 任务空态、模板空态、blocked 辅助 | source `1536x1200`，mobile `780x720` | 视效果 |

## Prompt 模板

### app-shell-material

```text
Abstract dark iron and obsidian mobile app shell material for a fantasy game analysis console, subtle engraved metal, faint arcane blue circuit traces, smoky depth, restrained gold wear on edges, center kept dark and readable, high-end product UI background, vertical 9:16 composition, no text, no numbers, no logos, no brand marks, no class icons, no talent icons, no gear icons, no readable UI, no fake dashboard, no characters
```

### command-board-material

```text
Abstract command board material for a mobile fantasy intelligence app, dark forged metal frame, aged tactical parchment undertone, subtle brass rails, faint blue arcane map lines, strong readable center area, premium app surface, not a screenshot, no text, no numbers, no logos, no maps with labels, no game UI, no icons, no characters
```

### readiness-slab-material

```text
Abstract readiness status slab for a mobile evidence cockpit, dark iron panel, narrow side status groove, restrained warm gold edge light, subtle red amber blue green atmospheric traces without labels, high contrast readable center, premium app component material, no text, no numbers, no logos, no icons, no charts, no data tables, no game screenshot
```

### workflow-rail-material

```text
Abstract modular workflow rail for a mobile fantasy build simulator app, four empty module bays connected by a thin status spine, dark iron and obsidian, subtle brass bevels, no symbols inside the bays, no text, no numbers, no logos, no icons, no fake buttons, no game UI screenshot, clean readable areas for real app content
```

### evidence-drawer-material

```text
Abstract evidence drawer background for a mobile analytics ledger, quiet dark metal desk surface, fine horizontal grooves for rows, very low contrast arcane blue trace lines, minimal gold separators, designed for readable text overlay, no text, no numbers, no logos, no charts, no fake rows with data, no icons, no characters
```

### source-ledger-material

```text
Abstract editorial source ledger surface for fantasy game news, dark archive paper and iron edge, subtle vertical timeline groove, restrained red and gold edge wear, readable list background, premium mobile news app texture, no text, no dates, no logos, no fake article cards, no icons, no screenshots, no characters
```

### context-bridge-material

```text
Abstract context bridge panel for moving from a build cockpit to simulation or chat, dark iron console bridge, compact horizontal frame, subtle arcane connection lines, empty center for real app text, premium mobile UI material, no text, no numbers, no logos, no icons, no fake charts, no game screenshot
```

### task-tabletop-material

```text
Abstract task tabletop material for a mobile simulation task log, dark archive desk, metal clamps, subtle paper grain, low contrast gold dividers, readable center, no text, no numbers, no logos, no fake list entries, no charts, no icons, no characters
```

### empty-state-material

```text
Abstract empty state illustration background for a fantasy build archive, dark quiet archive shelf and console silhouette, no real objects, no readable labels, no character, no logos, no icons, subdued gold and blue accent, plenty of empty space for real app copy, mobile composition
```

## 视觉边界

### 必须像

- 成熟移动 App 的材质系统。
- 暗铁、奥术、档案、战情、控制台。
- 可承载高密度中文信息的低对比表面。
- 有模块结构，但不预置业务内容。

### 不能像

- 魔兽游戏截图。
- 伪 Blizzard 官网。
- 伪 SimC 报告。
- 伪装备/天赋 UI。
- 普通 AI 紫色玻璃后台。
- 页游皮肤广告图。
- 单纯大背景图。

## 生产流程

1. 先生成 source 图。
2. 视觉筛选：去掉含文字、假 logo、假图标、假 UI 的图。
3. 裁切移动端 production 图。
4. 压缩并记录文件大小。
5. 写入 manifest。
6. 在 current vs target 设计板中标注每个素材的用途。
7. 只有用户确认目标稿后，才把 production 图接入小程序代码。

## 效果图使用规则

Phase 3 的 current vs target 图可以使用这些素材，但必须遵守：

- 左侧必须是真实小程序现状截图。
- 右侧目标稿可以是设计重排，但不能伪装为已实现页面。
- 目标稿中的所有业务文字、状态、数值必须来自当前真实截图或明确标记为结构占位。
- 下方注释必须说明保留了哪些信息、改善了什么。
- 注释区和真实页面内容要视觉分离。

## 接入代码规则

进代码前检查：

- 是否有 manifest。
- 是否无文字、logo、真实对象图标。
- 是否不遮挡中文长文本。
- 是否能在低端机上滚动稳定。
- 是否能在 blocked / partial / source_reference / verified 下复用。
- 是否没有因为素材导致包体不可接受。

建议接入方式：

- 全局底图只放一层。
- 模块材质用 `image` + scrim 或 CSS `background-image`。
- 状态色通过 CSS token 叠加，不为每个状态生成硬编码文字图。
- 真实图标层永远在素材层之上。

## 第一轮生成优先级

1. `workflow-rail-material`：解决工作台四模块不像流程的问题。
2. `readiness-slab-material`：解决主结论 slab 不够有判断感的问题。
3. `command-board-material`：解决资讯和职业 tab 头部普通的问题。
4. `evidence-drawer-material`：解决资深证据区像普通表格的问题。
5. `context-bridge-material`：解决 SimC / Chickenbro 承接感弱的问题。
6. `app-shell-material`：统一页面底，但只保留一层。

## 自检

- 本 brief 没有要求生成真实 WoW 对象。
- 本 brief 没有要求生成业务结论、评分、DPS 或榜单。
- 本 brief 把素材拆成可复用布局资产，而不是整页假截图。
- 本 brief 支持后续 current vs target 效果图和真实小程序实现。
