# 装备模拟隐式种族上下文设计

## 用户目标

玩家导入社区装备模板后，应立刻看到该来源角色口径的非战斗属性；随后换任意装备也不应再次询问种族。手动搭配装备则以人类作为稳定起点。种族不是装备模拟的设置项，不显示、不切换、也不阻塞页面。

## 已确认产品规则

| 进入路径 | 用于本地属性解释的种族 | 用户界面 |
| --- | --- | --- |
| 已验证来源种族的社区模板导入 | 来源角色 `raceKey` | 静默继承 |
| 在该导入状态下换装备、强化或保存后再次应用 | 继承的 `raceKey` | 静默保持 |
| 手动搭配、首次进入、清空选择、历史模板没有来源种族 | `human` | 静默默认 |

玩家不能在装备模拟中更改种族。该规则仅影响 `pages/builds/detail.*` 的即时非战斗属性解释；独立 SimC 页面的种族设置、SimC 请求、DPS 任务和后台 winner 审计均不在本次范围内。

## 数据可信边界

来源种族只接受 Raider.IO 已采集角色 profile 中的可规范化种族值。采集层将其标准化为小写下划线 `raceKey`，逐件保留在 observed-profile ref，并在形成单角色社区模板、Release import evidence 与 public import envelope 时封存。任何缺失、未知、多来源冲突或旧 Release v1 证据都不推测来源种族，改为 `human` 默认。

使用一个只读状态对象：

```json
{
  "schemaRevision": "gear-attribute-character-v1",
  "raceKey": "human",
  "origin": "source_profile"
}
```

`origin` 只用于状态和测试，不向装备页展示。合法值为 `source_profile` 与 `default_human`。页面只把 `{ raceKey }` 传给本地属性规则；没有匹配的 verified 属性规则时继续如实显示“属性资料待补齐”，但不会回到种族选择。

## 架构与状态流

```text
Raider.IO profile race
  -> observed profile ref / community template payload
  -> sealed import evidence (v2)
  -> community-import public template.attributeCharacterContext
  -> detail page gearAttributeCharacterContext
  -> local attribute calculator
```

社区导入的 sealed v2 evidence 将 `sourceRaceKey` 纳入 source fingerprint。历史 v1 evidence 仍可导入，但 projector 明确产生 `human/default_human`，不改变旧 Release、Manifest 或 winner。手动装备选择和 reset 也构造相同的人类默认状态。保存模板将该上下文与 `importOrigin` 一并保存，重新应用不会丢失继承语义。

## 非目标与失败方式

- 不发起导入时的补抓、角色查询或任何额外网络请求。
- 不重新发布、篡改或自动修复已有 Release；后续正常候选刷新才会生成含 v2 evidence 的新 Release。
- 不将来源种族缺失解释为来源角色是人类；只把当前本地计算的默认值设为人类。
- 不依赖 SimC，不改变其 race 选择、profile 或任务结果。

## 验收

1. 有来源 `raceKey` 的社区导入得到 `source_profile` 上下文，换装、强化、保存并重开后仍相同。
2. 缺来源值、历史 v1 evidence、手动起点与 reset 均为 `human/default_human`。
3. 装备页没有种族行、选择 sheet、种族提示或相关事件处理；属性面板仍即时刷新。
4. Community import 继续只有一个既有请求；无 SimC、无 profile 补抓、无 Release/Manifest 写入。
5. 旧 v1 Release import 兼容；新 v2 evidence 的 fingerprint 绑定其来源 `raceKey`。

