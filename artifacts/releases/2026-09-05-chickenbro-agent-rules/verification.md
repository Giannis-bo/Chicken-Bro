# 炸鸡队长规则验证

日期：2026-09-05。实现 commit：`1209850cdb6b601669706602603156a00c15d493`。

## 自动验证

- 本地专项测试 38 项通过：application 与规则加载、热加载、失败关闭、指令/用户数据分离。
- 本地控制面 62 项通过，`git diff --check` 通过。
- 云端隔离源码 `/tmp/chickenbro-agent-rules.11bo6spz` 使用已有 `/opt/chickenbro-runtime/bin/python` 执行 `package.json` 的后端命令，243 项通过，无新增依赖。
- 独立审查无本次可操作缺陷。Windows 完整 adapter 存在已有大小写代理变量及路径分隔符断言差异，Linux 完整套件通过。
- Candidate 使用真实 Astra/high、服务环境与新的 Chat adapter：股票问题及身份绕过固定一句拒答；坦克职责简答；混合提问仅回答治疗职责。详见 `behavior-candidate.json`。
- 部署后正式/测试各两组真实调用通过：将股票问题包装为奥格瑞玛拍卖行仍固定拒答，打断技能问题正常简答。详见 `behavior-production.json`、`behavior-test.json`。

## 部署身份与回滚

- 部署包 SHA256：`4a821967ee680df7e5307aa70934045990f60f5ef96c7d80624f932023545486`。
- 正式服务保留原目录 `/opt/chickenbro`，只覆盖清单的四个文件；不包含其余测试登录分支改动。
- 测试 current 为 `/opt/chickenbro-test/releases/1209850cdb6b601669706602603156a00c15d493`；基础 release 与 Web 构建仍来自 `83b9684b605fa2496db14b81eceb18dc40424c9b`。使用独立 `AGENT_RULES_PATCH.json` 标记后端覆盖，不改写旧 Web 构建身份。
- 正式原文件完整备份在 `/var/lib/chickenbro/agent-rules-backups/1209850cdb6b601669706602603156a00c15d493`；`production-manifest.json` 是脱敏清单副本。原文件内容归一化 SHA 与实施前本地 HEAD 一致，覆盖后 SHA 与实现 commit 一致。
- 初次测试切换因健康检查地址误写成 `/api/v2/ready` 自动回滚；修正为 `/api/v2/health/readiness` 后重新切换，正式/测试所有组件均 ready。旧测试 release 完整保留。
- 只重启两端 API；没有变更数据库、认证凭证、模型配置、Worker 或客户端文件。

## 证据边界

真实模型检查直接使用部署目录的 ChatApplication/NativeCodexChatAdapter 与对应服务环境，没有伪造用户会话或写入用户历史；不能替代 Mini/Web 完整用户验收。话题与语气规则属于模型行为约束，服务端权限仍由原有控制执行。运行态验证不表示 main 已合入或整个测试账号任务已收尾。
