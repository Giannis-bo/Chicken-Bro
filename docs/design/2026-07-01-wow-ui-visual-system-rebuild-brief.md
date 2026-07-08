# WoW 小程序视觉系统重建 Brief

## 目标

把上一轮已经修通的真实链路，升级成一套真正像 App 的“移动端艾泽拉斯分析控制台”。本轮不再证明功能能跑，而是证明真实小程序页面能同时做到：

- 魔兽题材识别明确。
- 真实数据和证据边界不被装饰稀释。
- 首屏有控制台感，而不是黑底卡片墙。
- imagegen 进入素材工作流，但不生成事实 UI。

## 上一轮为什么不通过

上一轮主要完成了产品链路修补：工作台 readiness、SimC 承接、Chickenbro bounded context、截图脚本和禁止无证据强结论。这些逻辑底座要保留。

但视觉失败点也很清楚：

- 过度保守：把“不能硬造数据”误做成“视觉不能冒险”。
- 容器单一：大部分页面仍是黑底、金边、卡片、列表。
- 题材感弱：真实天赋 / 装备图标存在，但没有成为页面身份系统。
- imagegen 断层：生成素材只被登记，没有真正转化为 shell、cockpit、slab、rail 等组件语言。
- 页面孤岛：资讯、职业 tab、工作台、SimC、Chickenbro 缺少同一套 App 壳和状态表达。

## 保留底座

以下内容继续作为真实产品约束：

- 工作台状态模型：`ready_to_simulate`、`blocked`、`partial`、`stale`、`source_reference`。
- 未具备完整 SimC-ready 天赋和装备前，不显示 DPS、综合评分、S/A 级、提升优先级。
- SimC 从工作台进入时继承职业、专精和场景。
- Chickenbro 只解释 bounded context 内的证据和阻断，不编造日志、排名、DPS。
- 真实天赋和装备图标来自 API/read model 的 `gameAsset.iconUrl` / `iconUrl`。

## 新视觉原则

### 页面壳

页面不再只是纯黑滚动容器。核心工具页使用 `console shell`：

- 竖向暗铁 / 烟玻璃材质作为低透明背景。
- 内容中心留白，边缘有结构线和状态氛围。
- 顶部 cockpit 承担当前对象身份，首屏不放大面积装饰图。

### 容器语言

减少普通卡片堆叠，改用以下结构：

- `cockpit`：当前对象、状态、主动作。
- `verdict slab`：唯一主结论和阻断。
- `workflow rail`：天赋 -> 装备 -> SimC -> 队长的流程状态。
- `evidence drawer`：资深玩家证据层。
- `timeline / feed strip`：资讯滚动列表。
- `dock / command row`：页面主动作和快捷入口。

### 真实图标规则

- 真实对象：职业、专精、天赋、装备、地下城、首领等，只能来自 `gameAsset.iconUrl`、接口 `iconUrl` 或受控真实资产索引。
- 缺图时使用短文字 fallback，且不能伪装成真实图标。
- imagegen 不能生成职业、专精、天赋、装备、来源 logo 或任何会被误认为真实游戏资产的内容。

### 状态表达

状态必须比边框颜色更强：

- `blocked`：红色边缘氛围、断点感、主动作指向补齐。
- `partial`：金色警戒氛围，表达“可参考但不强结论”。
- `ready_to_simulate`：绿色可执行信号，但不输出 DPS 或评级。
- `source_reference`：蓝色来源参考，明确不是已验证结论。
- `stale`：过期 / 需刷新表达，不继续强推。

### 密度

高密度不等于小字堆满：

- 首屏只允许一个主 verdict。
- 主 blocker 只保留 1 个，次要 blocker 去 evidence。
- 模块状态要像流程，不像四个等权入口。
- 资讯滚动列表要让标题、来源、时间、状态一眼可扫。

## Imagegen 素材工作流

本轮新增素材位于：

- `assets/generated/ui-redesign/20260701/azeroth-console-material-mobile.jpg`
- `assets/generated/ui-redesign/20260701/evidence-state-strip-mobile.jpg`

这些素材只承担视觉材质：

- 页面 shell 背景。
- cockpit / verdict slab / status rail 的暗铁和烟玻璃质感。
- blocked / partial / ready / source_reference 的抽象氛围。

禁止用途：

- 不从素材中裁切图标、徽章、文字或状态结论。
- 不把素材当作真实地图、来源截图、游戏 UI 截图。
- 不使用素材表达 DPS、评分、排名、提升优先级。

## 旗舰页要求：当前专精工作台

工作台必须先达到目标，再扩展到其他页面。

首屏结构：

1. `cockpit`：当前职业 / 专精 / 英雄天赋 / 场景，带真实图标或明确 fallback。
2. `verdict slab`：一个主结论、一个主 blocker、一个主 action。
3. `workflow rail`：天赋、装备、SimC、队长以流程状态串起来。
4. `template dock`：我的模板是资产入口，不抢主流程。
5. `evidence drawer`：展开后才显示 coverage、checkedAt 的用户化时间、catalogStatus、statSnapshot、blockers。

blocked / partial / ready 视觉必须肉眼可分，不只依靠一行文字。

## 扩展页要求

### 资讯首页

从新闻列表改成版本情报面板：

- 顶部是情报控制台，不重复当第一篇文章。
- 精选故事只放一个主故事。
- 滚动列表更密，突出频道、来源、短时间和状态。

### 职业专精 tab

从入口集合改成职业控制台：

- 工作台为最高优先级入口。
- 天赋、装备、SimC、任务按构筑工作流组织。
- 移除脚手架文案和普通功能卡片感。

### SimC / Chickenbro

- 从工作台进入时必须显式展示当前解释对象。
- 空态要说当前专精缺什么和下一步。
- Chickenbro 建议问题来自 bounded context，不越权扩展为日志 / 排名 / DPS 结论。

## 验收重点

官方小程序截图必须证明：

- 不再是黑色卡片堆叠。
- 工作台视觉强度明显高于上一轮。
- 真实图标来自 read model，不使用臆造图标。
- imagegen 素材只做材质，不输出事实内容。
- 无 `scheduled`、裸 `checkedAt`、长 timezone、`能力 02`、`深入模块`、`旧入口保留`。
- 无无证据 DPS、综合评分、S/A 级、提升优先级。
