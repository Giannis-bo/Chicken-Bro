# 预览就绪的装备属性规则包实施计划

> **For agentic workers:** 用 Harness Strict 作为交付控制面；按任务顺序执行，先写失败测试，再实现最小代码。不得用 SimC、网络请求或异步审计替代本地属性计算。

**目标：** 让装备模拟在微信开发者工具中能对已具备完整来源事实的社区模板和手动换装立即展示可信角色属性；对于来源角色、物品变体或强化事实不完整的历史/异常模板，统一展示“属性资料待补齐”，绝不展示估算最终属性。

**范围：** 只推进版本化规则包、Resolver 静态输入、本地解释器、规则发布和首次真实小程序验证。不会新增在线 SimC 依赖、winner 刷新、数据库 schema、种族入口或后台巡检机制。

**当前约束：** 第一批可发布上下文必须以 `mage:frost:90:dwarf` 和 `mage:arcane:90:night_elf` 两个已封存的官方候选为垂直切片；其它上下文只有在自己的规则、完整输入和黄金样本齐全后才能加入。不能把这两个样本的常数外推给任意职业、专精或装备。

## 成功标准

- 页面属性计算只在本地发生；导入、换装、宝石/附魔调整后不发起 SimC 请求，也不等待审计任务。
- 对一个已发布、完整的规则上下文，主属性、耐力、各绿字 raw rating 与黄金样本的 canonical 输入逐字段相等；转换百分比与官方未舍入值相差不超过 `0.01` 个百分点，显示取整与英雄榜一致。
- 规则、来源角色、物品变体或强化事实任一不完整时，页面没有最终属性数字，状态为“属性资料待补齐”；不会回退到装备词条合计或人类默认值伪装最终面板。
- 已验证社区来源的种族继续静默继承；在该模板上换装/强化后保留；手动和默认场景仍使用人类，无 UI 入口。
- 首次规则启用之前完成候选部署、API/read-model smoke 和真实微信开发者工具的导入、换装、降级三条路径验证；若验证未通过，公开规则包保持为空，回滚为 `rule_unavailable`。

## 任务 1：固化“可计算或待补齐”的输入合同

**文件：**

- 修改：`server/gear_resolver.py`、`server/pg_gear_authority_loader.py`
- 修改：`server/gear_attribute_api.py`、`pages/builds/detail.js`
- 修改：`tests/gear_resolver_test.py`、`tests/gear_attribute_api_test.py`、`tests/builds-page.test.js`

1. 为 Resolver 的 `staticAttributes` 增加完整性输出：物品、变体、宝石、附魔、美化的每一个已选输入都必须有 canonical stat facts 或明确的 `ATTRIBUTE_STATIC_FACTS_UNAVAILABLE` 问题；不得把缺失 option 的空对象当成零属性。
2. 写失败测试：完整 Resolver snapshot 可被属性引擎消费；缺一项强化事实时，服务端参考结果和页面都不能产生最终数值，只返回“属性资料待补齐”。
3. 仅在 `resolverContext.status=verified`、`staticAttributes` 完整、种族上下文可解析且发布规则适用时构造本地计算输入。保留现有 raw 选装展示，但与最终角色属性严格区分。
4. 跑：
   ```bash
   python3 -m unittest tests.gear_resolver_test tests.gear_attribute_api_test
   node --test tests/builds-page.test.js
   ```

## 任务 2：建立两个黄金样本的可复核 canonical 输入

**文件：**

- 修改：`tests/fixtures/gear-attribute-armory-v1.json`
- 修改：`tests/fixtures/gear-attribute-calculator-cases-v1.json`
- 修改：`docs/gear-attribute-rule-source-ledger.md`
- 新增（如需）：`tests/fixtures/gear-attribute-resolver-inputs-v1.json`
- 修改：对应 Python/Node 测试文件

1. 从已封存官方 Profile 的 15 槽 item level、bonus、宝石、附魔和活动天赋构造可复算的 Frost Dwarf 与 Arcane Night Elf Resolver 输入。每个数值必须能追溯到官方 Profile、本地物品事实或离线 SimC/DBC 审计来源；不允许人工补常数。
2. 写逐字段失败测试，覆盖：智力、耐力、生命/法力、暴击、急速、精通、全能、闪避、吸血、速度的 raw 与未舍入 percentage/effect。Frost 与 Arcane 的候选状态保持 `candidate`，直到全部字段断言通过。
3. 对已确认事实写入项目受控 option/static facts；对仍缺失的事实保留显式问题。不要进行全库补数或更新 winner。
4. 运行两端共同 fixture，确保 Python 参考计算器和 JavaScript 本地解释器对象完全一致：
   ```bash
   python3 -m unittest tests.gear_attribute_engine_test tests.gear_attribute_rules_test
   node --test tests/gear-attribute-engine.test.js
   ```

## 任务 3：把公式证据变成可发布规则，而不是样本补丁

**文件：**

- 新增：`server/gear_attribute_rulebook.py`
- 修改：`server/gear_attribute_rules.py`、`server/gear_attribute_engine.py`
- 修改：`pages/builds/gear-attribute-engine.js`
- 修改：`tests/gear_attribute_rules_test.py`、`tests/gear_attribute_engine_test.py`、`tests/gear-attribute-engine.test.js`
- 修改：`docs/gear-attribute-rule-source-ledger.md`

1. 定义受控的 `ACTIVE_ATTRIBUTE_RULEBOOK`。只允许 `verified` context 进入运行时；candidate、fixture_only 和缺样本 context 必须被 validator 拒绝。
2. 将法师基础属性、种族基础差异、等级 rating、递减曲线、稳定天赋、资源和顺序编码成声明式规则：
   - 装备 raw 值与可证实的稳定修正在 `stableModifiers` 阶段处理；
   - rating 曲线在 `ratingTransform` 阶段处理；
   - 只把已逐字段验证的常态百分比修正写入 `postConversionModifiers`；
   - 任一战斗/触发/持续时间条件效果保留为 `conditionals`，不改变基础面板。
3. 写失败测试禁止以下情形：线性 `ratingPerPercent` 进入 verified context、曲线/等级缺引用、样本 identity 与 rule context 不一致、或一个未知天赋 effect 悄悄计入最终数值。
4. 为每一个晋级规则在 ledger 记录 revision、源码、黄金样本、字段覆盖、核验时间和未覆盖项。只有两个样本都从 candidate 转 verified，才允许启用对应 context。

## 任务 4：受控发布到现有 gear payload 和本地页面

**文件：**

- 修改：`server/websim_payload.py`、`server/news_backend.py`
- 修改：`pages/builds/detail.js`、`pages/builds/detail.wxml`、`pages/builds/detail.wxss`
- 修改：`tests/websim_payload_test.py`、`tests/news_backend_test.py`、`tests/builds-page.test.js`

1. 让运行时 payload 从 `ACTIVE_ATTRIBUTE_RULEBOOK` 返回只读、可解释的 `attributeCalculator` context；未覆盖职业/专精/等级仍返回当前有问题码的 `rule_unavailable`，不暴露 candidate 规则和角色身份。
2. 页面在同一 `setData` 更新中调用纯 JS 解释器：导入完成、物品切换、宝石/附魔/美化改变、保存重放都立即重算。不得调用 `gear/stat-snapshots`、等待网络或读取 SimC 状态。
3. 展示每项绿字的 `raw rating + converted percentage/effect`；只在所有输入完整时显示。缺来源/强化事实统一显示“属性资料待补齐”，不出现种族入口、估算或误导性的数值。
4. 测试应证明：同一社区模板导入后的本地换装立即改变例如急速 `100 → 200` 的 raw/percent；手动人类路径无 race UI；不完整模板没有数字；已有 SimC 快照状态改变不影响本地最终属性行。
5. 跑：
   ```bash
   python3 -m unittest tests.websim_payload_test tests.news_backend_test tests.gear_attribute_api_test
   node --test tests/gear-attribute-engine.test.js tests/builds-page.test.js
   ```

## 任务 5：候选部署与真实微信开发者工具预览

**前置：** 仅当至少一个 context 已在黄金样本逐字段通过并进入 `ACTIVE_ATTRIBUTE_RULEBOOK` 后执行。本任务之前不得启用公开规则。

1. 用候选分支部署，不触发异步同步（`WOW_DEPLOY_START_ASYNC_SYNCS=0`）。记录 commit、运行时文件哈希、`/health`、`/api/data/health` 与 Frost/Arcane 16 槽 gear payload 的 `attributeCalculator` 状态。
2. 在现有、已登录的微信开发者工具项目中低扰动打开装备页；不关闭/重启 DevTools，不清缓存，不切 AppID。使用单条短路径验证：
   - 导入一个已验证的社区模板，记录黄金样本的属性；
   - 切换一件装备，确认本地属性同次交互更新且没有 SimC/属性审计等待；
   - 导入缺强化/来源事实的 fixture，确认只有“属性资料待补齐”。
3. 使用现有 DevTools CLI/自动化端口仅作必要的项目打开或截图；若 DevTools 不稳定，立即停下批量自动化，保留候选 fail-closed 状态并记录 blocker。
4. 将 API、两端 fixture、DevTools 截图/操作记录、SimC worker 不参与证明、rollback probe 写入本次 release evidence。候选或真实小程序任一失败，撤销该 context 的发布，而不是降低误差门槛。

## 收口与扩展原则

- “任意模板”只意味着一旦其完整规则和静态事实存在，任意组合均由同一本地解释器即时计算；并不允许未知专精、变体或强化以估算冒充准确结果。
- 此计划的首个预览只承诺已验证的 Frost Dwarf / Arcane Night Elf 垂直切片与明确降级路径。其它职业/专精按照同一 source ledger + golden sample 流程逐个加入，不复制样本特例。
- 不在本计划中实现新巡检、自动修复、SimC 服务或数据全量回填；具体历史/异常模板出现后，先保存其事实和问题码，再单独分析原因。
