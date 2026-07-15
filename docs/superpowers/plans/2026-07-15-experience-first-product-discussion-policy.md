# 用户体验优先讨论协议实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的“先谈用户体验、后谈实现”规则固化为项目级协作合同。

**Architecture:** `AGENTS.md` 定义所有 agent 的默认表达顺序；`docs/harness.md` 将其接入 Light/Standard/Strict 的需求门禁；`docs/roadmap.md` 指向当前合同与设计。该变更只修改文档，不改运行时代码。

**Tech Stack:** Markdown、Node.js Harness 验证脚本。

## Global Constraints

- 保留用户/其他 session 已有的未提交内容，仅追加本任务的最小变更。
- 不改变运行时代码、数据、部署、验证强度或审批边界。
- 用户侧验收与 Harness 证据/回滚要求必须同时保留。

---

### Task 1: 建立项目级默认讨论规则

**Files:**
- Modify: `AGENTS.md`

- [x] **Step 1: 写入体验优先的默认表达顺序。**

增加用户场景、旅程摩擦、目标体验、用户侧验收、事实/假设边界和技术第二层的固定顺序；规定 Bug 先写用户影响。

- [x] **Step 2: 校验规则覆盖技术例外。**

确认数据真实度、隐私、性能、可用性、降级与回滚会影响用户承诺时仍必须说明，且用户要求技术设计时可以切换主叙述。

### Task 2: 把规则接入当前控制面

**Files:**
- Modify: `docs/harness.md`
- Modify: `docs/roadmap.md`
- Create: `docs/superpowers/specs/2026-07-15-experience-first-product-discussion-design.md`

- [x] **Step 1: 在 Harness 中增加共用讨论门禁。**

明确 Light、Standard、Strict 都以用户体验为默认入口；只读排查不被阻断，但建议、方案与完成声明必须回到用户影响和可观察验收。

- [x] **Step 2: 记录已采纳状态和设计证据。**

在 roadmap 顶部加入已完成的协作治理条目，链接 `AGENTS.md`、Harness 与设计文档；不改写已有历史条目。

- [x] **Step 3: 运行文档/控制面验证。**

Run: `node scripts/verify-project.js --profile harness --release artifacts/releases/2026-07-15-harness-v06-efficiency`

Expected: Harness profile exits `0`; no runtime deployment is applicable.
