# QQ 陪伴角色验收与 Git 交付

2026-09-23，用户反馈“OK，验证了，可以。继续推进。”，确认默认直接发送、按需引用的真实群效果，并授权本批收尾。此前 @ 后文字／表情及未 @ 主动互动均已有用户确认。

本批实现包括 NapCat 独立群通道、炸鸡角色与群观察、成员事实记忆、受限魔兽专业工具、群表情复用与搜索、主动参与和按需引用。线上版本为 20260923-companion-quote-v5；[发布与恢复记录](../optional-quote/release.json)保持原始发布身份，提交内容按其 237 项源码清单逐项核对。

实现提交：`f6f0745770ce7a55db00c930feb1b74dee4fc119`，已推送 `origin/main`。该提交的 237 项 server 文件与正式 v5 manifest 完全匹配；本次仅补验收与 Git 交付证据，不重新切服务。

## 最终验证

- 云端完整后端回归：921 项，920 通过、1 项 Windows junction 检查按平台跳过。
- 项目状态、归属与保留路径控制检查 16 项通过，Git diff 空白检查通过。
- 隔离真实 PostgreSQL：QQ channel、companion 与 Chat durable 共 42 项通过，无跳过。
- 线上 237 项 server 文件与当前本地源码均符合发布清单；QQ 两服务 active，主动参与开启。
- 网站后端与 Web 发布指针保持原版本；公网 app.js 与服务器文件 SHA-256 相同。无客户端修改，无需本批 Web 构建。
- 首版和后续行为变更已完成独立审查，记录见[首版审查](../review.md)、[主动参与](../activation/README.md)与[按需引用](../optional-quote/README.md)。

[机器可读验证记录](verification.json)。记忆和 SimC 已实现且通过真实模型 Candidate 验证，正式群体验仍按实际使用继续核对。隔离开发工作区与原始备份保留。
