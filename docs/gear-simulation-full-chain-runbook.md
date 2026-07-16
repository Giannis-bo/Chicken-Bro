# 装备模拟全链路 Runbook

## 适用范围

本手册覆盖 `/api/websim/gear`、装备 catalog、职业专精兼容规则、强化配置、模板导入、SimC serializer、PostgreSQL 同步、health、发布和回滚。

稳定数据规则见 [装备数据库治理](gear-database-governance.md)，产品与路由关系见 [职业专精架构](builds-architecture.md)。

## 不变规则

- Runtime 是 PostgreSQL-only；SQLite 只允许作为显式离线迁移源或备份输入。
- 装备事实先在后端归一，前端只消费 typed payload，不按名称、ID、职业或槽位打补丁。
- `verified` 必须有可追溯 source、当前赛季归属、结构化变体和可执行字段。
- 缺 metadata、变体、属性、来源或兼容证据时返回 `partial` / `blocked` 和 blocker。
- Read API、health 和页面加载不得触发同步、写库或外部下载。
- Serializer fail-closed；展示可用不等于 SimC-ready。
- 生产写库前备份实际 PostgreSQL target；代码与 DB 回滚分别处理。

## 数据链路

```text
Battle.net journal/item metadata + SimC probes + governed rules + observed evidence
  -> PostgreSQL cache catalog
  -> source / item / variant / mod-option / compatibility validation
  -> /api/websim/gear compact read model
  -> Taro gear editor and template snapshot
  -> /api/websim/profile serializer
  -> SimC task
```

## 可信来源

| 来源 | 可以决定 | 不能决定 |
| --- | --- | --- |
| Battle.net Game Data | 物品身份、来源、inventory type、Journal 与套装关系 | 当前实例完整属性、SimC 可执行性 |
| SimulationCraft | 变体属性探测、profile 语法和可执行性 | 官方掉落来源、玩家热度 |
| Raider.IO / WCL observed evidence | 真实玩家使用样本和候选发现 | 规则合法性、BiS、物品属性真值 |
| 仓库 governed mapping | 明确可审计的职业、槽位、制造业和例外规则 | 未登记的外部事实 |

社区截图、攻略和 target 只用于发现问题或表达 UI，不得写成装备事实。

## 核心代码入口

- `server/websim_payload.py`：gear read model、兼容规则、serializer 与 health 聚合。
- `server/postgres_cache_store.py`：PostgreSQL cache 读写。
- `server/postgres_cache_sync.py`：显式同步编排。
- `server/crafted_gear_backfill.py`：制造业受控回填与 dry-run。
- `server/gear_legality.py`：职业专精装备合法性。
- `packages/domain`、`packages/api-client`：typed contract。
- `apps/mini-taro`：消费者 UI。

## Catalog 合同

### Source

每条玩家可见 source 至少包含来源类型、赛季、状态、provenance 和更新时间。Inactive、错季、诊断-only 或无法解释的 source 不进入可选候选。

### Variant

玩家可见 verified variant 必须包含：

- item level / track 身份；
- `itemStats` 或等价结构化属性摘要；
- 生成来源与验证状态；
- SimC 所需 bonus、crafted stats 或其他实例字段；
- 与 source、item 和赛季一致的 revision。

只有 item level、preview stats 或兄弟变体不能把当前 variant 提升为 verified。

### Mod option

Socket、enchant、embellishment 和 crafted stats 必须是独立结构化 option。每项包含适用槽位、兼容条件、状态、显示文案和 serializer 值。Blocked option 不进入默认可选列表。

### Compatibility

后端统一裁决：

- 护甲类型和职业限制；
- 单手、双手、双持、盾牌和 held-in-off-hand；
- 主手占用副手；
- 主属性裁剪；
- unique、套装和美化上限；
- spec-specific weapon rules。

前端不得重新实现这些规则。

## Read Model

`GET /api/websim/gear` 必须：

- 只读 PostgreSQL；
- 即使 stale/partial 也保持完整 schema；
- 返回 `dataStatus`、catalog status、blockers、更新时间和来源；
- 为每个 canonical slot 返回已选项、候选、variant 和 mod capability；
- 保留 `gearBySlot`、`enhancementBySlot`、`replacementCandidates` 和模板所需字段；
- 对不可执行候选明确禁用，不静默补值。

Compact payload 可以裁剪冗余 evidence，但不能裁掉 UI 和 serializer 所需的 source、variant、兼容和状态字段。

## 前端合同

- 页面只展示后端结构化字段。
- 换装备后立即裁剪不兼容的 enhancement draft。
- 两个等价槽位仍使用独立 canonical slot key。
- 真实缺口显示 blocker 或 unavailable，不隐藏整个目标区域。
- 保存模板时持久化结构化 `gearBySlot` / `enhancementBySlot` 和 revision。
- 提交前必须重新经过 `/api/websim/profile` readiness 校验。

## Serializer

Serializer 至少阻断：

- 缺失或 partial variant；
- 错赛季或 inactive source；
- 不兼容武器、护甲或槽位；
- stale / blocked enchant、gem、embellishment 或 crafted option；
- 超量美化、unique 冲突和双手副手冲突；
- 缺失的实例字段或无法解释的 profile line。

Serializer 生成的结果必须可重复，并保留输入 revision 和 blocker。

## 只读审计

每次更新前检查：

1. `/api/data/health` 的 season、gear catalog、stat weights 和 template blockers。
2. 当前 PostgreSQL source/item/variant/mod-option 的 verified/partial/blocked 分布。
3. Verified variant 缺属性、无 provenance、错赛季或 serializer 不可执行的数量。
4. 40 专精 compatibility coverage。
5. 重点规则样本：增强萨、酒仙、狂暴战、冰 DK、法师和盾牌专精。

审计只读，不通过 GET 接口修复数据。

## 更新顺序

1. 明确版本、赛季、实例、套装、制造业和规则变更范围。
2. 运行本地测试与只读审计，列出 blockers。
3. 备份实际写入的 PostgreSQL target。
4. 对支持 dry-run 的脚本先执行 dry-run，核对新增、更新、跳过和阻断数量。
5. 按 source -> item metadata -> variant -> mod option -> compatibility -> read model 顺序写入。
6. 重建 health/read model，抽样 compact payload 和 serializer。
7. 运行 40 专精 traversal 与前端 smoke。
8. 部署后复核 `/health`、`/api/data/health` 和关键 API。

外部下载、依赖安装或新的数据源访问遵循 `AGENTS.md` 的网络规则；已获授权的已知云服务器例行部署按仓库云端规则执行。

## 验证

```bash
python3 -m unittest tests.websim_payload_test
python3 -m unittest tests.gear_observed_backfill_test
node --test tests/builds-page.test.js
npm run typecheck
npm run test:taro
git diff --check
```

远端 smoke 至少包括：

```bash
curl -fsS "$BASE_URL/health"
curl -fsS "$BASE_URL/api/data/health"
curl -fsS "$BASE_URL/api/websim/gear?class=shaman&spec=enhancement&compact=1"
curl -fsS "$BASE_URL/api/websim/gear?class=warrior&spec=fury&compact=1"
curl -fsS "$BASE_URL/api/websim/gear?class=mage&spec=frost&compact=1"
```

测试、HTTP 200 或 40 专精 traversal 只能证明工程和 schema 基础；仍需检查状态、blocker、来源和关键样本内容。

## 回滚

### 代码问题

回退代码并重新部署，不修改可信 DB 数据；复核 health、compact payload 和 serializer。

### 数据污染

1. 停止会继续写入的同步 job。
2. 备份当前异常 PostgreSQL 状态供审计。
3. 恢复本轮写入前的 PostgreSQL 备份。
4. 重启服务并复核 health、关键 payload 和 40 专精 coverage。

SQLite 备份不能恢复为线上 runtime fallback。

### 少量规则错误

仍先备份，再做最小数据修正；规则错误必须同时补代码和测试，不能只改生产数据。

## 发布清单

- [ ] 赛季、实例、套装和制造业范围明确。
- [ ] Verified variant 缺属性和缺 provenance 为 0。
- [ ] Source、variant、mod option 与 compatibility blockers 可解释。
- [ ] 40 专精 compact traversal 通过。
- [ ] 重点武器、护甲、主属性、unique、美化和套装样本通过。
- [ ] Serializer 对 stale 和 incompatible 输入 fail-closed。
- [ ] PostgreSQL 备份路径与写入范围已记录在本次任务输出。
- [ ] 本地测试、远端 health 和 API smoke 通过。
