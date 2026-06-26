# 社区模板导入全链路 Runbook

> 适用范围：社区天赋模板、社区装备模板、Raider.IO / WCL / manual fixtures / WebSim baseline 来源、SQLite 入库、`communityTemplates` read model、前端导入 sheet、个人模板保存、`/api/websim/profile` 最终校验、health 和回滚。
> 最后更新：2026-06-26。

本文是“导入社区天赋 / 装备推荐”的执行手册。它不重新定义天赋树规则，也不重新定义装备 catalog；这两部分分别由 [全职业天赋模拟全链路 Runbook](talent-simulation-full-chain-runbook.md) 和 [装备模拟全链路 Runbook](gear-simulation-full-chain-runbook.md) 负责。本文只管外部或派生模板如何进入推荐、展示、应用和保存链路。

## 总原则

- Source honesty：Raider.IO / WCL 是真实玩家样本；manual fixture 是开发或运营种子；WebSim baseline 是后端 authority 生成的兜底模板。不得把 baseline 冒充成社区玩家样本。
- Backend authority：模板能否可视化、可编辑、可保存、可提交 SimC，最终都以后端 validator / serializer 为准。
- Consumer-only frontend：前端只展示和应用后端返回的 `communityTemplates`，不跨专精补模板，不猜装备槽位，不拼 SimC profile line。
- Per-spec cap：天赋模板展示按当前 `classKey + specKey` 收敛，每个专精最多 3 条，不能有重复公开身份。
- Fail-closed import：无法解析成当前 WebSim 节点或 canonical gear snapshot 的模板不能标为可编辑；raw import code 只能走 SimC-only / external 路径。
- Full-spec fallback：真实社区样本不足时，允许用 `websim_baseline` 为每个 expected spec 生成 1 条可编辑天赋兜底；该兜底必须点满三棵树并通过 `encode_websim_talents`。
- No implicit writes：`GET /api/websim/talents`、`GET /api/websim/gear`、`/api/data/health` 都不得触发外部同步或 DB 写入。
- Approval gate：下载、远端刷新、生产 DB 写入、部署和外部数据落盘都需要 owner 明确批准。

## 端到端链路

```mermaid
flowchart TD
  A["Raider.IO runs / profiles"] --> B["profile normalization"]
  C["Warcraft Logs / future sources"] --> B
  D["manual fixtures"] --> E["explicit community sync"]
  F["websim_talents backend authority"] --> G["WebSim baseline generator"]

  B --> H["talent loadout / gear snapshot extraction"]
  E --> H
  G --> H

  H --> I["validate visual/editable state"]
  I --> J["websim_community_talent_templates"]
  I --> K["gear community templates in read model"]

  J --> L["/api/websim/talents communityTemplates"]
  K --> M["/api/websim/gear communityTemplates"]
  L --> N["Mini Program import sheet"]
  M --> N
  N --> O["apply to simulator state"]
  O --> P["save personal template"]
  P --> Q["/api/websim/profile final readiness"]
```

关键点：

- 社区模板是推荐输入，不是规则真相。
- 天赋可编辑模板必须有 `websimExportCode` 和 `talentState.selectedNodes`。
- 装备可编辑模板必须能映射到 canonical slots 和结构化 `gearBySlot / enhancementBySlot`。
- baseline 只解决“全职业专精有可编辑起点”，不代表 BiS、排行榜、玩家样本或强度结论。

## 来源与可信边界

| 来源 | 用途 | 可标为 verified 的条件 | 不可做的事 |
| --- | --- | --- | --- |
| Raider.IO profile / run | 真实玩家天赋和装备样本 | class/spec/hero/scenario 可归属；structured loadout 或 gear snapshot 可解析；去重后仍有可执行字段 | 不能把 profile API 的装备属性当成生产属性来源 |
| Warcraft Logs | 后续高质量战斗样本入口 | 凭据可用、授权边界清楚、样本窗口可追踪、可解析成模板字段 | 缺凭据时不得伪造 WCL 模板 |
| Manual fixture | 小范围开发和 smoke 种子 | 显式 sync 写入；带 source/status/checkedAt；能通过后端 validator | 不能由 GET 自动 bootstrap |
| WebSim baseline | 缺真实样本专精的可编辑兜底 | 当前 `websim_talents` 能生成三树满点状态，且 `encode_websim_talents` 返回 encoded | 不能显示为 Raider.IO/WCL；不能参与玩家强度结论 |
| SimC raw `talents=` code | SimC-only external 输入 | class/spec 已知，raw code 保留原样，profile serializer 可 fail-closed | 不能强行反解到 WebSim 可视化节点 |
| 前端临时状态 | 交互预览 | 只作为待校验输入提交 | 不能作为可信模板或 SimC profile |

## 天赋导入契约

### 入库

`sync_community_talent_templates` 是唯一显式入库入口，当前来源：

- `manual_fixture`
- `raiderio`
- `warcraftlogs`
- `websim_baseline`

每条模板入库前必须经过：

1. `normalize_community_talent_template`
2. structured loadout 解析到 WebSim 节点，或保留 raw external code
3. `encode_websim_talents`
4. signature 去重和 source refs 归并
5. `status=verified|blocked`

`websim_baseline` 额外要求：

- 按当前 `WOW_CLASSES` 遍历 expected specs。
- 每个 spec 只生成默认 hero tree 的 1 条 baseline。
- 通过后端 authority 贪心选点，active 点数达到 `class=34 / spec=34 / hero=13`。
- hero granted root 不计入 purchased SimC line，但必须计入 active 点数。
- 任一树无法点满或 encoding 失败时，该 spec 的 baseline 为 blocked，不进入展示。

### 读取

`GET /api/websim/talents` 必须：

- 只读 DB，不触发 sync。
- 按 `class_key + spec_key` 查询。
- 只返回 `status=verified`。
- 先按 talent signature 去重，再按公开展示身份去重。
- 每个 spec 最多返回 3 条。
- Raider.IO/WCL 等真实样本按 `maxKeyLevel/sampleCount/updatedAt` 优先；baseline 因 `maxKeyLevel=0/sampleCount=0` 只做兜底。

公开展示身份至少包含：

- `sourceKey`
- `playerId` 或可见名称
- `classKey`
- `specKey`
- `heroKey`
- `scenarioKey`

### 前端

前端可以：

- 展示可编辑模板。
- 应用 `websimExportCode` 到当前天赋树。
- 如果模板目标 class/spec/hero 不同，先切换树再应用。

前端不能：

- 自行扩大到其他专精模板。
- 对 raw external code 伪造可编辑节点。
- 把 baseline 文案写成社区玩家样本。
- 绕过 `talentReadiness` 保存可执行模板。

## 装备导入契约

装备模板继续由 `/api/websim/gear` 输出 `communityTemplates`，并遵守装备模拟 Runbook 的 source / variant / mod-option 门禁。

装备导入必须：

- 只应用当前 class/spec 可用的 canonical slot。
- 保留 `gearBySlot` 与 `enhancementBySlot` 结构化快照。
- 对 observed-only、source-reference、partial variant 明确阻断或降级。
- 最终由 `merge_websim_gear_enhancements` 和 `/api/websim/profile` 重新校验。

装备导入不能：

- 直接信任 Raider.IO/WCL 装备属性。
- 把缺 `bonus_id/gem_id/enchant_id/crafted_stats` 的展示候选保存为 SimC-ready。
- 前端按装备名、slot 文案或 item id 猜可执行字段。

## Health 和验收

`/api/data/health` 的 `community_templates.details` 至少确认：

- `templates.total / verified / blocked`
- `sources.manual_fixture / raiderio / warcraftlogs / websim_baseline`
- `scanCoverage.totalSpecCount`
- `scanCoverage.coveredSpecCount`
- `scanCoverage.missingSpecs`
- `dedupedCount`
- `hiddenDuplicateCount`
- `templateRevision`

上线验收必须跑：

```text
/health
/api/data/health
/api/websim/talents?class=shaman&spec=elemental&hero=stormbringer
/api/websim/talents?class=mage&spec=frost&hero=spellslinger
/api/websim/gear?class=mage&spec=frost&compact=1
```

天赋 40 专精矩阵必须检查：

- `specsChecked == 40`
- 每个 expected spec 至少 1 条 verified template
- 每个 spec 展示数 `<= 3`
- 没有 wrong spec
- 没有重复公开身份
- 每条可编辑模板的 `websimExportCode` 可被 `/api/talents/validate` 编码

装备矩阵必须检查：

- 当前 40 spec 的 `/api/websim/gear?compact=1` 可返回 payload。
- `communityTemplates` 不含跨职业 / 跨专精不兼容模板。
- 可应用模板仍由 serializer 返回 `profileReadiness`。

## 只读审计 SQL

```sql
select source_key, source_status, status, count(*)
from websim_community_talent_templates
group by source_key, source_status, status
order by source_key, source_status, status;

select class_key, spec_key, count(*) as verified_count
from websim_community_talent_templates
where status = 'verified'
group by class_key, spec_key
order by class_key, spec_key;

select class_key, spec_key, source_key, count(*) as template_count
from websim_community_talent_templates
where status = 'verified'
group by class_key, spec_key, source_key
order by class_key, spec_key, source_key;

select id, class_key, spec_key, hero_key, source_key, status, json_extract(payload_json, '$.baseline.complete') as baseline_complete
from websim_community_talent_templates
where source_key = 'websim_baseline'
order by class_key, spec_key;
```

## 刷新和发布顺序

1. 确认 owner 已批准外部刷新、生产写库和部署。
2. 备份生产 SQLite。
3. 先确认天赋和装备 authority 当前 health。
4. 显式运行 `sync_community_talent_templates`。
5. 只读审计 source/status/count。
6. 跑 40 专精天赋矩阵。
7. 跑装备 import smoke。
8. 代码热部署。
9. 公网 `/health` 和 `/api/data/health`。
10. 抽样小程序关键接口。
11. 把备份路径、模板计数、coverage 和 blockers 写回 roadmap。

## 回滚

- 代码回滚：回滚 `server/websim_payload.py`、前端 import sheet 相关文件和文档链接，然后热部署。
- DB 回滚：停止服务，恢复写库前 SQLite 备份，重启服务，再跑 `/health` 和 `/api/data/health`。
- 数据局部回滚：如只需撤销 baseline，可删除 `source_key='websim_baseline'` 的模板并重建 `community_talent_templates` sync state；执行前仍需备份。
