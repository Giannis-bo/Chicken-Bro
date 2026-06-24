# Season Gear Instance Slice Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current brittle raid-season selection with a verified current-season pool, then fill the self-owned gear catalog one dungeon or raid instance at a time with clear per-instance acceptance.

**Architecture:** Treat the current season pool as a small verified control plane first, then let Battle.net Journal, SimC, Raider.IO observed variants, and health checks attach evidence to that pool. Do not run another big-bang catalog rebuild as the primary strategy. Each instance should move from blocked/partial to verified independently, and health should expose which instance is still incomplete.

**Tech Stack:** Python backend in `server/websim_payload.py` and `server/news_backend.py`, SQLite cache tables, Battle.net Game Data API, SimC-derived variant metadata, Raider.IO observed variant backfill, Node frontend tests for `pages/builds/detail.js`.

## Confirmed Current Season Pool

The current-season allowlist must include these instances.

Mythic+ dungeons:

- `Magisters' Terrace`
- `Maisara Caverns`
- `Nexus-Point Xenas`
- `Windrunner Spire`
- `Algeth'ar Academy`
- `Pit of Saron`
- `Seat of the Triumvirate`
- `Skyreach`

Current raids:

- `The Voidspire`
- `The Dreamrift`
- `March on Quel'Danas`
- `Sporefall`

Explicitly exclude wrong-season raids such as `Manaforge Omega` from current-season raid coverage.

## Principles

- Fix the season pool gate before backfilling gear details.
- Do not treat "last raid in journal expansion" as current season.
- Do not hand-maintain a BiS truth database. The self-owned database stores normalized evidence, source state, and blockers.
- Filling one instance means: instance ref verified, bosses/encounters present, loot items present, item metadata verified, slot/armor/weapon compatibility clean, source labels correct, and missing SimC variant fields remain `partial` instead of being promoted.
- After each instance slice, run both instance-level coverage checks and all-spec smoke. Do not only verify mage/frost.

## Upgrade Track Rules

Current-season gear stats must not infer upgrade tracks from whatever item-level buckets happen to exist in the cache. The accepted normal track caps are:

- `Champion 6/6`: item level `263`
- `Hero 6/6`: item level `276`
- `Myth 6/6`: item level `289`

Item level `298` is a separate exceptional ceiling, not normal Myth max. Only model it when the item is eligible through a documented special path, such as Ascendant Voidcore weapon/trinket upgrades or Sporefall Sporefused raid drops. For non-Sporefall dungeon armor, jewelry, and other ordinary drops, do not expose 298 as the default top track even if SimC can mechanically calculate `itemId + ilevel=298`.

For manual review tables, `itemId + ilevel` SimC-calculated stats may be shown as derived candidates, but they are not the same as `verified` season variants. A catalog entry still needs deterministic SimC variant evidence (`item_id + item_level + bonus_id/gem/enchant` where applicable) before it can move from `partial` to `verified`.

## Validated Attribute Slice Pattern

Windrunner Spire was used as the first manual attribute-review slice on 2026-06-23, before writing calculated stats back into the catalog.

Accepted pattern for the next instances:

1. Read the instance loot from the current production/local cache in read-only mode.
2. Confirm item count, encounter names, armor/weapon type, inventory type, socket metadata, current `verified` / `partial` state, and existing variant item levels.
3. Calculate stats with the deployed SimulationCraft binary, using `itemId + ilevel` only:
   - normal columns: `263`, `276`, `289`
   - special column: `298` only for documented exceptional eligibility, currently weapons/trinkets via Ascendant Voidcore or Sporefall Sporefused drops
4. Use probe classes that can equip the item type, and map catalog slots to SimC slots explicitly:
   - cloth -> mage/frost
   - leather -> druid/balance
   - mail -> shaman/elemental
   - plate -> warrior/arms
   - bows/guns/crossbows -> hunter/beast_mastery
   - caster one-hand mace/dagger/staff probes may need shaman/druid rather than warrior
   - `shoulder` must become SimC `shoulders`; `wrist` must become SimC `wrists`
5. Treat the output as a derived manual-review table until deterministic variant evidence exists. Do not promote `partial` to `verified` just because `itemId + ilevel` stats match.
6. After user/manual validation, record the instance result in this plan and only then decide whether to write catalog rows.

## Reused Legacy Dungeon Current-Season Loot Validation

For reused legacy dungeons, raw Battle.net Journal rows are not accepted season loot by themselves. Use this three-layer check before generating or writing an accepted per-instance table:

1. `raw_journal` upper bound: all cached Battle.net Journal loot rows for the instance. This may include old expansion loot, timewalking-style duplicate buckets, global dungeon buckets, and same-name alternate item ids. Treat this only as `journal_candidate`.
2. `observed_confirmed` lower bound: production/local observed variants with verified executable evidence. This confirms the item can exist in current play, but it is not a complete loot table.
3. `source_reference` middle set: a current-season loot reference table or item-level cross-source evidence. Record the source name, URL, source update date if available, checked date, item ids, boss/source, and any discrepancy note. This set becomes the manual-review candidate list.

Rules:

- `season_revision`, raw Journal membership, and Battle.net `preview_item.bonus_list` are not enough to include a reused legacy-dungeon item in the accepted current-season subset.
- Raw-only rows that are not in the current-season reference set stay `journal_candidate` or `excluded_legacy_bucket`; they are not used for accepted SimC tables or coverage math.
- Local observed rows that are not in the reference set are kept as `observed_confirmed` evidence and must be investigated before promotion.
- If a guide table and an item page disagree, keep the item only when the item page/source explicitly confirms the same current-season dungeon and boss; mark it as `source_discrepancy`.
- Only the `source_reference` set proceeds to the 263/276/289 SimC table, plus 298 only under the special-lane rules.
- Even after source-reference acceptance and SimC stat calculation, the catalog variant remains `partial` unless deterministic SimC variant evidence exists.

2026-06-23 application:

- `Pit of Saron / 萨隆矿坑`: raw Journal `74`; first local filter `49` remains only the `journal_candidate` upper bound; observed lower bound `13`; current-season source-reference target `24`.
- `Seat of the Triumvirate / 执政团之座`: raw Journal `44`; first local filter `44` remains only the `journal_candidate` upper bound; observed lower bound `6`; current-season source-reference target `35` (`34` from the current-season M+ rewards guide plus `258523 / 奈扎尔的虚空爪` confirmed by item page cross-reference).
- `Skyreach / 通天峰`: raw Journal `230`; local current-id filter `28` is now accepted as the source-reference target after current-season rewards guide and item-page cross-check; the remaining `202` rows stay `excluded_legacy_bucket`.

Windrunner Spire result snapshot:

- instance: `1299` / `风行者之塔`
- loot items: `26`
- normal track review columns: `Champion 263`, `Hero 276`, `Myth 289`
- special track review column: `298` for weapons/trinkets only
- socket metadata: only `251096 / 悲恸吊坠` has a prismatic socket in the reviewed table
- user validation: user spot-checked several item stat lines and confirmed they were correct
- caveat: `251094 / 无眠之心印记` had an existing observed `298` variant in production, but it is an off-hand item and should not be automatically treated as weapon/trinket 298 eligibility without separate evidence

Magisters' Terrace result snapshot:

- instance: `1300` / `魔导师平台`
- loot items: `26`
- source refs used: production `/opt/wow-mini-program/server/data/wow_news.sqlite3` read-only query, Battle.net journal loot metadata already cached, production SimC `/opt/wow-simc/current/simc`
- normal track review columns: `Champion 263`, `Hero 276`, `Myth 289`
- special track review column: `298` for weapons/trinkets only; `251105 / 破法者之盾`, `251115 / 分叉指环`, armor, cloaks, and other ordinary drops were not given a 298 lane
- current catalog state: dungeon source variants remain `partial` for all 26 loot items with top blocker `missing deterministic SimC variant preset`; observed_profile variants exist for `251111 / 裂纱钉刺` at 298 and `251115 / 分叉指环` at 289 but do not make the dungeon source verified
- socket metadata: only `251115 / 分叉指环` has a prismatic socket in the reviewed table
- user validation: user approved the table on 2026-06-23 and asked to continue other instances without further confirmation
- write status: no database write, no deploy, and no catalog promotion; results are still derived manual-review candidates

Maisara Caverns result snapshot:

- instance: `1315` / `迈萨拉洞窟`
- loot items: `20`
- source refs used: production `/opt/wow-mini-program/server/data/wow_news.sqlite3` read-only query, Battle.net journal loot metadata already cached, production SimC `/opt/wow-simc/current/simc`
- normal track review columns: `Champion 263`, `Hero 276`, `Myth 289`
- special track review column: `298` for weapons/trinkets only; armor, cloak, and jewelry were not given a 298 lane
- current catalog state: `251161 / 猎魂者的斗篷` has verified dungeon/observed 289 variants; the other 19 loot items still have dungeon source variants `partial` with top blocker `missing deterministic SimC variant preset`; observed_profile 289/298 variants exist on several items but do not make their dungeon source verified
- socket metadata: no prismatic socket found in the cached loot metadata for this instance
- user validation: user waived per-instance manual confirmation after Magisters; Maisara output remains a derived candidate set until deterministic SimC variant evidence exists
- write status: no database write, no deploy, and no catalog promotion; results are still derived manual-review candidates

Nexus-Point Xenas result snapshot:

- instance: `1316` / `节点希纳斯`
- loot items: `20`
- source refs used: production `/opt/wow-mini-program/server/data/wow_news.sqlite3` read-only query, Battle.net journal loot metadata already cached, production SimC `/opt/wow-simc/current/simc`
- normal track review columns: `Champion 263`, `Hero 276`, `Myth 289`
- special track review column: `298` for weapons/trinkets only; shields, armor, cloaks, and rings were not given a 298 lane
- current catalog state: `251093 / 圣光的遗落`, `251210 / 蚀影轻履`, and `251217 / 虚空的遮蔽` have verified dungeon/observed 289 variants; the other 17 loot items still have dungeon source variants `partial` with top blocker `missing deterministic SimC variant preset`; observed_profile 289/298 variants exist on several items but do not make their dungeon source verified
- socket metadata: `251093 / 圣光的遗落` and `251217 / 虚空的遮蔽` have prismatic sockets in the reviewed table
- user validation: user waived per-instance manual confirmation after Magisters; Nexus-Point Xenas output remains a derived candidate set until deterministic SimC variant evidence exists
- write status: no database write, no deploy, and no catalog promotion; results are still derived manual-review candidates

Algeth'ar Academy result snapshot:

- instance: `1201` / `艾杰斯亚学院`
- loot items: `24`
- source refs used: production `/opt/wow-mini-program/server/data/wow_news.sqlite3` read-only query, Battle.net journal loot metadata already cached, production SimC `/opt/wow-simc/current/simc`
- normal track review columns: `Champion 263`, `Hero 276`, `Myth 289`
- special track review column: `298` for weapons/trinkets only; shields, held-in-off-hand items, armor, cloaks, and rings were not given a 298 lane
- current catalog state: `193708 / 白金星辰指环`, `193712 / 药渍披风`, and `193714 / 狂根腕扣` have verified dungeon/observed 289 variants; `193701 / 艾杰斯亚谜题盒` has verified dungeon/observed 298 variants as a trinket special lane; the remaining 20 loot items still have dungeon source variants `partial` with top blocker `missing deterministic SimC variant preset`; observed_profile 289/298 variants exist on several items but do not make their dungeon source verified
- socket metadata: only `193708 / 白金星辰指环` has a prismatic socket in the reviewed table
- user validation: user waived per-instance manual confirmation after Magisters; Algeth'ar Academy output remains a derived candidate set until deterministic SimC variant evidence exists
- write status: no database write, no deploy, and no catalog promotion; results are still derived manual-review candidates

Pit of Saron result snapshot:

- instance: `278` / `萨隆矿坑`
- correction: this slice initially used raw Battle.net Journal loot and is overbroad for a current-season M+ review; do not treat the `74` rows, or the first `49`-row local filter, as accepted current-season gear
- raw/journal-candidate filter: raw Journal rows `74`; first local filter `49`; excluded `25` `133xxx` same-name rare duplicate rows; this is only an upper-bound candidate set
- current-season source-reference filter: accepted manual-review candidates `24`; exclude the other `25` rows from the first `49`-row local filter unless a stronger current-season source is found
- source-reference candidate ids: `50228`, `49812`, `49823`, `49825`, `49809`, `50263`, `49805`, `50264`, `49806`, `49817`, `49824`, `50233`, `49810`, `49811`, `49819`, `50234`, `50272`, `49808`, `252421`, `50259`, `49807`, `50227`, `49802`, `49813`
- raw loot items: `74` (`49` epic, `25` rare); bosses: `熔炉之主加弗斯特`, `伊克和科瑞克`, `天灾领主泰兰努斯`
- source refs used: production `/opt/wow-mini-program/server/data/wow_news.sqlite3` read-only query, Battle.net journal loot metadata already cached, production SimC `/opt/wow-simc/current/simc`
- normal track review columns: `Champion 263`, `Hero 276`, `Myth 289`
- special track review column: `298` for main-hand weapons and trinkets only; shields, held-in-off-hand items, armor, cloaks, necks, and rings were not given a 298 lane
- journal-candidate SimC coverage: see [reused dungeon current-season candidate review](2026-06-23-reused-dungeon-current-season-candidates.md); its `49`-row Pit table is retained as downfilter evidence, not accepted current-season coverage
- obsolete raw SimC candidate coverage: the previous `238` raw cells came from the overbroad 74-row slice and must not be used as accepted current-season coverage
- current catalog state: `70` loot items still have dungeon source variants `partial` with top blocker `missing deterministic SimC variant preset`; `4` loot items currently lack a dungeon variant row and should remain source-gap/partial until catalog evidence is fixed; `13` loot items have observed verified variants at `276`, `289`, or `298`, but observed variants do not make their dungeon source verified
- socket metadata: `49803 / 红玉骨戒`, `49804 / 闪亮的镜盔`, `50229 / 寒冰深渊腿甲`, `50228 / 尖刺伊米亚颈饰`, `49812 / 被盗的婚戒`, `49816 / 天灾领主的冰封胸甲`, `50271 / 败坏灵魂指环`, `49822 / 霜织丝裤`, `50267 / 枭首`, and `49818 / 苦痛刺圈` have cached sockets
- user validation: user rejected `49` as too high and accepted the `24`-item source-reference target as the next review basis; Pit of Saron output remains a derived candidate set until deterministic SimC variant evidence exists
- write status: no database write, no deploy, and no catalog promotion; results are still derived manual-review candidates

Seat of the Triumvirate result snapshot:

- instance: `945` / `执政团之座`
- correction: this is also a reused legacy dungeon; the first `44`-row raw Journal slice is only a journal-candidate upper bound, not accepted current-season coverage
- raw/journal-candidate filter: raw Journal rows `44`; first local filter `44`; excluded `0` by local duplicate/id-bucket rules; this remains overbroad without a current-season source reference
- current-season source-reference filter: accepted manual-review candidates `35`; exclude the other `9` rows from the raw slice unless a stronger current-season source is found
- source-reference candidate ids: `151309`, `151308`, `151311`, `151337`, `151299`, `151303`, `151305`, `151300`, `151304`, `151336`, `151315`, `151318`, `151316`, `151314`, `151317`, `151323`, `151325`, `151321`, `151326`, `151338`, `151333`, `151331`, `151329`, `151332`, `151327`, `151330`, `151307`, `151312`, `151310`, `151340`, `258524`, `258525`, `258516`, `258514`, `258523`
- source discrepancy: `258523 / 奈扎尔的虚空爪` is included through item-page cross-reference to `总督奈扎尔`, because it was not present in the guide table's off-hand/shield section
- loot items: `44` (`44` rare); bosses: `晋升者祖拉尔`, `萨普瑞什`, `总督奈扎尔`, `鲁拉`
- source refs used: production `/opt/wow-mini-program/server/data/wow_news.sqlite3` read-only query, Battle.net journal loot metadata already cached, production SimC `/opt/wow-simc/current/simc`
- normal track review columns: `Champion 263`, `Hero 276`, `Myth 289`
- special track review column: `298` for main-hand weapons and trinkets only; off-hand items, armor, necks, and rings were not given a 298 lane
- journal-candidate SimC coverage: the first `44`-row table computed `140` derived stat cells with no SimC process failures; downfilter to the `35`-item source-reference set before accepted manual review
- current catalog state: `41` loot items still have dungeon source variants `partial` with top blocker `missing deterministic SimC variant preset`; `3` loot items currently lack a dungeon variant row and should remain source-gap/partial until catalog evidence is fixed; `6` loot items have observed verified variants, but observed variants do not make their dungeon source verified
- socket metadata: `151308 / 艾瑞达斯贵族印戒`, `151309 / 扭曲虚空项链`, and `151311 / 执政团指轮` have cached sockets
- user validation: user rejected `44` as too high and accepted the `35`-item source-reference target as the next review basis; Seat of the Triumvirate output remains a derived candidate set until deterministic SimC variant evidence exists
- write status: no database write, no deploy, and no catalog promotion; results are still derived manual-review candidates

Skyreach result snapshot:

- instance: `476` / `通天峰`
- correction: this slice used raw Battle.net Journal loot and is overbroad for a current-season M+ review; the `230` rows include legacy/global dungeon loot and must not be treated as the accepted current-season gear list
- current-season source-reference filter: raw Journal rows `230`; accepted manual-review candidates `28`; excluded `202` historical/global rows
- local candidate rule: keep `252xxx` trinkets and `258xxx` current item ids; exclude `109xxx`, `110xxx`, and `112xxx` Warlords-era/global dungeon buckets
- raw loot items: `230` (`230` rare); bosses: `兰吉特`, `阿拉卡纳斯`, `鲁克兰`, `高阶贤者维里克斯`
- source refs used: production `/opt/wow-mini-program/server/data/wow_news.sqlite3` read-only query, Battle.net journal loot metadata already cached, production SimC `/opt/wow-simc/current/simc`
- normal track review columns: `Champion 263`, `Hero 276`, `Myth 289`
- special track review column: `298` for main-hand weapons and trinkets only; off-hand items, armor, cloaks, necks, and rings were not given a 298 lane
- source-reference SimC coverage: see [reused dungeon current-season candidate review](2026-06-23-reused-dungeon-current-season-candidates.md); the `28`-row Skyreach table is accepted as source-reference, while deterministic SimC variant gaps still keep most rows `partial`
- obsolete raw SimC candidate coverage: the previous `709` raw cells came from the overbroad 230-row slice and must not be used as accepted current-season coverage
- current catalog state: `228` loot items still have dungeon source variants `partial` with top blocker `missing deterministic SimC variant preset`; `2` loot items currently lack a dungeon variant row and should remain source-gap/partial until catalog evidence is fixed; `10` loot items have observed verified variants at `289` or `298`, but observed variants do not make their dungeon source verified
- socket metadata: no cached socket metadata on reviewed loot rows
- user validation: user later requested processing the three reused dungeons separately, then writing the source-reference sets
- write status: production source-reference write completed for Skyreach together with Pit of Saron and Seat of the Triumvirate; deterministic SimC variant gaps still prevent most items from becoming `verified`

Reused legacy dungeon loot filter blocker:

- read-only diagnosis: `Pit of Saron / 萨隆矿坑` raw Journal loot is `74` rows because it contains original Wrath item ids (`498xx` / `502xx`), duplicated Legion-timewalking style rows (`133xxx`) with the same names, and one newer observed/current-season row (`252421`)
- read-only diagnosis: `Skyreach / 通天峰` raw Journal loot is `230` rows because it contains Warlords-era global dungeon loot (`109xxx`, `110xxx`, `112xxx`) plus a smaller newer observed/current-season-looking subset (`252xxx`, `258xxx`)
- evidence: Pit has `24` duplicate item names across `498xx` and `133xxx`; Skyreach has large generic slot buckets such as `30` rings, `24` necks, `23` feet, and only `10` loot rows with observed verified current-season variants
- conclusion: for reused legacy dungeons, `websim_loot` / `websim_gear_sources` currently represent raw Journal coverage, not the final current-season M+ loot subset
- execution decision: rewind acceptance for Pit of Saron, Seat of the Triumvirate, and Skyreach raw attribute slices; do not write or promote raw Journal lists as accepted current-season coverage
- first local filter result, now classified as `journal_candidate`: Pit `74 -> 49`, Skyreach `230 -> 28`, Seat `44 -> 44`
- current-season source-reference cross-check result: Pit accepted target `24`; Seat accepted target `35`; Skyreach accepted target `28`
- evidence artifact: [reused dungeon current-season candidate review](2026-06-23-reused-dungeon-current-season-candidates.md)
- next required action: continue deterministic SimC variant preset backfill for accepted reused-dungeon items that remain `partial`; do not promote raw Journal-only counts beyond their candidate/excluded statuses
- 2026-06-23 user review update: user agreed the Pit `49` and Seat `44` candidate counts still look too high for accepted current-season loot. Treat those as `journal-candidate`, not accepted source coverage.
- stricter evidence rule: `season_revision`, raw Battle.net Journal membership, and Battle.net `preview_item.bonus_list` are not enough to include a reused legacy-dungeon item in the accepted current-season subset. They can only create manual-review candidates.
- observed-confirmed local subset: production read-only `observed_profile` verified variants currently confirm Pit `13` items and Seat `6` items. This is a confirmed observed subset, not a complete loot table.

2026-06-23 production source-reference write:

- backup: `/opt/wow-mini-program/backups/wow_news.sqlite3.20260623T100725Z.pre-reused-legacy-source-reference.bak`
- source status result: Pit `24 source_reference / 25 journal_candidate / 25 excluded_legacy_bucket`; Seat `34 source_reference / 1 source_discrepancy / 9 journal_candidate`; Skyreach `28 source_reference / 202 excluded_legacy_bucket`
- variant result: accepted reused-dungeon variants updated `141`; restored `62` deterministic variants to `verified`; kept `79` as `partial` with `missing deterministic SimC variant preset`
- health result: `/api/data/health` M+ coverage `8/8`, `sourceItemCount=464`; raid coverage remains outside this write scope
- traversal result: all `40` class/spec compact gear payloads returned without incompatible candidates, journal/excluded source leakage, or observed-profile drop-source disguise
- validation state split: `observed_confirmed` for the narrow proven set, `source_reference` for the accepted manual-review target, `journal_candidate` for the larger raw/local-filter set, `excluded_legacy_bucket` for raw-only historical buckets, and `source_discrepancy` for guide/item-page disagreements requiring explicit notes.

Current raid pool blocker snapshot:

- read-only scope: production `/api/game/season`, production `/api/data/health`, production `/opt/wow-mini-program/server/data/wow_news.sqlite3`, and local `server/websim_payload.py` / `tests/websim_payload_test.py`
- local code state: `MIDNIGHT_CURRENT_SEASON_RAIDS` is already `The Voidspire`, `The Dreamrift`, `March on Quel'Danas`, and `Sporefall`; tests assert these raids are selected and `Manaforge Omega` is excluded
- production season state: `/api/game/season` returns those four raid names only as placeholders with empty `id` / `instanceId`; `raidPoolStatus.refs` is empty and blocker is `current season raid pool missing verified journal refs`
- production DB state: `websim_instances` currently has only raid `1302 / 法力熔炉：欧米伽` with `91` loot rows and `91` raid gear sources; no rows exist for `The Voidspire`, `The Dreamrift`, `March on Quel'Danas`, or `Sporefall`
- production health state: `gear_catalog.details.seasonSourceCoverage.raid` reports expected `4`, covered `0`, missing `4`, missing instances `The Voidspire`, `The Dreamrift`, `March on Quel'Danas`, and `Sporefall`; blockers include `current season raid pool missing verified journal refs` and `4 current expansion raid missing gear loot`
- execution decision: stop before raid attribute calculation because the required instance ids and loot are missing; do not run full sync or write catalog rows from this state
- next required action: resolve or sync verified current raid journal refs first, then start the raid slice order with `Sporefall`

2026-06-23 follow-up:

- user confirmed proceeding with the raid-slice plan after the first 4-raid production count returned `0 / 0 / 0 / 0`.
- fresh production checks still show `/api/game/season` exposing only placeholder raid names and `/api/data/health` reporting `expected 4 / covered 0 / missing 4` for raid coverage; the stale `91` raid sources are still `Manaforge Omega` and must stay excluded from current-season coverage.
- remote read-only diagnostics show Blizzard API credentials are present in `/etc/wow-backend.env`; the production miss comes from journal expansion selection under `zh_CN`: Battle.net returns expansion `505 / 本赛季`, but the old selector only matched `Current Season` / `Midnight`, then fell back to the last expansion `514 / 地心之战` and kept `Manaforge Omega`.
- local follow-up fix: `selected_journal_instance_refs` now recognizes localized `本赛季` / `至暗之夜`, and current-season raid filtering canonicalizes localized raid names such as `虚影尖塔`, `梦境裂隙`, `进军奎尔丹纳斯`, and `孢陨幽境` back to the stable English allowlist.
- next gate before any production DB write: deploy the selector fix, then run a controlled Blizzard journal sync with service credentials and verify raid refs resolve to `1307 / The Voidspire`, `1314 / The Dreamrift`, `1308 / March on Quel'Danas`, and `1305 / Sporefall`. Do not write Wowhead/guide-derived raid rows into the catalog without explicit approval because they are network-fetched content and must be labeled as `source_reference`, not verified Battle.net journal loot.

2026-06-23 production follow-up:

- deployed the `server/websim_payload.py` selector/canonicalization fix by hot-patching the single backend file, then restarted `wow-backend`; `/health` stayed verified and `wow-websim-sync.service` remained inactive with the timer active.
- backed up production SQLite to `/var/lib/wow-backend/backups/wow_news-before-raid-sync-20260623-194247.sqlite3` before writing.
- ran a controlled raid-only Blizzard journal slice with the production service credentials. The first full path was aborted before visible writes because it was spending too long on dungeon/item metadata; the final slice skipped M+ instance refetch, synced the 4 current raids, rebuilt `gearCatalog`, removed stale raid instance `1302 / 法力熔炉：欧米伽`, and refreshed `websim_sync` to the current partial snapshot.
- production verified refs: `1307 / The Voidspire / 虚影尖塔`, `1314 / The Dreamrift / 梦境裂隙`, `1308 / March on Quel'Danas / 进军奎尔丹纳斯`, and `1305 / Sporefall / 孢陨幽境`; `raidPoolStatus.blockers=[]`.
- production loot/source counts: The Voidspire `60`, The Dreamrift `8`, March on Quel'Danas `24`, Sporefall `12`, total raid `sourceItemCount=104`; `法力熔炉` loot query now returns `0`.
- production `/api/data/health` now reports `seasonSourceCoverage.raid expected 4 / covered 4 / missing 0`, `journalLoot.status=verified`, `missingCatalogSourceCount=0`, and no stale raid source examples. Overall `gear_catalog` remains `partial` only because of remaining deterministic SimC variant presets, trusted-source gaps outside the current raid slice, and socket gem metadata.

2026-06-23 item-level variant backfill follow-up:

- user approved the Dreamrift and March on Quel'Danas loot lists, then asked to calculate and write the corresponding attributes using the Mythic+ instance-slice scheme.
- added `backfill_official_item_level_variants_for_instance` in `server/websim_payload.py`. It writes accepted `simulationcraft_item_level_probe` variants for verified official loot sources, using normal tracks `Champion 263`, `Hero 276`, and `Myth 289`, plus `Void Upgrade 298` only when the item is eligible under the current special-lane rule. It records SimC-derived `itemStats`, `statSummary`, probe class/spec, and the generated gear line in variant payload.
- production dry run on a copied SQLite DB wrote `109` verified variants and `0` partial variants in `18.553s`: The Dreamrift `8` items / `27` tracks, March on Quel'Danas `24` items / `82` tracks. A first dry run exposed the Demon Hunter warglaive off-hand requirement for `260408 / 泯光哀歌`; the probe builder now removes off-hand only for two-handed/ranged main-hand probes.
- production write used the shared sync lock and first backed up SQLite to `/var/lib/wow-backend/backups/wow_news-before-raid-itemlevel-backfill-20260623-123445.sqlite3`. Final production write result: The Dreamrift `27/27` verified, March on Quel'Danas `82/82` verified, aggregate `109` verified item-level variants and `0` partial.
- production verification: `/api/data/health` remains `gear_catalog.partial` but raid coverage is still `4/4`, `staleSourceCount=0`, and `journalLoot.status=verified`; current variant readiness is `824 verified / 521 partial / 1345 total`. `/api/websim/loot?instanceId=1314` returns `8`; `/api/websim/loot?instanceId=1308` returns `24` split as `11` for 至暗之夜降临 and `13` for 贝洛朗，奥的子嗣. Full 40-spec compact gear traversal passed with no incompatible candidates; only the expected empty off-hand slots remain for 8 two-hand/no-offhand specs.

2026-06-23 remaining raid item-level variant backfill follow-up:

- user asked to continue the remaining instances without another manual confirmation. Scope was interpreted as the two remaining current-season raids after Dreamrift and March on Quel'Danas: `1307 / The Voidspire / 虚影尖塔` and `1305 / Sporefall / 孢陨幽境`.
- first production-copy dry run showed The Voidspire `60` items / `202` tracks all verified, but Sporefall `12` items / `48` tracks all partial because SimulationCraft BCP item fetch returned `401`. Root cause was local to `server/websim_payload.py`: the item-level probe runner did not pass Blizzard credentials to SimC, while the observed-gear runner already wrote `WOW_BLIZZARD_CLIENT_ID/SECRET` into a temporary `~/.simc_apikey`.
- local fix: `run_websim_simcraft_process` now creates a temporary SimC HOME with `.simc_apikey` when Blizzard credentials are present. Regression test: `test_run_websim_simcraft_process_passes_blizzard_api_key_to_simc_home`.
- after hot-patching production `server/websim_payload.py` and restarting `wow-backend`, the second production-copy dry run removed the 401 failure. Final dry-run result: The Voidspire `202/202` verified; Sporefall still `0/48` verified and `48` partial because current production SimC/BCP returns `unable to download item id=268284 information from Blizzard, reason: The document is empty` for the `268xxx` Sporefall items. The SimC JSON exits successfully but does not include the target item in the gear slot, so `itemId + ilevel` cannot calculate attributes for this raid yet. Battle.net metadata has base stats for 11 of 12 Sporefall rows at preview level `219`; `268280 / 孢子大王的蕈菇盖` is cosmetic with no stats. Do not promote Sporefall variants until SimC/BCP supports these item documents or a separately verified scaling fallback is designed and tested.
- production write was limited to The Voidspire only. Backup before write: `/var/lib/wow-backend/backups/wow_news-before-voidspire-itemlevel-backfill-20260623-205548.sqlite3`. The write used the shared sync lock with the ordinary `ubuntu` user opening `/run/lock/wow-mini-program-sync.lock`, then `sudo env python3` inside the lock because `sudo flock` cannot open that lock file on this host.
- production write result: The Voidspire `60` source items / `202` verified variants / `0` partial in `31.165s`; tracks are `Champion 263 = 60`, `Hero 276 = 60`, `Myth 289 = 60`, and `Void Upgrade 298 = 22`.
- production verification after backend restart: current raid source counts remain Sporefall `12`, The Voidspire `60`, March on Quel'Danas `24`, Dreamrift `8`; item-level verified track rows now exist for `1307`, `1308`, and `1314`, with no `1305` verified item-level rows. `/api/data/health` remains `gear_catalog.partial`; variant readiness is now `1026 verified / 521 partial / 1547 total`. `/api/websim/loot?instanceId=1307` returns `60`, `/api/websim/loot?instanceId=1305` returns `12`. Full `39` spec compact gear traversal passed with `0` incompatible candidates; only `8` expected off-hand-empty specs remain (`deathknight` blood/frost/unholy, `druid` feral/guardian, `hunter` beast_mastery/marksmanship, `monk` brewmaster).

2026-06-24 current-season M+ item-level variant backfill follow-up:

- scope: write accepted M+ `source_reference/source_discrepancy` item-level probe variants into production DB, and write Sporefall failed probe rows as explicit `partial` blockers instead of silently skipping them. The write still excludes raw-only reused-dungeon rows: Pit of Saron skipped `50`, Seat of the Triumvirate skipped `9`, and Skyreach skipped `202` `journal_candidate` / `excluded_legacy_bucket` rows.
- backup before write: `/var/lib/wow-backend/backups/wow_news-before-itemlevel-backfill-20260624-111442.sqlite3`.
- production write result: `215` accepted source items / `723` item-level tracks processed in `166.650s`; `675` verified and `48` partial. Per-instance verified counts: Seat of the Triumvirate `35` items / `113` tracks, Algeth'ar Academy `24` / `82`, Nexus-Point Xenas `20` / `65`, Pit of Saron `24` / `78`, Maisara Caverns `20` / `68`, Skyreach `28` / `96`, Windrunner Spire `26` / `87`, Magisters' Terrace `26` / `86`.
- remaining item-level non-verified rows: Sporefall `12` items / `48` tracks (`263`, `276`, `289`, `298` for each item) remain `partial` because SimC JSON does not include the target item stats for item ids `268280`, `268282`, `268283`, `268284`, `268285`, `268286`, `268287`, `268288`, `268289`, `268290`, `268291`, and `268292`.
- production health after backend restart and compact read-model deployment: `/health` verified; `/api/data/health` reports `gear_catalog.partial` with variant readiness `1701 verified / 579 partial / 2280 total`. The remaining `579` non-observed partial variants are `520` old `needs-variant` placeholder rows with `missing deterministic SimC variant preset`, the `48` Sporefall item-level rows with `SimC JSON did not include target item stats`, plus `11` old raid statless verified rows corrected to partial. Observed stat coverage is `898 / 1369`; the remaining `471` observed variants now surface as partial/blocker instead of verified-without-stats. Full `40` class/spec compact API traversal passed with `0` request errors and `0` verified variants missing stats.
- compact gear smoke after write: production DB had `32` class/spec pairs with profile presets; all `32` `/api/websim/gear?compact=1` requests returned without request errors or candidate slot failures. This smoke is not a full 39/40-spec traversal because the enumeration source was current production profile presets.

## Task 1: Lock the Season Pool With Tests

**Files:**

- Modify: `server/websim_payload.py`
- Test: `tests/websim_payload_test.py`

**Step 1: Add failing tests for confirmed M+ pool**

Add a test that calls `current_season_payload()` or the explicit helper introduced in the implementation and verifies the eight dungeon names above are present and no stale Season 3 dungeon markers are present.

Run:

```bash
python3 -m unittest tests.websim_payload_test -k season
```

Expected: fail until the helper and allowlist are explicit enough.

**Step 2: Add failing tests for confirmed raid pool**

Add a test for `current_season_raid_refs` or a new helper such as `official_current_season_raid_refs`:

- returns `The Voidspire`, `The Dreamrift`, `March on Quel'Danas`, `Sporefall`
- does not return `Manaforge Omega`
- does not silently fall back to the last raid ref when the journal expansion contains unrelated raids

Run:

```bash
python3 -m unittest tests.websim_payload_test -k raid
```

Expected: fail against the current `raids[-limit:]` behavior.

## Task 2: Replace Raid Selection Fallback

**Files:**

- Modify: `server/websim_payload.py`
- Test: `tests/websim_payload_test.py`
- Optional docs update: `docs/roadmap.md`, `docs/roadmap/ideas.md`

**Step 1: Add explicit raid constants and source refs**

Add constants near the existing `MIDNIGHT_SEASON_ONE_DUNGEONS`:

- `MIDNIGHT_CURRENT_SEASON_RAIDS`
- optional `MIDNIGHT_CURRENT_SEASON_RAID_NAME_KEYS`
- optional explicit instance ID env override support via `WOW_WEBSIM_CURRENT_SEASON_RAID_INSTANCE_IDS`

Keep env overrides explicit only. Do not use them to justify a default "last raid" fallback.

**Step 2: Change `current_season_raid_refs` behavior**

The function should:

- normalize any raid refs found from Battle.net Journal
- filter them by explicit configured IDs if present
- otherwise filter by confirmed current-season raid names
- return an empty list or blocked state if the expected current-season raids cannot be resolved
- never default to `raids[-1:]`

**Step 3: Carry blockers into sync/health**

If expected current-season raids are missing from journal selection, `sync_blizzard_journal` and `build_gear_catalog_sync_state` should surface a blocker such as:

```text
current season raid pool missing verified journal refs
```

Wrong-season refs should produce a stale-pool blocker instead of being accepted.

**Step 4: Verify**

Run:

```bash
python3 -m unittest tests.websim_payload_test
git diff --check
```

Expected: all pass, no whitespace errors.

## Task 3: Add Per-Instance Coverage

**Files:**

- Modify: `server/websim_payload.py`
- Test: `tests/websim_payload_test.py`

**Step 1: Extend season source coverage details**

In the health/catalog path that builds `gear_catalog.details.seasonSourceCoverage`, add per-instance rows for current M+ and raid refs.

Each row should expose at least:

- `instanceId`
- `name`
- `category`
- `expected`
- `covered`
- `verifiedItemCount`
- `partialItemCount`
- `missingReason` or `blockers`

**Step 2: Add tests for incomplete and complete instances**

Create fixture rows where one dungeon is complete and one raid is missing. Verify health can say exactly which instance is missing, instead of only giving global counts.

Run:

```bash
python3 -m unittest tests.websim_payload_test -k seasonSourceCoverage
```

Expected: fail before implementation, pass after per-instance coverage exists.

## Task 4: Implement Instance Slice Workflow

**Files:**

- Modify: `server/websim_payload.py`
- Optional create: `scripts/gear_instance_slice_probe.py`
- Test: `tests/websim_payload_test.py`

**Step 1: Pick the first slice**

Windrunner Spire was completed first for manual stat review at the user's request. Continue with the next instance slice from the remaining current-season pool. If Battle.net instance IDs are not already known locally, discover them read-only first. Before writing network-fetched data to disk or syncing production, ask the user for explicit approval.

**Step 2: Build or reuse a probe**

The probe should answer:

- Is the instance in the current season pool?
- Are all encounters present?
- Are loot items present?
- Which items are verified vs partial?
- Which partial items lack deterministic SimC variant fields?
- Are any wrong-season sources still accepted?

If adding a script, keep it read-only by default and add an explicit option for writing/syncing only after approval.

**Step 3: Fill one instance**

Use existing sync paths where possible. Do not invent item metadata. Battle.net metadata remains official for names, icons, inventory type, armor/weapon classification, and journal loot. SimC or observed variants remain required for executable variant fields.

**Step 4: Verify the slice**

Run:

```bash
python3 -m unittest tests.websim_payload_test
node --test tests/builds-page.test.js
git diff --check
```

If production sync/deploy is approved, also verify:

```bash
curl -sS "$PROD/api/data/health"
curl -sS "$PROD/api/game/season"
```

and run the all-class/spec compact gear traversal. Acceptance is not one mage sample; all 40 specs must still return compatible replacement candidates.

## Task 5: Repeat Per Instance

**Files:**

- Modify only files needed by the next instance slice.
- Update docs after each accepted slice.

Suggested remaining order after the Windrunner Spire validation slice:

1. `Magisters' Terrace`
2. `Maisara Caverns`
3. `Nexus-Point Xenas`
4. `Algeth'ar Academy`
5. `Pit of Saron`
6. `Seat of the Triumvirate`
7. `Skyreach`
8. `Sporefall`
9. `The Voidspire`
10. `The Dreamrift`
11. `March on Quel'Danas`

For each slice, record:

- source refs used
- verified/partial item counts
- top blockers
- attribute review result for `263 / 276 / 289` and any valid `298` special lane
- manual validation status
- any production sync/deploy evidence
- all-spec smoke result

## New Session Handoff Prompt

Use this prompt when starting a fresh Codex session to continue the remaining instance slices:

```text
你在 /Users/boyuan/Documents/wow_mini_program 仓库中工作。

先读并遵守：
1. AGENTS.md
2. docs/roadmap.md
3. docs/roadmap/ideas.md
4. docs/plans/2026-06-23-season-gear-instance-slice-plan.md

目标：继续按“逐副本 / 团本切片”补齐当前赛季自建装备数据库。不要大而全重建；每次只处理一个实例。Windrunner Spire / 风行者之塔已经作为样板完成 26 件装备属性人工核对，普通升级轨道口径已确认正确。

必须沿用的装备升级轨道规则：
- 勇士满级 = Champion 6/6 = ilvl 263
- 英雄满级 = Hero 6/6 = ilvl 276
- 神话满级 = Myth 6/6 = ilvl 289
- ilvl 298 不是普通神话满级，只能作为特例轨道：Ascendant Voidcore 可升级的武器/饰品，或 Sporefall/孢子幽境 Sporefused 掉落等有证据的特殊来源。

当前赛季池必须保持：
M+：Magisters' Terrace、Maisara Caverns、Nexus-Point Xenas、Windrunner Spire、Algeth'ar Academy、Pit of Saron、Seat of the Triumvirate、Skyreach。
团本：The Voidspire、The Dreamrift、March on Quel'Danas、Sporefall。
Manaforge Omega / 法力熔炉不是当前赛季团本，必须排除。

执行方式：
1. 从剩余实例里先选 Magisters' Terrace 开始；如果发现本地/生产库缺实例 id 或 loot，先只读定位原因，不要直接跑全量同步。
2. 用只读方式列出该实例全部装备：装备名称、boss/source、护甲/武器类型、inventory type、插槽、当前 verified/partial 状态、blocker。
3. 用部署环境的 SimulationCraft 对每件装备计算 263/276/289 三档属性；只对符合特例的武器/饰品或 Sporefall 特例装备计算 298。注意 SimC 槽位：shoulder -> shoulders，wrist -> wrists。
4. 输出完整表格给用户人工 check。此阶段不要写数据库；`itemId + ilevel` 计算结果只算 derived manual-review candidate。
5. 用户确认后，再考虑把该实例的装备属性/状态写入自建库；缺 deterministic SimC variant preset 的装备只能 partial，不能伪装 verified。
6. 每个大块修改后必须跑：
   - python3 -m unittest tests.websim_payload_test
   - node --test tests/builds-page.test.js
   - git diff --check
   - 全 40 职业专精 compact gear traversal，不能只看法师。

限制：
- 不要跑 CodeRabbit。
- 浏览官方文档可以；但下载、安装、pull/fetch、写入网络获取内容到磁盘，必须先向用户确认授权。
- 部署前先说明范围；部署后检查 /api/game/season 和 /api/data/health。
```

## Final Acceptance

- `/api/game/season` returns the confirmed M+ and raid pool.
- `Manaforge Omega` is absent from current-season raid coverage.
- Health exposes per-instance current-season coverage and blockers.
- Gear candidates do not show wrong-season sources as current.
- Partial items remain visibly partial when deterministic SimC variant presets are missing.
- All 40 class/spec combinations pass compact gear traversal after each substantial data change.
- `python3 -m unittest tests.websim_payload_test`, relevant Node tests, and `git diff --check` pass.
