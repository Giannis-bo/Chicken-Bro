# 2026-09-09 19:00 更新日志发布

已发布：`b48816f1bf610da1fed8db08ccafad59fa13f42e`，main / origin/main / GitHub main 一致。唯一源码变更为 WebHelpDialog.tsx 新增 9 月 9 日六条日志；旧历史保留。

内容依据当前 QQ、截图、全专精、持久化生成、场景实验及反馈按钮各发布证据和运行身份。未添加未发布的 Badcase 批次。

- 本地：改动前后相关 Web shell 13 项测试通过；H5 构建通过，保留两项已有资源体积警告；diff 检查通过。
- Candidate：本地生产构建在桌面/手机浏览器验证五组日期、六条新内容、历史保留、Escape 关闭、无溢出及无页面错误；读取 API 使用 fixture，无生产写请求。云端隔离目录 13 文件 SHA 校验通过。
- Live：发布锁下原子切换 Web 指针，公网 13 文件 SHA 全部匹配、readiness ready；公网真实静态产物的桌面/手机弹窗验证通过，读取 API 同样为 fixture。
- 本次仅静态日志发布；没有重启 API/Worker，没有重新执行 QQ OAuth、真实 Chat/SimC 或第二账号业务验收，不将文案 UI 验证冒称上述业务验收。
- 首次以普通 SSH 用户获取锁被文件权限拒绝，未切换；使用现有 sudo 后成功。

旧 Web `/var/www/chickenbro-web/releases/feedback-ui-d7c10b0711e217251a7cbdc6f81c692317df342c` 保留；新 Web 为 manifest.release。后端保持 `/opt/chickenbro-releases/simc-experiments-7ef8a5dfd9a48de9c9d6c12c660b6564446fd5eb`。发布器在公网哈希或 readiness 失败时恢复旧指针；本次未触发生产回滚，不称恢复演练。远端发布材料在 `/tmp/chickenbro-changelog-20260909`。

未提交的 Badcase 计划、其他任务未跟踪文件和工作区均保留。本证据目录为本地留档，未加入文案发布提交。

## 2026-09-14 本地材料整理

本文为当时发布记录，不表示当前运行版本。保留摘要、manifest、promotion 与结构化验收结果；截图和临时执行脚本已归入经独立恢复核验的私有备份，位置与逐文件哈希见[整理清单](../2026-09-14-local-cleanup/README.md)。历史结果及恢复目标保持原记录。
