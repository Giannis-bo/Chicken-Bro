# WCL 工具效率正式发布

2026-09-10，用户明确授权“是的，提交、合入、发布”。源码 `f95f6bbe234a2da8a67ca86466e96c6c29c6b794` 快进合入 main 并推送；本批五个后端运行文件已部署，API 与 Worker 同版本。后续证据/文档提交不改变运行源码身份。[结构化结果](release.json)。

## 验证

- 复用同一运行源码的 667 项后端、63 项控制面测试及两道真实模型对照，没有全套重跑或扩样本。
- [隔离 Candidate](candidate.json)：现有独立数据库、临时 API/Worker；QQ 授权 URL、CSRF/旧凭证拒绝、真实图片识别、断线续生成、账号并发、幂等、第二用户隔离通过。真实 SimC 完成且 DPS 为正，来源及版本核对通过。
- 隔离和[公网 WCL](production.json)各一次完整 HTTP/SSE 对话。真实持久化工具结果均为一次 Resources statistics、22 个角色事件、9 点圣能浪费，窗口及完整性一致；回答保留“资源浪费不能直接推算有效治疗损失”。公网第二账号返回 404。
- [Web 验证](public-web.json)：公网 HTTPS 14 文件 SHA256 与原 Web 发布清单一致。首次本机 Python 3.13 证书校验报 Missing Authority Key Identifier；改用云端现有 Python 经公网 HTTPS 验证成功，未禁用证书检查。
- [运行身份](runtime-final.json)：API/Worker cwd、五个文件、完整原版/候选目录、有效环境哈希、systemd unit/drop-in 哈希及 Web 指针一致；生产业务完成后再次确认。测试短期 Session 已撤销，临时 Candidate 进程已停止；生产复用既有专用测试身份，没有新建生产身份。

## 发布与恢复

[manifest.json](manifest.json) 绑定基底逐文件清单、五文件 overlay、Web 清单与环境摘要。[deploy.py](deploy.py) 复用仓库空闲门禁发布器，仅把白名单限定为本次五个文件；先预检和 staging，再在数据库门禁下确认 Chat/SimC/队列排空，停止 API/Worker，原子切换，先启动 Worker 后开放 API。

旧后端 `/opt/chickenbro-releases/badcase-fe4c35f8bb544a2066bfb804b5f00142ab8731bd` 与原 Web 完整保留。恢复 manifest 与包含配置的快照仅位于云端 root 私有目录 `/var/tmp/chickenbro-wcl-release-20260910`（700；快照 600），内容不进入仓库；已校验快照绑定及完整性。必要时由发布操作员运行：

```bash
sudo -n /opt/chickenbro-runtime/bin/python /var/tmp/chickenbro-wcl-release-20260910/deploy.py /var/tmp/chickenbro-wcl-release-20260910/manifest.json rollback
```

恢复同样受空闲门禁约束，不能中断真实在途任务。未执行生产回切演练；没有数据删除、配置修改或数据库回滚需求。未重复人工 QQ 登录，不将自动业务检查称为用户体验验收。所有指定检查通过后停止，未再增加模型样本。
