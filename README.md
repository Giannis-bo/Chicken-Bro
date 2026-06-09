# WOW Mini Program

魔兽世界辅助小程序，面向正式服与测试服玩家，提供资讯追踪、职业专精 BD 查询、大秘境 / 团本数据专区，以及带 AI 辅助能力的构筑模拟器。

## 项目目标

首版围绕 4 个核心能力展开：

1. **资讯追踪**：关注最新正式服以及测试服资讯，包括游戏玩法、版本变动和职业强度变化。
2. **职业专精 BD 查询**：查询职业专精 BD，包括天赋搭配、毕业装备、属性优先级和输出手法。
3. **大秘境和团本专区**：追踪大秘境天梯榜 top3 队伍阵容及玩家数据，并沉淀团本首领机制、掉落和打法信息。
4. **构筑模拟器**：提供 AI 功能辅助玩家跑 SimCraft、分析 WCL 数据、比较配装收益和定位战斗问题。

## 当前界面

小程序目前采用 5 个底部 tab：

| Tab | 页面 | 说明 |
| --- | --- | --- |
| 最新资讯 | `pages/news/news` | 由 Lighthouse 轻量后端提供正式服、测试服、职业强度动态与来源记录 |
| BD | `pages/builds/builds` | 职业专精、天赋搭配、毕业装备、属性与手法 |
| 副本 | `pages/pve/pve` | 大秘境天梯 top3、队伍阵容、玩家数据、团本专区 |
| 模拟器 | `pages/simulator/simulator` | SimCraft、WCL、配装对比、AI 分析建议 |
| 我的 | `pages/profile/profile` | 角色偏好、收藏职业、订阅与数据源设置 |

## 目录结构

```text
.
├── app.js
├── app.json
├── app.wxss
├── components/
│   └── navigation-bar/
├── pages/
│   ├── builds/
│   ├── news/
│   ├── profile/
│   ├── pve/
│   └── simulator/
├── project.config.json
└── sitemap.json
```

## 本地开发

1. 使用微信开发者工具导入本目录。
2. AppID 使用 `project.config.json` 中的当前配置，或按需要替换为自己的小程序 AppID。
3. 在开发者工具中编译预览。

本仓库不提交 `project.private.config.json`，该文件属于本地开发者工具个人配置。

## 后续方向

- 为 `最新资讯` 后端补充正式域名、HTTPS、微信 request 合法域名配置和刷新记录管理视图。
- 建立职业、专精、天赋、装备和副本数据模型。
- 接入大秘境榜单、玩家分数和团本进度数据。
- 设计 SimCraft 配置生成、WCL 日志解析和 AI 分析链路。
- 增加角色绑定、订阅提醒和收藏管理。
