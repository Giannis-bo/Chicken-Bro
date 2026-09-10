# Chat 有界研究发布

2026-09-10，用户审阅隔离验证报告后明确授权提交发布。源码 `3f0c15d988fd33fd08dae8514f70ee483862c3c8` 已提交至 main、推送，并上线到 API 与 Worker。仅更新7个后端文件，无数据库迁移、依赖或Web改动；后续证据提交不改变运行源码。

## 行为与验证

- Top10、最多3个比较组/深度战斗、5个网页来源、底层查询和事件额度按认证生成累计；原生网页搜索关闭，网页统一经过预算入口。复用现有4个SimC任务上限。跨轮持久化硬预算未实现，仍依靠模型连续性规则。
- 本轮重新运行后端693项、控制面63项通过；[此前固定10次模型验证](../README.md)按受检哈希及影响范围复用，不重复扩样。
- [隔离发布回归](candidate-general.json)：QQ授权URL、CSRF/旧凭证拒绝、真实图片识别、断线续生成、账号忙碌互斥、幂等和第二用户隔离通过。真实SimC任务成功、DPS为正、来源/报告/引擎版本一致；WCL一次窗口统计返回22个事件及9点圣能浪费，回答保留有效治疗解释边界。该测试只有图片与WCL两次模型生成和一个真实SimC任务。
- [正式公网](production.json)：Top100请求约9.91秒完成拒答，来源工具调用0；前两名真实排行榜查询约23.04秒完成，一次来源调用，答案与两条事实一致；单页SimulationCraft官网约20.68秒完成，一次认证public_web调用。三个案例均完成持久化回复、历史读取、断线续生成、第二用户404、幂等回放与会话撤销。
- [公网Web](public-web.json)：14文件SHA256与原发布清单一致。未重建或重发Web，无客户端源码改动。

## 身份与恢复

[精确manifest](manifest.json)绑定正式基底、7个overlay、新源码和Web清单。[前后核对](release.json)证明859个后端文件等于858个原文件加精确overlay，两服务运行目录一致，有效环境及systemd unit/drop-in哈希未变。

发布器持有发布锁，确认Chat/execution/SimC/queue排空并锁定准入后停止API/Worker，原子切换，先启Worker再开放API；未中断真实在途任务。

旧后端 `/opt/chickenbro-releases/badcase-f1f0f0a0d32c5682cae6493766b686f2aba824ac` 保留；Web仍为 `admin-ops-web-8fba1535f226c5dd6eebbcd3980fc2ca52c4075f`。root/0700目录内的0600恢复快照绑定manifest，已校验完整性，未输出凭据。回退仍受空闲门禁约束：

```bash
sudo -n /opt/chickenbro-runtime/bin/python /var/tmp/chickenbro-bounded-release-3f0c15d988fd/deploy.py /var/tmp/chickenbro-bounded-release-3f0c15d988fd/manifest.json rollback
```

[运行与恢复核对](runtime-recovery.json)：首次验证脚本误复用了导入的旧基底Python包，导致web配置断言失败；改用新解释器从目标目录加载后确认实际部署adapter禁用了原生搜索。生产文件未因此变更，公网网页工具回执也验证新入口生效。

未进行生产回切演练或本轮人工QQ登录，不宣称发布后用户体验已验收；没有前后性能/费用对照或大样本稳定性结论。业务验收完成后停止扩样。
