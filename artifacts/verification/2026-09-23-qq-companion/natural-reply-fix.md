# QQ 自带表情与轻互动修复

用户反馈截图：仅 @炸鸡 发送 QQ“耶”表情，却收到“在呢，啥事？你这条附件我没看到内容。”

## 根因与改动

- 正式 OneBot 历史回读确认原消息是 at + 空白 text + face(id=355)。旧 companion 解析只保留文字，所有 face 都标为 attachment；模型因此拿到空白内容和附件标记。
- 从已部署 QQ NT face_config.json 提取 282 项系统表情 id/名称，355 对应“耶”。[来源与校验](face-name-source.json)。仅使用可信本地映射，消息自带 name 不进入映射。
- 当前群文本按消息段顺序保留表情语义；未知表情只标注 QQ 表情，不虚构含义。face 不标附件，混合图片仍保留 attachment=true。没有新增数据库字段，历史兼容。
- 角色提示调整：先回应情绪与关系，表情、哈哈、招呼不默认变成待办，不默认追问“啥事”或讨论附件识别；不强行网络梗，不每句话自称鸡哥。对方确实请求识图时仍如实说明可见内容。

## 验证

新增 3 项回归先红后绿：真实表情语义/顺序、未知 ID、不把混合图片当纯表情。云端隔离 PG/Python 36 项相关测试通过。

[真实模型经 parser → 隔离 observations 持久化 → 模型输入](candidate-natural-replies.json)：

| 输入 | 实际输出 |
| --- | --- |
| QQ“耶” | 耶✌️ |
| 哈哈哈哈 | 哈哈哈，笑得都传染了 |
| 终于下班了 | 可算熬到了，出门那口空气都自由了。 |

独立只读审查通过：可信名称映射、真实 @ 边界、混合附件和数据库兼容无新增阻断。模型测试为 Candidate，不冒充正式群可见验收。

## 发布

[发布记录](natural-release.json)：QQ 版本 20260923-companion-social-v3，私有 QQ 备份经独立恢复逐表行数核对，236 项 server 文件与[源码清单](natural-release-manifest.json)匹配；[正式进程与解析回读](natural-readback.json)确认 QQ 两服务 active、face=耶 且 attachment=false。网站进程/代码/Web 指针未变，readiness ready，NapCat 未重启。主动参与开关仍关闭。原工作区 WIP 保持，未提交或推送 Git。
