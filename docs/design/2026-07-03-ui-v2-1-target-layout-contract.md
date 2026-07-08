# UI v2.1 Target Layout Contract

本文件把三张目标图的标准化坐标转换成小程序 `rpx` 布局约束，用于替代 pass5/pass6 这类在现有页面上局部补边框的做法。

换算规则：标准化目标图宽度 `780px` 对应小程序视口 `750rpx`，即 `1px = 0.9615rpx`。生产实现仍只使用低语义材质切片和真实接口数据，整屏参考图只用于坐标参考。

## Workbench

| 区块 | 目标坐标 | rpx 约束 | 实现 |
| --- | ---: | ---: | --- |
| Nav safe area | `[0,0,780,205]` | `197rpx` | 原生 `navigation-bar`，内容不得压入 |
| Identity panel | `[0,203,780,416]` | `height 205rpx` | `workbench-cockpit` |
| Verdict slab | `[2,437,550,861]` | `height 408rpx` | `verdict-slab`，右侧状态窗保持独立 |
| Status window | `[556,488,736,689]` | `173x193rpx` | `verdict-status-window` |
| Module dock | `[2,886,777,1130]` | `height 235rpx` | `module-band` |
| Evidence ledger | `[0,1156,779,1732]` | `top 1112rpx` | `evidence-section` |

## Builds Tab

| 区块 | 目标坐标 | rpx 约束 | 实现 |
| --- | ---: | ---: | --- |
| Nav safe area | `[0,0,780,150]` | `144rpx` | 原生 tab 页面顶部 |
| Spec console | `[0,156,780,433]` | `height 266rpx` | `builds-spec-console` |
| Workbench panel | `[1,458,779,1001]` | `height 522rpx` | `workbench-entry` |
| Workflow timeline | `[1,1024,779,1543]` | `height 499rpx` | `query-section` |

## News Home

| 区块 | 目标坐标 | rpx 约束 | 实现 |
| --- | ---: | ---: | --- |
| Nav safe area | `[0,0,780,170]` | `163rpx` | 原生 tab 页面顶部 |
| Intelligence panel | `[19,180,759,341]` | `height 155rpx` | `news-command` |
| Hero visual | `[16,359,765,767]` | `height 392rpx` | `banner-card` |
| Channel dock | `[22,794,757,930]` | `height 131rpx` | `channel-grid` |
| Ranked feed | `[16,945,763,1691]` | `height 717rpx` | `highlight-list` |

## Execution Rule

后续改动先满足本表的区块高度、首屏露出和素材层位置，再调细节。任何单个组件为了塞内容把区块撑高，都视为偏离目标图。
