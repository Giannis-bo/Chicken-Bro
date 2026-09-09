# 截图输入正式发布（2026-09-09）

后端与 Web 已发布并通过公网业务验证。运行源码 `72e6224f21eb0d5fb0635237d454eebe8b845884`，保留 Badcase `913d901c7` 的后台生成、断线落库和来源研究修复。本任务已按后续明确授权合入 main，代码和发布记录一并推送远端；源工作区其他任务的 5 处未提交改动与 54 个未跟踪文件完整保留。线上运行源码仍为上述版本，后续收尾提交仅更新交付记录。用户已授权部署及冲突整合，人工产品验收尚未执行；Mini 后续验证按用户要求免验，本次没有上传小程序。

##  fresh 验证

- 后端 450、独立 PostgreSQL 91（无 skip）、控制面 62、Pillow 解码 4、Web/图片 35、图片与后台生成组合 15 项通过；类型和 lint 通过。H5 构建成功，2 个大小警告，入口 718 KiB。
- 候选空库迁移 0001—0007，实际服务/模型读取图片随机错误码 `YZP6C8PW`；主动断开 SSE 后回答仍落库，账号互斥、owner 隔离、CSRF、限额、上传/发送幂等和历史读取通过。
- 实际 Web 使用候选 API 完成上传、预览、发送、模型回答与刷新历史；无 API 模拟，截图见 web-candidate-sent.png。
- 公网正式 API 独立识别 `7MWWUBT4`，同样验证断线继续、幂等、权限与历史。测试用户已禁用、会话归档、登录凭据撤销，图片进入正常到期策略。
- 新代码包 217 文件逐项 SHA 一致，公网 Web 27 文件 SHA 一致，www/api 两域 readiness 正常，入口启用。详见 live-verification.json、production-smoke.json。

## 部署与恢复

发布路径 `/opt/chickenbro-releases/images-72e6224f21eb0d5fb0635237d454eebe8b845884`；Web `/var/www/chickenbro-web/releases/images-72e6224f21eb0d5fb0635237d454eebe8b845884`。保留上一版后端 badcase-913d901c7 与 Web credit-189d71164，以及配置备份。

Pillow12.3.0 已安装到 `/opt/chickenbro-runtime`；与官方 HTTPS PyPI wheel 的 132 个 PIL/动态库文件逐字节一致，wheel SHA `78cb2c6865a35ab8ff8b75fd122f6033b92a62c82801110e48ddd6c936a45d91`。

备份 `/var/lib/postgresql/chickenbro-images-merged-20260909.dump`，SHA `38175f46ac9a709c86e85bdbccb8627592522118f38e92b9e7b4b6536a402103`；独立库 chickenbro_images_merged_restore_20260909 恢复核对 15 张表与同一快照计数一致。保留数据库与备份，不执行清理。

第一次切换因清理服务缺少 WOW_APP_ENV 失败，零图片绑定检查后自动恢复旧代码/Web、重启并验证 ready。补齐环境，先用相同配置独立 dry-run 通过，再成功切换。该次真实回滚验证不代表已演练有图片写入后的回退。出现已绑定图片或无法确认写入状态时，应保留新历史读取代码并关闭上传，不能回退为旧读者。

chickenbro-image-retention.timer 已启用，每日服务器时间 04:30 执行，Persistent=true；清理服务已成功执行，当前到期数为 0。只清空到期 payload，保留消息和 metadata。归档即时禁止读取、图片七天后可清理。

原始未合并候选/本地证据仅代表先前版本，当前证据以带 merged 的候选结果、production-smoke.json 和 live-verification.json 为准。本目录脚本是精确发布记录，不得脱离 manifest、私有配置和门禁直接重放。
