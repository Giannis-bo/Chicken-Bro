# 14 路由 UI 交付边界

状态：`正在推进`

## 目标

交付 14 个注册路由的微信小程序 UI：共享 chrome 稳定，页面结构忠实于 canonical target，真实数据与交互保持可用，P0/P1 视觉问题清零。

## 范围

- news：`news_home`、`news_list`、`news_detail`
- builds：`builds_home`、`current_spec_workbench`、`build_intel`、`talent_simulator`、`gear_detail`
- simulation/profile：`simulator_home`、`simc_submit`、`chickenbro_chat`、`tasks_list`、`task_detail`、`profile_templates`

## 共享完成标准

- `AppShell` 独占安全区、设计舞台、背景和纵向滚动。
- `PageFrame` 独占 root、pushed、pushed-action、chat 四类头部与胶囊避让。
- `ProductTabBar` 在四个根页保持四等分、底部安全区和稳定选中态。
- 原生控件由共享 adapter 清除微信默认几何；素材槽明确 fit、fallback 和语义。
- 页面私有样式只负责 canonical target 中独有的内容 composition。
- `audit:ui-architecture` 必须通过；数据属性选择器必须由编译层生成同源运行时标记。

## 单路由完成标准

每条路由必须同时具备：

1. 正确的微信 path、viewport、安全区和 capsule bounds。
2. 一份 target/runtime 映射与主要区域 geometry 结论。
3. 无头部、TabBar、固定输入区、文字或组件碰撞。
4. 目标要求的结构、信息密度、材质和素材角色。
5. ready/loading/empty/error 等真实需要状态的稳定几何。
6. 一个核心交互的实际结果。
7. 按 `runtime-review-contract.json` 输出 `PASS`、`FAIL` 或 `UNVERIFIED`。

## 全局完成标准

三基线 `news_home`、`simulator_home`、`news_detail` 先同时成立；随后三个固定批次全部完成。最终 14 路由均有完整 review，P0/P1 为 0，并由用户确认可交付状态。

运行截图、hash、差异和交互结果属于 review 产物，不写回本文件。历史目标、截止时间、执行过程和阶段结论由 Git 保存。
