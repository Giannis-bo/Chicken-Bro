# G2 持久化生成与查询耗时

状态：`正在推进`；用户已授权定位、通用修复、测试、提交、合入、推送和后端发布。

**Goal:** API 重启不终止生成，Worker 中断有确定终态，复杂研究以实测改进耗时并保留质量。

**Architecture:** PostgreSQL 原子保存消息、run 与待执行记录；独立 Worker 执行并保存公开事件。Worker 自有只读/SimC 工具网关，租约与执行代次保护写入。未开始任务可接管；模型已开始而无法安全继续时失败，不自动重放未知副作用。

**Tech Stack:** 现有 Python / FastAPI / PostgreSQL / systemd / Codex app-server；不新增依赖。

**Spec:** 本任务用户授权；当前架构 `docs/chickenbro-simc-architecture.md`、验证矩阵及生产 Runbook。

## 约束与验收

- 保护 G2 断线后保存、账号互斥、幂等、owner 隔离和双端共享历史；客户端协议保持兼容。
- 不假设 Codex 会话任意恢复；模型执行中断默认明确 failed/retryable。
- 工具结果与阶段持久化仅服务端可见；不保存模型思维链、凭据或公开真实对话。
- SimC 仅云端运行；故障演练仅隔离 Candidate。
- 上线前检查当前线上身份和活动任务，保留可回退代码与 additive schema。

## 执行步骤

- [x] 基线：`artifacts/verification/2026-09-09-g2-durable/` 保存计时脚本及脱敏统计；原问题与同类问题使用同配置，记录工具区间并集、请求重复/重叠、模型总墙钟和非工具区间。非工具区间不冒称纯推理时间。
- [x] 性能：`source_gateway.py` / `wcl_source.py` 按基线确定有界复用及独立查询合并；先写失败测试，验证不同筛选和 owner/run 不混用，异常不缓存为成功，预算耗尽明确不足。
- [x] 持久化：`repository.py`、新 product migration、`application.py` 分离 admission/execution；真实 PostgreSQL 测试证明 admission 原子性、单账号约束、事件有界、终态唯一与过期写入拒绝。
- [x] Worker：`server/app/chickenbro/worker.py` 与现有 Worker bootstrap；工具网关脱离 API 内存，租约心跳、未执行接管、执行中断明确失败。先测试重启/失租不得重复模型及副作用。
- [x] 本地复核：后端、迁移、控制面和相关 ops；审查 owner/dependency 与协议；无客户端变更则不宣称新客户端验收。
- [ ] Candidate：独立数据库/API/Worker，生成中重启 API、杀 Worker、失租写入、单回答/单 SimC、跨端读取与隔离；原问题和同类问题计时及答案证据比较。
- [ ] 已授权发布：精确 commit/manifest，排空与回滚保护，合入推送并刷新线上身份，公网业务回归，更新路线图/发布证据；未完成门禁不宣称闭环。

## 初始核实

2026-09-09 `HEAD = origin/main = f4535c7cde94ab334aac11ea7d68e7395e92c108`。线上 code 指针仍为 `badcase-913d901c7ed3e839cbe611b6037ed71f0848de8f`。本任务工作树干净，独立分支 `codex/g2-durable-generation`；图片输入另有工作树。

历史 417.43 秒记录包含 50 次网关调用：46 个成功请求没有完全相同的 target/options，45 个使用时间窗口。尚无逐次耗时，不能将“重复查询”假说当成实测结论；须区分完全重复、重叠窗口和每次重复获取静态报告数据。

## 发布前新事实

主分支与生产已由其他任务更新为图片输入与 Web-only QQ；当前 G2 验证基于旧版本，不可直接发布。须保护新合同并重新做组合 Candidate。详见本轮 evidence README。
