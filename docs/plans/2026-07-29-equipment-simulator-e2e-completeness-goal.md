# 装备模拟端到端完整性验证 Goal

**状态：** `blocked`（2026-07-31 截止收口；未达到完整性和全矩阵完成门禁）

**Harness 分级：** Strict，多阶段 Goal；每个会改变数据、Catalog、运行时或发布状态的切片必须使用自己的唯一 task-scoped release packet。
**用户目标：** 玩家在真实微信小程序中浏览、导入、编辑、保存并模拟当前赛季 PVE 装备时，看到的是完整、合法、可追溯且可执行的后端事实；不能漏装备，不能把 `partial` / `blocked` 包装成通过，也不能靠视图绕过上游问题。

## 1. 当前事实

- generation 35 和 Phase 0-4 是已归档 v1 基线，不是本 Goal 的当前验收证据。
- 当前 `manifest-catalog-detail-contract` 仍是 Catalog Browse 纠偏切片；其旧候选、微信包和 evidence 绑定 `da051891`，不能证明后续 `d1006712` 及其之后的源码。
- 现有 40 专精 shadow 从同一 Catalog 投影 public candidates，只能证明集合内部映射自洽，不能证明官方当前赛季 PVE 来源宇宙没有漏 instance、encounter、difficulty 或 item。
- Journal 摄取存在 instance、raid、encounter、item 容量上限；当前没有逐项记录所有因容量、失败或 fallback 未进入 staging 的关系。
- 当前来源政策已为 19 类必需来源逐项写入官方有效窗口；新增的第 19 类是此前被漏掉的 Revelations Val/Naigtal 世界内容稀有怪装备池，它与同区域世界 Boss 掉落不是同一来源。政策仍是 `required_membership_discovery`，不能批准正式 Universe。
- 用户已明确批准把官方来源、有效窗口和成员快照下载到本 Goal 隔离证据目录。当前已校验 24 个 Blizzard 权威页面、335 个 Game Data 响应和 SimC 客户端物品快照；没有同步生产、没有切正式指针。
- 当前官方投影为 19 个来源中 `complete=0`、`partial=9`、`blocked=10`，保留 1871 条原始关系和 21 条显式缺口。build 68887 客户端关系已把 172 个制造配方输出和 1412 个唯一 Journal `source + instance + encounter + item` 难度关系完整回连，关闭了 recipe-output 与 6 条 Journal difficulty 缺口；剩余缺口是 9 条 progression、10 类无官方成员 API 的来源和 2 条 transform eligibility，故必须继续 `blocked`。
- 随后的受控客户端关系审计又抓取并解析了 7 份官方 DB2，隔离目录现有 58 份 raw DB2。唯一带奖励行的 expansion-11 Mythic+ 候选 season `117` 可见完整 `+2..+10` 周常装等，但 end-of-run 全为 `0`，且缺少把数值 season ID 绑定到 Midnight Season 1 的官方 join；`RenownRewards` 能精确证明满级项链、腰带、头部、饰品四个 power unlock 和三条 Delve 进度解锁，但相关 `item_id` 全为 `0`。因此 `current-client-progression-investigation.json` 按字面为 `blocked`，本轮没有把 21 条缺口中的任何一条伪装成闭合；上游 owner 已进一步收敛为 current-season activity/reward join 与 vendor-stock/item relation。
- 用户随后批准在隔离证据目录下载固定提交 `wowdev/WoWDBDefs@b207ddd46e9e5350d262c2bd8e3d6181c5561aba` 的最小定义和许可证。该提交只作为字段布局辅助，不能建立官方当前赛季 PVE 成员权威；所有 `?` 字段继续显式标记为 `unverified_*`，没有执行第三方代码，也没有同步生产或切正式指针。
- 固定 schema 辅助与三张补充官方 join DB2 已让 10/10 张表的全部未加密记录完成可复验解析。字节序修正后的 partial re-extract 又恢复 114 条加密记录，`CollectableSourceVendor → CollectableSourceInfo → ItemModifiedAppearance` 现可回连 19,309 个官方可装备 item 候选，其中要求等级 90 的候选仍为 374；`QuestPackageItem` 仍为 11,058 个候选。恢复记录新增 6 条 source info、17 条 vendor、17 条 vendor sparse 和 74 条 appearance；其中 39 个 item 命中官方 all-equippable 索引，但全部是 level 1、无 sourceKey 的外观/幻化类物品，source info 实际只回连两件参与活动战袍，vendor sparse 的 9 个 item 无一命中官方可装备索引，因此 `promotableCurrentPveMemberCount=0`。
- WDC5 section 审计证明成员关系链共有 178 条加密表记录；当前已真实解析 114 条，仍有 64 条不可用，不能假定与本赛季无关。`current-client-source-relations-audit.json` 因而保持 `blocked`、`promotableMemberCount=0`、`resolvedGapCount=0`，并保留 `CURRENT_CLIENT_ENCRYPTED_SOURCE_RECORDS_UNAVAILABLE`、`CURRENT_QUEST_PACKAGE_RELATION_UNAVAILABLE`、`CURRENT_SEASON_PVE_VENDOR_IDENTITY_UNAVAILABLE` 和 `THIRD_PARTY_SCHEMA_FIELDS_UNVERIFIED` 四个根因。官方快照 exact-head 重建仍是 21 条缺口，恢复记录和关系候选均未写入 Catalog。
- 当前客户端的官方静态 `TactKey` / `TactKeyLookup` 也已在同一隔离边界内抓取、解析并交叉验证：24 条静态 key、204 条 lookup 可组成 24 个 join，但成员关系链 178 条加密记录所需的 12 个 key 中命中 `0/12`，覆盖记录 `0/178`。`current-client-tact-key-coverage.json` 只持久化 key ID 覆盖计数，不输出任何 key material，并以 `CURRENT_CLIENT_STATIC_TACT_KEYS_INCOMPLETE` 保持 `blocked`。该结论只说明静态客户端表未携带所需密钥；另行批准的 current public source 已恢复 114 条记录，但剩余 64 条仍必须纳入完整性阻断，不能用 partial 结果替代完整闭包。
- 固定 `c034041` 的首轮 v4 审计曾把 WDC5 `uint64` 文本和 BLTE 原始 8-byte identity 当成两个 namespace，直接字符串比较得到伪 `0/12` 重合。刨根后确认 12 组 identity 实际逐一对应：把 WDC5 ID 按字节反转，重合为 `12/12`；例如 `be7d592cd36508a2 → a20865d32c597dbe`。因此旧的“record/BLTE namespace mismatch”结论已撤回，它不是上游密钥缺失事实，而是提取器 keyfile writer 的字节序合同错误。
- 该追踪共暴露三条提取器契约问题：SimC JSON keyfile 大小写与 `keyfile.find` 不一致；WDC5 little-endian `uint64` 文本没有转换为 BLTE byte order；旧隔离环境缺少 `fixedint` 时会禁用 Salsa20、把加密 chunk 零填充并仍留下看似成功的 WDC5 文件。当前 Goal-only writer 同时统一小写并执行 byte-order mapping，抓取器强制验证 Salsa20，且单独发布 key/hit/decrypt/zero-fallback 计数；正式 SimC 运行时未修改。
- freshness 复核发现 `c034041` 不是仓库当前头后，用户授权 Goal 内必要操作无需逐项确认。当前已精确抓取 `wowdev/TACTKeys@a3449fd5cfc3a0053cbff2c65f7d16166774cbf9`：981,450 bytes、19,629 行、SHA-256 `e4fe2fd39ccc43b5ee14b1ced69dce9f21d4d90267a8a3e2bbb2b953597f55f9`。当前头覆盖 WDC5 `9/12` 个 key、`114/178` 条记录；byte-order mapping 后 SimC 执行前 lookup 为 `9/12`，v5 实际得到 `key hit=17/20`、`decrypted=17/20`、`zero fallback=3/20`，四表解析行数精确增加 114，剩余 3 个 key 对应 64 条记录继续不可用。current-source 状态是 literal `partial`，不是 complete。原始 `WoW.txt`、临时 keyfile、v5 工作集和早期 `c034041` 的 49,026,131-byte transient 工作集均已精确删除；Goal transient 剩余文件数为 0，只保留不含 key material 的哈希、计数、官方 DB2 与派生审计。清理后根盘 80%、`MemAvailable≈2.19 GiB`、生产后端 `active/NRestarts=0`，没有同步生产、修改正式 SimC 或切换指针。
- 上游来源追踪继续覆盖 Raidbots 公布的 exact-build DBCache：9 份 `verified
  retail/enUS` 缓存和当时保存的 unverified 第一页中 98 份 build `68887` opt-in
  retail 缓存均以单线程、内存内目标表扫描完成，抓取失败为 0，总读取
  298,323,339 bytes，原始缓存和完整 key 输出均未落盘。旧 scanner 会预载归档 static
  TactKey/TactKeyLookup，因此其 `6/12`、关联 `82/178` 是 composite effective-client
  view，不是 cache-body-only 口径；该旧快照也没有持久化 cache-only 分解。可安全保留的
  结论是这些选中观察没有补出三枚 blocker key，也没有向 current TACTKeys `9/12`
  增加 target。`git ls-remote` 复核仓库头仍是 `a3449fd`，故当前批准 source union
  仍为 `9/12`、`114/178`，缺失仍精确是 `14f4b11d7b067aa2`、
  `62bf37a70e6d54f6`、`fbbf041f980ce0dc` 及其 64 条记录。这把边界收敛为
  “已选公开/缓存观察均未提供”，但不能推断所有地区、账号资格、内容门禁或未穷尽
  unverified corpus 下都不存在；完整性仍保持 `blocked`。
- 用户已明确授权本 Goal 内所有必要项目操作直接推进，不再逐项询问；授权不放松 Harness 的资源门禁、隔离候选、生产/正式指针切换条件、手工验收关闭条件或 fail-closed 状态纪律。
- 24 个已抓取 Blizzard 权威页面也完成 item-link 反查：仅出现 9 个 item ID，其中 8 个是坐骑、PvP、外观或 cosmetic 奖励；唯一 PVE 装备关系 `249367 Chiming Void Curio` 已存在于 current-client Journal 成员证据。本轮没有发现新的 PVE 战斗装备成员，也没有关闭 21 条缺口。
- 新补录的 Revelations 上线页和 7 月 29 日发布的 7 月 28 日热修页把证据新鲜度推进到当前：热修明确 Val/Naigtal 世界 Boss 奖励必须匹配玩家所选专精。Ritual Sites、Lost Armaments、Val/Naigtal 世界 Boss、Voidforge、Prey 的官方页面仍只定义动态战利品专精/战团奖励池、档位或粗粒度 transform 条件，不枚举战斗装备成员；这能收紧 eligibility 事实，但不能解除 `OFFICIAL_SOURCE_MEMBERSHIP_API_UNAVAILABLE`。
- exact-head Universe 审计不再用空 discovery 把这些事实压扁成 19 条“缺来源”：它通过隔离快照适配器保留 19 条 blocked source、21 条具体 upstream gap 和 1 条未批准政策门禁，共 41 条 blocked ledger；未具备 progression 或成员全集的关系仍不被伪造成 canonical member。
- 官方 90 级可装备反向账本有 977 项，其中 256 项连接到部分 Journal/套装/制造证据，721 项仍缺来源或治理性排除；完整正整数 ID 空间的官方可装备索引现已闭包为 109786 项，其中 1431 项连接到部分来源证据，108355 项仍缺来源关系或治理性排除。两者都不是 Universe 分母。
- 已否决最初的 `itemId=230000..280000` 反向抓取边界：完整隔离抓取从 ID 1 开始，最终首件为 25、末件为 282426，共 440 页、407881902 个持久化响应字节。末四页真实经历未截断 `pageCount=4→3→2→1`，最后一页 36 项；逐响应 SHA/bytes、raw-file manifest、游标、排序、范围、可装备性、终止页和 exact-head 代码哈希均已复验。该索引仍明确标记 `sourceMembershipComplete=false`，不能冒充赛季来源成员全集。
- 官方制造专业投影得到 172 个非 PvP 装备候选；项目候选权威现已逐件纳入 172/172，allowlist 缺失、额外和 unsupported 均为 0。三种制造副属性合同分别为 106 件双副属性自定义、38 件单副属性放大和 28 件固定/配方定义属性；固定属性装备不伪造副属性选择器。
- Game Data 静态响应自报 build `67808`，SimC 客户端快照为 live hotfix build `68887`；当前证据门禁按 build mismatch 阻断，不把同日抓取包装成版本一致。
- 隔离候选 `ca71c49f` 已在微信开发者工具中按严格 runner 完成预览目录/动作矩阵：13 职业、40 专精、640 槽位、240 个动作检查、6619 次物品检查和 21349 次物品/进度关系检查，聚合状态为 `PREVIEW_CATALOG_ACTIONS_PASS`、`reasonCodes=[]`。三类强化和 head/main-hand/trinket1 应用路径均有交叉覆盖；26 个支持专精仍明确为 `simcFormalRequired=26`、`simcExecuted=0`，14 个不支持专精只证明了执行前策略阻断，因此该结果不能替代正式 Manifest 后的终局矩阵。
- 旧预览还漏验了一条实际用户主路径：制造副属性在 compact Catalog 中被折叠为 `craftedStatOptions`，但 Taro 只把它渲染成“仅展示”，Apply 又会清空目标槽强化，`craftedOptionId` 从未进入 Selection Intent；PG native 制造回填也没有写 canonical mod option，Resolver 因而可能静默采用底层默认 `crafted_stats`。当前修复把四种副属性 ID、单/双属性 option identity 和 label 收归 `crafted_stats_authority.py`，PG/SQLite 回填、Catalog、Resolver、Taro draft/commit 全链路共用；可自定义制造装备缺选择时以 `GEAR_CRAFT_OPTION_REQUIRED` 阻断，固定属性装备不显示伪选择器，payload identity 与 `crafted_stats` 冲突也保持 blocked。旧候选对两个已由 current-client membership 与 SimC 验证的制造探针 item 均未返回候选，进一步证明该问题不能由视图补丁绕开。
- 本地 CR 随后发现 membership 回填曾把武器/副手/饰品的槽位直接当作虚空晋升资格，并可能在 SimC 属性探针成功后把仍缺 progression authority 的制造变体升级为 `verified`。当前修复不再由槽位推断 `crafted_void_upgrade`；只有显式 `voidUpgradeEligibilityStatus=verified` 的上游成员才能发布该 track，且 `OFFICIAL_PROGRESSION_STATE_UNAVAILABLE` 会在 SimC 属性成功时继续把对应变体保持为 blocked。PG 默认 seed 与 SQLite 回填使用同一 fail-closed 边界。
- 严格重跑定位并修复了两条不能靠视图绕开的上游链路：火法社区 Exact 已占满后端全局美化额度时，前端仍优先打开未配置戒指，后端以 `GEAR_CRAFT_EMBELLISHMENT_LIMIT_EXCEEDED` 正确阻断；冰法头部插槽由 Exact 实装实例证明时，Exact 绑定只发布当前宝石，没有发布同槽位 canonical 替换宝石。候选现直接使用 ResolvedSnapshot 的 `embellishmentUsed` / `embellishmentMax` 控制新增与替换，并在 editor-managed Exact 能力上把后端已验证、适用同槽位的普通强化选项纳入 Resolver allow-list；火法 `embellishment→embellishment`、冰法 `socket→socket` 均在微信端 `fallbackUsed=false`、Resolve=`verified`。
- exact-head 审计继续发现旧预览矩阵只校验 item/variant identity 与状态，没有证明实际可见的名称、来源、装备类型、装等、静态属性、progression 文案或图片，也没有逐一选中每个可用变体；同时 compact payload 未发布装备类型 badge，Taro 在变体物化时还会丢失既有 badge/type 字段。当前候选代码已把装备类型归还后端公共展示合同、保留变体物化后的后端事实，并将 runner 加强为逐候选 row/media/detail 与逐 ready/partial 变体点击核对；这些修改尚未绑定最终不可变候选和新一轮 DevTools 全矩阵，不能复用旧的 `PREVIEW_CATALOG_ACTIONS_PASS` 作为证明。
- 新 runner 还会逐一核对并实际点击每个可见制造属性 option，验证草稿、已提交选择和 Resolver 回显三方 `craftedOptionId` 一致；40 个专精各完成一次制造属性 Apply→Resolve，终局汇总至少覆盖 8 个槽位、20 件制造装备和全部 10 种 canonical 单/双副属性 option identity。该门禁尚未在最终不可变候选执行，不能由 Node 单测替代。
- 对旧候选进行了单请求串行的 40 专精 × 16 槽位只读诊断：640/640 endpoint 共 6619 件候选、21349 个变体；只在诊断内跳过旧 payload 已知缺少的 `equipment_type` badge 后，名称、来源、图片 URL、装等、静态属性、progression label/kind/status 没有第二类合同缺口。该诊断结束时根盘仍为 80%、`MemAvailable≈2.18 GiB`、生产/候选 `NRestarts=0`；它用于限定根因，不证明新后端 badge、Taro 实际显示、图片实际加载或逐变体点击。
- 云服务器根盘曾达到 92%，违反目标架构 `<= 80%` 的候选硬门槛。日志输出上游修复、受控轮转/压缩、journal vacuum 和精确保留清理后已复核为 79%；历史 PostgreSQL/SQLite 备份保留。新候选仍须在每次启动前重新通过同一门槛。
- Goal 期间 `wow-gear-release-refresh.timer` 曾自动启动约 1.7 GiB RSS 的刷新任务，将 `MemAvailable` 压到约 483 MiB；已精确停止该 service/timer，生产与候选 backend 均保持 `NRestarts=0`。资源重任务结束前它与 `wow-community-template-sync.timer` 保持停用，收口前必须按记录恢复并复核。
- 官方全索引在独立 systemd cgroup 中串行完成，CPU 31.972 秒、内存峰值 92.5 MiB、swap 0；后续 join DB2、静态 TACT key DB2 抓取和关系解析同样使用单 worker、`CPUQuota=40%`、`MemoryHigh=256M`、`MemoryMax=384M` 的隔离 transient unit。v5 byte-order 修正提取耗时 42.432 秒、CPU 14.009 秒，随后四表解析耗时 47.317 秒、CPU 18.936 秒，二者 swap 均为 0。临时 CSV 曾使 shell 根盘口径短暂显示 81%，触发停止线后立即复制隔离证据并删除唯一 transient 工作集；复核恢复为 80%、`MemAvailable≈2.20 GiB`，生产 backend `active/NRestarts=0`，没有同步生产、修改正式 SimC 或切换正式指针。
- 当前候选链的自动化回归可作为诊断和修复证据，但真实微信验收必须重新绑定最终同一不可变候选。

## 2. 用户可见完成标准

1. 玩家选择任意一个 40 专精，合法槽位都能看到本赛季实际可获得且适配该专精的完整 PVE 候选。
2. 每件候选的名称、图标、来源、难度、装备类型、进度状态、装等、静态属性和可强化能力都来自匹配的后端 Catalog / Exact / Enhancement 证据。
3. 普通 Browse 只显示 governed maximum-rank progression；制造品质和虚空晋升保持独立 canonical progression；低 rank 玩家实装只能保留在 Exact。
4. 社区或个人 Exact 导入保留真实 bonus、宝石、附魔、制造副属性和美化，不会为了进入 Browse 而改写身份；缺证据时明确阻断。
5. Apply 后必须经过 canonical Resolve；ready ResolvedLoadout 才能编译和提交 SimC。26 个支持专精产生真实终态结果，14 个不支持专精在执行前按策略阻断。
6. 微信 DevTools / Computer Use 中的真实操作覆盖完整交叉矩阵，不以法师或一两个样本外推全量结论。

## 3. 当前赛季 PVE 宇宙合同

建立不可变 `SeasonPveUniverseRevision`，其 identity 至少绑定：

- `seasonRevision` 与 source-policy revision；
- 每个 `sourceType + instanceId`；
- 每个 `instanceId + encounterId + difficultyKey`；
- 每个来源关系下的 `itemId`；
- authority、抓取时间、原始 evidence reference、fetch/cap/fallback 状态；
- universe 内容 hash 与生成器 revision。

每个 universe member 必须且只能落入以下一个终态：

- `included`：可追到 staging item/source/variant、Catalog ItemDefinition/BrowseVariant、专精 eligibility 与 Resolve；
- `excluded`：逐项记录稳定 `reasonCode`、事实 owner、evidenceRef、时间和治理决定；
- `blocked`：上游证据缺失或冲突，明确阻断候选和发布。

聚合计数、HTTP 200、40/40 spec 数量、zero-unmapped 或“至少一个候选”都不能代替这个一对一 partition。

## 4. 执行切片

### Slice A — 收敛当前 Catalog correction

- 修正 current-HEAD 与 requirement/evidence/微信包身份漂移。
- 让 public verified-detail 与 replacement visibility 同时校验真实 Catalog Browse provenance。
- 用真实代码回归覆盖 exact-only import → Exact authority → Resolve → ResolvedLoadout → canonical SimC compiler，且不创建 Browse membership。
- 运行本地相邻回归和 CR；服务器资源门槛已恢复，但 dormant/read-only 证据仍不能代替当前不可变候选和 Universe 闭包。

### Slice B — Universe authority 与只读差集

- 从官方当前赛季 PVE 来源策略建立 universe revision。
- 把摄取 caps、分页、fetch failure、fallback 和未映射关系变成 machine-readable omission ledger。
- 输出 universe → Journal → staging → Gear Release → Catalog 的逐项差集；本切片不因发现缺口而静默过滤。
- 官方当前赛季来源、窗口、成员证据及 Goal 必需的固定第三方审计输入已获准写入本 Goal 隔离目录；必要操作无需逐项确认，但必须保持来源固定、证据脱敏、隔离落盘、及时清理原始密钥材料，并遵守 Harness 的候选、资源与发布边界。

### Slice C — 上游修复与 dormant Catalog

- 按实际 owner 修复 source discovery、ingestion、staging、静态事实、类型、progression 或 authority mapping。
- 每个修复先有失败回归，再做最小实现；不得在 Taro 中推断或补写装备事实。
- universe 差集归零或每条获得治理性 exclusion 后，才构建 dormant Catalog / Exact / Manifest dependency vector。

### Slice D — 资源受控不可变候选

- [x] 候选前根盘恢复为 79%，保留 active + rollback、当前/上一版 SimC 和数据库备份；每个新 candidate/temp workset 仍须重新预测并满足 `<= 80%` 与显式 reserve。
- 启动时 `MemAvailable >= 2 GiB`，运行中不得低于 512 MiB。
- 同时只运行一个资源密集型候选操作；生产 backend 保持在线；sync/backfill/collector 和非必要 SimC job 关闭。
- 候选使用 `MemoryHigh=1G`、`MemoryMax=1280M` 的声明预算；持续超过 1 GiB 或瞬时超过 1152 MiB 时停止并保留诊断。
- 始终使用 `WOW_DEPLOY_START_ASYNC_SYNCS=0`；记录 commit/tree/file parity、active pointer 前后、PG rollback、timer/backflow 与 cgroup current/peak。
- 历史数据库在没有 checksum backup + 独立 restore/read-back 之前只保留，不执行 drop、truncate、vacuum full 或文件删除。

### Slice E — 自动化全矩阵

自动化证据必须覆盖并持久化每一行结果：

- 40 专精 × 合法槽位 × universe item × progression eligibility；
- 每个 expected relation 的 visible / rule-excluded / governance-excluded / blocked 终态；
- Catalog / Exact / Enhancement / ResolvedLoadout revision parity；
- 普通、制造、虚空、套装、饰品、武器/副手、双戒/双饰品和合法空副手边界；
- 跨职业 armor/weapon proficiency、主属性、unique-equipped、插槽、附魔、美化和制造副属性；
- 26 支持专精真实 SimC 终态与 14 不支持专精前置阻断；
- 任一错误沿 `UI → public payload → PG read model → Catalog/Exact → staging → source universe` 追到 owner 和根因。

### Slice F — 真实微信全矩阵

- 构建产物的 source hash、Git commit/tree、后端 API base 和 Manifest dependency vector 必须绑定同一不可变候选。
- 使用现有微信 DevTools 进程、`miniprogram-automator` 和必要的 Computer Use；不自动安装 DevTools，不把截图或接口 smoke 冒充人工验收。
- 全部 40 专精逐一进入装备模拟，遍历每个合法槽位和返回候选；对每个 expected item/progression relation 实际打开详情并核对显示/可选状态。
- 每个专精至少完成一次跨槽换装、Apply、Resolve、保存、重载和异常恢复；Exact/强化使用跨职业、跨护甲、跨武器类型的完整类别矩阵。
- 13 份职业报告必须全部为非诊断 `PASS`，再由唯一终局汇总门核对 13 职业、40 专精、640 槽位、280 个动作（每专精 7 项，含一次制造属性选择→Resolve、26 个真实 SimC 任务完成与 14 个后端策略阻断）以及全部候选物品/进度/制造属性关系；缺任一职业、槽位、动作、运行时身份或交叉类别都必须 fail closed。
- 制造属性不允许只抽样：每个 ready option 都要在 DevTools 中实际选中并核对选中态；40 个专精的 Apply 证据需至少覆盖 8 个槽位、20 件 item 和 canonical 10 种 option identity，且 committed/Resolver echo 必须与草稿完全相等。
- 26/14 SimC 路径逐项验证任务提交或前置阻断、任务列表、详情终态、重试/返回路径。
- 自动化可执行的 DevTools 操作全量执行；Computer Use 负责真实点击、输入、回退、滚动、选中态和异常状态复核。任何 route crash、空列表、旧包、请求失败或状态不一致都回到上游根因。
- 结果 ledger 至少记录 class/spec/slot/item/progression/action/assertion/status/runtime identity；少量样本不能获得全量通过结论。

## 5. 停止线

- universe 未形成一对一 inclusion/exclusion/blocked 闭包；
- 任何来源、难度、物品因 cap/fetch/fallback 静默丢失；
- Catalog/Exact/Manifest/微信包 revision 不一致；
- 云盘、内存、cgroup 或生产健康超过预算；
- 真实微信未覆盖完整 40 专精交叉矩阵；
- 只得到 API/test/build 通过，没有同一候选的 DevTools 实际操作证据；
- `partial`、`blocked`、`stale` 被改写成成功；
- 需要超出本 Goal、破坏性扩大数据范围、绕过 Harness 关闭门禁或无法证明回滚的操作。

## 6. Harness 关闭

每个改变运行态的切片必须经过当前 requirement、targeted tests、local CR、唯一 task packet、不可变候选、回滚证据和 CI。最终 Goal 只有在：

1. universe completeness closure 通过；
2. 自动化全矩阵通过；
3. 同一最终候选的真实微信全矩阵通过；
4. 用户给出明确的 post-test acceptance；
5. merge、production、local/origin/cloud parity 与清理完成；

之后才能标记完成。

## 7. 2026-07-31 截止收口

本 Goal 按用户要求在 17:30 前停止扩展并完成迁移收口。结论必须保持
`blocked`，不能标记为完成或允许生产 promotion：

- 官方 build `12.0.7.68887` 的来源关系链共有 178 条加密记录，已真实恢复
  114 条，仍有 64 条不可用。当前公开 TACTKeys、9 份 verified DBCache
  和 98 份 opt-in exact-build DBCache 的并集仍缺
  `14f4b11d7b067aa2`（12 条）、`62bf37a70e6d54f6`（8 条）和
  `fbbf041f980ce0dc`（44 条），因此
  `APPROVED_PUBLIC_TACT_KEYS_INCOMPLETE` 与
  `CURRENT_CLIENT_ENCRYPTED_SOURCE_RECORDS_UNAVAILABLE` 未解除。
- 官方来源投影仍为 19 类中的 `complete=0`、`partial=9`、`blocked=10`，
  21 条 progression、source membership 和 transform eligibility 缺口没有
  得到治理性 closure；候选 Universe、Catalog 和 production pointer 均未把这些
  缺口伪装为成功。
- 隔离 Gear Release
  `gear-release:sha256:2b197bf7609411575a5e433b20386325c533bf473c67ba47fc5e3f4479e5d2ad`
  已校验为 1564 items、33599 sources、52713 variants、73 mod options。
  但新的社区模板构建仅有 7/80 能满足同 item、已核验 progression authority，
  所以未发布 Community Release，也未组成可 promotion 的正式 Manifest。
- 最新微信包绑定源码头 `1b33356c3e97653bc91f3747ecd046784650d0a7`、
  source hash
  `sha256:e9e8556a3a630f38125e8ff586ef593136f5e028046ddc38c49335f742a044e1`
  和上述 gear-only preview。官方微信开发者工具实际完成死亡骑士 3 专精、
  48 槽、432 个候选、1269 个 item/progression relation 的可见事实检查，并
  实际选择 1173 个 ready/partial 变体，结果为 `CATALOG_ONLY_PASS`。动作、
  Exact、保存、Resolve 和 SimC 明确未在该只读阶段执行；其余 12 职业、
  37 专精和完整 13×40×16 终局矩阵未完成，因此不能外推为 Goal 通过。
- 本轮按真实微信失败追到并修正三条事实/证据合同：`speed` 后端权威标签统一为
  “速度”；上游 progression conflict 的 blocked 变体不再被要求或伪造装等；
  UI 不再在用户点击前把后端默认 variant 标记成已选择，避免 stale stats
  被 runner 误认成目标变体。相邻回归为 Vitest 44/44、Node 53/53。
- 云端候选 service、484 MB 隔离数据库、116 MB 候选目录和专用凭据均已回收；
  根盘由 80% 回到 79%，`MemAvailable=2551 MiB`，生产 backend
  `active/NRestarts=0`。两个原有 timer 已恢复 active；Persistent timer
  触发的 community backflow 被立即停止并 reset 为 inactive，下一次自然运行
  为次日窗口。生产 generation 仍为 35，Manifest/Gear/Community/Catalog/Exact
  五个正式指针与 Goal 前完全相同。

迁移入口为任务分支 `codex/equipment-simulator-e2e-matrix` 及
`artifacts/releases/2026-07-30-equipment-simulator-e2e-matrix/handoff.json`。
隔离原始官方快照仍保留在本机证据目录且没有提交 Git。为支持跨电脑接力，
1,498 个证据文件已归档为 63,202,189 字节的 zstd 文件，存放在云服务器隔离目录
`/var/lib/wow-evidence-handoff/equipment-simulator-e2e/d6426b07/`；归档
SHA-256 为
`d5b2a6bfbb955f9be7a13f4637e278745684225f48bb477b76105ff2ba963ea5`，
并已通过远端 SHA、zstd、tar 目录和文件数校验。该目录不属于
`/opt/wow-mini-program`，保持压缩、按需在非生产工作区解包，不供生产服务、
数据库、定时任务或正式指针消费；可迁移的结论、哈希、阻断项和微信实测报告
继续以任务分支中的 handoff 为入口。

## 8. 2026-07-31 接力恢复

**状态：** `正在推进`

新 Goal `019fb823-90bf-7f63-ae60-9aaa82662f9c` 接续旧 Goal
`019faddb-abb5-79a3-a477-3cb6e6368120`；旧 Goal 的最终状态仍是
`blocked`，没有改标为完成。接力 checkpoint 的 local HEAD、origin task
branch 和 `git ls-remote` 均为
`9183bad2322a429da47912b12a1d0bd693e3f5ba`。

- 云端归档再次通过 archive SHA、handoff SHA、`zstd -t` 和逐文件校验：
  1,498 个文件全部匹配，另有 88 个目录条目；handoff 仍为 `blocked`，
  `productionPromotionAllowed=false`、`cloudProductionConsumed=false`。
- 最新生产仍是 generation 35、Manifest
  `season-manifest:sha256:20453991e93a1dc1650dbacfd85bdd042e9b020737c7851bef943f1e3e68883a`，
  `/api/data/health` 如实为 `partial`，正式 Gear、Community、Catalog 和 Exact
  指针没有被本接力 Goal 修改。`wow-gear-release-refresh.service` 在自然 timer
  触发后运行 20 分钟并超时为 `failed`；backend 仍为 `active/NRestarts=0`，
  未自动重跑或 reset 该失败。
- 从已校验归档恢复原始 DBCache 语义解析器及测试后，重新绑定当前
  Raidbots source-list 并串行内存扫描；unverified 滚动列表曾瞬时显示 100 个
  exact-build 条目，实际扫描快照为 verified 9/9、unverified 99/99，抓取失败 0，
  总读取 296,829,090 bytes。这里的计数是归档 static TactKey/TactKeyLookup 与
  hotfix cache overlay 的 composite view：两套语料仍只有 `6/12` joined-material
  target keys、对应 `82/178` 条关系，
  三枚 blocker key 均未出现；重建的 aggregate 仍为 source union `9/12`、
  `114/178`、缺 `3/12` 和 `64/178`。
- 滚动 unverified endpoint 随后又产生两批独立快照：97/97 与 96/96，抓取失败
  均为 0；与交接 98、接力 99 和 verified 9 一起累计 399 次缓存观察、329 个
  唯一内容 SHA-256、1,098,143,766 bytes。新增两批的 composite view 仍各自只有
  `6/12` joined-material targets、对应 `82/178` 条关系，
  没有向 current public TACTKeys 之外增加 key。为防止无界轮询，本轮在两批增量后
  停止重采样；原始缓存仍未落盘，只记录 redacted audit、source-list 与内容哈希。
- 纠偏：上述 Raidbots 结果只证明多个选中快照，不证明公开 corpus 穷尽。每个保存
  的 list 都固定返回 100 个 descriptor 并携带非空 `cursor`；当前 endpoint 对已尝试
  的 `cursor`/`start_cursor`/`pageToken`/limit 参数均返回同一第一页，仓库扫描器也不
  遍历 cursor。因此旧文中的“全部 98”或“完整 corpus”不得继续作为穷尽证据；
  后续实测到 cursor path traversal 并闭合 verified 终止页，但本段样本仍不能外推为
  unverified 穷尽。只能报告 329 个唯一 cache 内容样本均未补出 blocker key。
- 归档中的旧 aggregate 曾引用随后被同名刷新覆盖的 corpus SHA。Harness
  verifier 现在必须接收 snapshot root，并逐一复算 public、verified corpus 和
  unverified corpus 三个 component 的路径、字节数与 SHA-256；缺文件、越界路径、
  同名覆盖或 SHA 漂移都会 fail closed。
- 本机已安装的 Blizzard 正式 `zhCN` DBCache 精确为 build 68887，覆盖
  cache-body-only `2/12` joined-material targets（关联 `47/178` 条关系）；与归档
  official static 表叠加后的 composite client view 为 `8/12`（关联 `92/178`），
  但两种口径均不含三枚 blocker key，且 composite view 仍是 current public TACTKeys
  的严格子集。用户随后完成认证、进入角色世界并正常退出；post-exit observation
  发现 cache 从 1,360,908
  bytes / SHA-256 `1b263313…67fca` 更新为 1,376,502 bytes / SHA-256
  `d5aa61dc…b723`，但 redacted 复扫的两种口径未增加 blocker key，三枚仍为 0。
  第三方 metadata 只能把三枚 key 的首次观察收窄到
  12.0.7 XPTR/12.0.0 Beta 的未知 quest/transmog/item-set 上下文，不能据此解密、
  排除或证明当前赛季成员关系。
- 本机 6,395 个候选文件的 header 枚举只找到 8 个 XFTH：当前 68887 cache 与
  7 个 build 66192-67823 的旧 `.tmp`；旧 cache 均不含 blocker identity，且 build
  不匹配。Wago exact-build `TactKeyLookup` 可把三枚 identity 分别绑定到 record
  8193、8225、8087，但 exact-build `TactKey` 无对应记录；Blizzard build config
  与 Raidbots verified enUS cache 也没有可用 state-1/state-2 记录。另一次未封存
  source response 的 bounded Wago research observation 枚举了 96 个
  major-version-12 retail/PTR/XPTR/Beta build，观察到三枚 lookup identity、未观察到
  对应 `TactKey` material row；该 96-build 计数和 absence 只能作为 research lead，
  不能升级为可复验 authority。因此当前分类
  仍是 `identity_confirmed_exact_build`、`key_material_missing`、
  `decryption_unverified`，64 条记录继续 fail closed。
- Raidbots cursor path 的只读实测 request shape 为
  `GET /api/dbcache/{verified|unverified}/{percent-encoded opaque cursor}`。verified
  链在 55 页、5,428 个不重复 descriptor 后以显式 `cursor=null` 终止；持久化 ledger
  包含逐页响应哈希和 5,428 个 redacted descriptor URL 哈希，可独立复核计数与去重。
  unverified 只完成两页 200 项无重叠探测，因 30 天滚动写入且没有已发布的
  snapshot-isolation
  合同，整体 corpus 穷尽仍不得宣称；保留
  `UNVERIFIED_DBCACHE_PAGINATION_EXHAUSTION_UNPROVEN` 与
  `UNVERIFIED_DBCACHE_SNAPSHOT_ISOLATION_UNDOCUMENTED`。该 request shape 是实测行为，
  不是 provider-published API contract。
- exact-build 68887 的 verified 第一页还包含 4 个 `version=xptr` cache；已在内存中
  全部扫描，共 15,431,411 bytes、抓取失败 0。cache-body-only 只有 `2/12`
  joined-material targets（关联 `47/178`），叠加归档 static 表的 composite view 为
  `6/12`（关联 `82/178`），两种口径均无三枚 blocker key。累计样本更新为 403 次
  观察、333 个唯一内容 SHA-256、1,113,575,177 bytes；四个 XPTR cache body 未持久化，
  redacted audit 未输出 key material；含 key material 的已校验 static 输入仍只保留在
  Git 外的隔离 handoff 解包目录。
- 用户授权范围仍固定为原始 63 个历史 descriptor：XPTR build 67227 两个，
  以及 12.0.0 Beta 七个 build 共 61 个，metadata 合计 61,090,619 bytes。
  从原始 main rollout 只恢复出 52 个完整 descriptor：XPTR 67227=2；Beta
  64339=12、64529=7、64611=6、64741=12、64774=13。对应 52 个 body 已下载并
  扫描，共 58,259,882 bytes，全部为唯一 XFTH v9 且 header build 匹配，三枚
  target identity 命中 0；`.part`、request URL 泄露和 actual key/material 泄露均为
  0，Git 外隔离证据 ACL 保持 restricted。原授权集合仍缺 11 个 descriptor：Beta
  64124=3、64228=1、64339=7，因此 blocker 精确更新为
  `AUTHORIZED_HISTORICAL_CACHE_SET_INCOMPLETE_11_DESCRIPTORS_UNRECOVERED`。
  另一次 fresh verified metadata 得到的是独立 52 项集合（XPTR 67227=2；Beta
  64124=3、64228=1、64339=19、64529=7、64611=6、64741=9、64774=5），其 URL
  set hash 为 `0a00f1…f5df65`、object set hash 为 `c6df57…4a3a19`；它与原授权
  descriptor 是否同一 identity 未获证明，body 未下载，也不继承 fixed-63 授权。
- 官方客户端的人机刷新动作已经闭合：退出后 WoW 进程为 0，新 cache 仍为 XFTH v9 /
  build 68887，并由 `local-official-client-post-login-cache-audit.json` 绑定；
  原先已跟踪的 `LOCAL_OFFICIAL_CLIENT_LOGIN_CONTEXT_REQUIRED` 已移除。该动作没有复制
  原始 cache、没有输出 key material，也没有触碰生产或 release pointer。
- 如果后续获得 key，最小安全重放路径是固定四个已知 BLTE range 与 build/config/
  root identity，而不是重新绑定已经推进的 live retail。执行前仍需补齐 expected-build/
  config 门禁、输出 root-MD5、完整解密非零退出、禁止覆盖及下游 `12/12` 成功路径；
  即使 64 条记录恢复，也仍需单独闭合 21 个 Universe 缺口。
- `BroadcastText` 语义已按固定上游源码纠偏：有效 HTFX v9 条目尾部 28 bytes
  是 4-byte `TactKey` table hash、8-byte identity 和 16-byte actual material，
  不是 reference；审计只保留计数和源码 pin，不持久化 material。纠正后的本机 cache
  扫描解析 12,212 条、未识别 table 11,500 条、未建模 state 0 条；cache-only
  joined 2、Broadcast effective records 19、carried unique material identities 1、
  available identities 3，composite joined 123、available identities 124，两种口径的
  blocker present 都是 0。相关旧 artifact 已把 `broadcastReference*` 纠正为
  `broadcastCarriedMaterial*`；四个 XPTR raw body 未保留、未按新 scanner 重放，
  但其 target Broadcast count 原本就是 0，因此 target coverage 不变。
- 当前 public `wowdev/TACTKeys` 仍固定在
  `a3449fd5cfc3a0053cbff2c65f7d16166774cbf9`；`WoW.txt` 981,450 bytes、
  SHA-256 `e4fe2fd39ccc43b5ee14b1ced69dce9f21d4d90267a8a3e2bbb2b953597f55f9`，
  三枚 blocker identity 命中 0，所以 `9/12` keys、`114/178` records 未变。
  本机已安装 exact-build CASC 的四个目标 raw BLTE 都能在 local idx 唯一定位，
  计划读取 3,516,950 bytes；正文尚未抽取，当前没有安全现成 local extractor，
  `Data/config` 只观察到 1 个 key identity 且 target match 为 0。这只证明 offline
  transport replay readiness，不缩小 3 keys / 64 records。另有 2 XPTR + 61 Beta
  共 63 个历史第三方 descriptor 的固定范围已得到用户明确下载授权；其中从原始 main
  rollout 恢复的 52 个 body 已扫描且 target 命中为 0，但 11 个授权 descriptor 仍未
  恢复。独立 fresh 52 项 metadata 不能补齐该缺口或继承授权。因此 3 keys / 64 records /
  21 个 Universe 缺口均未改变，handoff 历史入口继续 `blocked`，production 与 release
  pointer 也未改变。
- 新的 fail-closed 证据入口是
  [current-client-tact-key-scanner-and-local-replay-audit.json](../../artifacts/releases/2026-07-30-equipment-simulator-e2e-matrix/universe/official-snapshot/official-client-db2-v1/current-client-tact-key-scanner-and-local-replay-audit.json)。
  授权历史子集的脱敏扫描链由
  [historical-authorized-cache-subset-scan-audit.json](../../artifacts/releases/2026-07-30-equipment-simulator-e2e-matrix/universe/official-snapshot/official-client-db2-v1/historical-authorized-cache-subset-scan-audit.json)
  绑定；仓库 artifact 不含 request URL、raw key/material 或绝对本机路径。
  旧 [handoff](../../artifacts/releases/2026-07-30-equipment-simulator-e2e-matrix/handoff.json)
  仍是 `blocked` 历史入口；其中 `branch-head` 文字不能代替实时 SHA 校验。本轮未提交
  证据 diff 的历史 checkpoint 于 `2026-07-31T16:15:36.3282380Z` 核对：local HEAD、
  `origin/codex/equipment-simulator-e2e-matrix` tracking ref 与实时 `git ls-remote` 均为
  `2afcaf2382e556c5c4914f81bc34a471eb856400`；它不是提交后的 current HEAD，提交并推送后
  仍须重新实时校验三者一致。Goal 与生产状态
  均未改变，没有合入 `main`、生产 mutation 或 release pointer mutation。

当前首要 blocker 仍是取得三枚缺失 TACT key 的获批 exact-build 来源，或取得
64 条记录的权威解密结果。未解除该 blocker 前，不进入 19 类来源的完成性宣称、
候选 promotion 或终局微信/SimC 矩阵。
