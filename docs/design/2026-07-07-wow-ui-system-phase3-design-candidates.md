# WOW 小程序 UI 系统重建 Phase 3 Design Candidates

Status: `design_candidate_brief`
Created: 2026-07-07

Linked goal:

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Phase 1/2 Inventory](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md)

This document opens Phase 3. It does not lock a final target, does not authorize implementation, and does not replace runtime verification.

## Design Read

Reading this as: a high-density consumer WoW companion mini-program for players making build and simulation decisions, with a dark Azeroth evidence-console language, leaning toward a custom component system rather than a generic dashboard or marketing aesthetic.

Taste dials for this product:

- `DESIGN_VARIANCE: 6/10`: WoW material and asymmetric hierarchy are allowed, but the app must stay navigable and repeatable.
- `MOTION_INTENSITY: 2/10`: only tactile taps, segmented controls, drawers and expand/collapse. No cinematic motion before runtime stability.
- `VISUAL_DENSITY: 8/10`: first screens must preserve fast scanning, blockers, evidence status and next action.

## Fixed Product Facts

Every candidate below uses the same facts. A candidate may change layout and visual language; it may not change the product truth.

- Current registered app pages: news home/list/detail, builds tab, workbench, intel, talent simulator, gear detail, simulator tab, SimC, Chickenbro, tasks, task detail and profile.
- Core user chain: read version/news signal -> pick or inherit class/spec/hero/scenario -> inspect talents and gear -> determine readiness -> fix blocker or submit SimC -> ask Chickenbro to explain evidence.
- Readiness states: `ready_to_simulate`, `blocked`, `partial`, `stale`, `source_reference`, plus `unknown` only while loading or when evidence is absent.
- No complete SimC-ready talents plus core gear means no DPS, no comprehensive score, no S/A grade and no upgrade-priority claim.
- Real WoW objects use real sources only: interface/API payload, Battle.net/WebSim mapping, verified repo asset or user-provided asset. imagegen may not invent class/spec/talent/equipment/source icons.
- imagegen output is allowed only as low-semantic material: `panel`, `border`, `texture`, `socket`, `state-base`, `state-atomic`, `decorative`.
- Bottom tab, safe area, navigation and keyboard avoidance must follow real WeChat mini-program chrome. No fake time, battery, Wi-Fi or capsule.
- Chickenbro is a first-class surface, not a leftover chat page. It must support empty session, generating, completed reply, failed reply, evidence explanation, topic drawer, new topic, input focus and long-message scroll.

## Candidate Rules

- Produce 2-3 visually and structurally different candidates before any `target_locked` claim.
- Candidates must use the same route map and the same sample evidence facts so comparison is about UI quality, not invented content.
- Each candidate must cover all core surfaces at the information-architecture level: news, builds tab, workbench, talents, gear, SimC, Chickenbro, tasks and profile.
- Each candidate must name which foundation components it stresses and which risks it reduces.
- Whole-page imagegen concepts are reference only. If a candidate later receives imagegen work, the output must be split into low-semantic material manifest entries before production use.
- Candidate status can only be `design_candidate_brief`, `reference_visual`, `target_candidate`, or `target_locked`. This file is not `target_locked`.

## Shared Sample Facts For Candidate Comparison

Use these as neutral fixture facts when producing candidate visuals, browser previews or component boards:

| Fact Type | Fixture |
| --- | --- |
| Current object | 法师 / 冰霜 / 法术投射者 |
| Scenarios | 单体, 5目标, 大秘境 |
| Ready fixture | 天赋可读, 装备 16/16, SimC 可提交, 队长可解释 |
| Blocked fixture | 天赋部分可读, 装备 0/16 或缺核心槽, SimC 待补齐, 队长限证据 |
| Partial fixture | WebSim source_reference, local template missing, checkedAt visible |
| News fixture | 官方更新, 社区讨论, 攻略内容, source_reference 行都要可见 |
| Chickenbro fixture | one empty session, one generating state, one evidence-backed reply, one failed/fallback reply |

These are fixture labels for layout and state testing. They are not permanent product copy and cannot be promoted to runtime fact without payload evidence.

## Candidate A: Evidence Cockpit

Core idea: make the app feel like a compact WoW command cockpit. The current object and readiness decision are always near the top; every page answers "what is the current state and what do I do next?"

### Surface Direction

| Surface | Candidate A Layout |
| --- | --- |
| News home | Top intelligence strip, source status chips, one large hero story, six-channel dock, ranked feed with state-aware thumbnails. |
| Builds tab | Current spec console first, workbench entry second, old talent/gear/SimC/tasks entries as compact workflow rail. |
| Workbench | Identity cockpit, dominant readiness slab, four-module dock, evidence ledger. |
| Talents | Talent source switcher, tree coverage summary, import/apply/save actions, blocker strip. |
| Gear | 16-slot equipment board, missing-slot callout, source/catalog strip, compact item picker entry. |
| SimC | Submit gate, template pair summary, task-lock indicator, deterministic next action. |
| Chickenbro | Co-pilot cockpit with current context pinned above chat, evidence drawer one tap away, input fixed with safe-area owner. |
| Tasks/Profile | Task queue and template vault use the same module-card rhythm as workbench. |

### Component Emphasis

`AppShell`, `PageFrame`, `WowPanel`, `StatusVisual`, `ModuleCard`, `EvidenceLedger`, `ChatShell`.

### Strength

- Best at preserving the fast scanning information the user called out.
- Strongest route from workbench to SimC/gear/talent/Chickenbro.
- Easier to compare against prior v2.1 target layouts.

### Risk

- Can become over-framed if every row receives heavy borders.
- Needs strict typography scale so dense information does not become tiny or cramped.

## Candidate B: Evidence Ledger

Core idea: make evidence provenance and source freshness the visual backbone. The product feels like an adventure journal mixed with a verification ledger: less hero-heavy, more readable for veteran players.

### Surface Direction

| Surface | Candidate B Layout |
| --- | --- |
| News home | Source ledger header, chronological ranked list, channel filter as narrow rail, fewer decorative panels. |
| Builds tab | Class/spec picker with evidence summaries, then a two-column compact module ledger for talents/gear/SimC/Chickenbro. |
| Workbench | Readiness verdict is compact; evidence ledger is above module dock and can expand into source rows. |
| Talents | Tree coverage and source rows dominate; real icon sockets are smaller and strictly object-bound. |
| Gear | Slot ledger grouped by missing/ready/source_reference; item visuals are secondary to completeness. |
| SimC | Form-like evidence checklist before submit, clear blocked reasons, no decorative submit theater. |
| Chickenbro | Evidence-first answer layout: user asks, captain replies with short answer, then "依据" rows in human language. |
| Tasks/Profile | Audit-log style list with status, checkedAt and owner boundaries. |

### Component Emphasis

`PageFrame`, `EvidenceLedger`, `StatusVisual`, `ActionButton`, `RankedFeed`, `ChatShell`.

### Strength

- Best for data trust and veteran-player confidence.
- Lowest risk of imagegen material overpowering real content.
- Easier to verify with source and route smoke tests.

### Risk

- May feel less magical or less App-like if material language is too restrained.
- Needs a strong navigation and status rhythm so it does not become a plain list app.

## Candidate C: Party Operations

Core idea: frame the app around a player preparing for content with a team. The pages feel like an operations board: build state, tasks, queue and Chickenbro guidance are integrated more visibly.

### Surface Direction

| Surface | Candidate C Layout |
| --- | --- |
| News home | "Today's operations" feed: official news, gameplay-impact updates and saved topics grouped by action relevance. |
| Builds tab | Current loadout board with three lanes: build, simulate, ask captain. Old entries become lane actions. |
| Workbench | Mission card with readiness, blocker lane and captain hint; module cards are arranged as an action sequence. |
| Talents | Talent loadout as preparation step, with import/save/apply and source confidence. |
| Gear | Gear readiness as checklist, missing slots grouped by role impact without inventing DPS. |
| SimC | Queue handoff view: submit-ready profile, active task limit, recent tasks. |
| Chickenbro | Captain room: topic drawer, context chip, answer stream and next question prompts grounded in evidence. |
| Tasks/Profile | Mission history plus personal vault. Templates are presented as reusable loadouts. |

### Component Emphasis

`AppShell`, `ModuleCard`, `ActionButton`, `StatusVisual`, `ChatShell`, `GameObjectIcon`.

### Strength

- Best at making Chickenbro and task history feel like first-class product surfaces.
- Strongest "complete app" narrative, beyond a single workbench screen.
- Good for novice players because next actions are explicit.

### Risk

- Highest risk of changing product hierarchy too much if mission framing hides evidence.
- Needs careful copy discipline so "队长" does not imply unsupported judgment or fabricated recommendation.

## Target Lock Scorecard

A candidate cannot be locked without scoring each row below. The score is internal design evidence, not user-facing proof.

| Criterion | Weight | Required Evidence |
| --- | ---: | --- |
| Information retention | 20 | First screen keeps object, readiness, blockers, next action, module state and source boundary. |
| Component ownership | 18 | Every visual structure maps to a foundation owner; page-private geometry is called out as forbidden. |
| WoW material quality | 14 | Uses low-semantic material with real object icon slots; no fake WoW fact assets. |
| Evidence trust | 16 | No strong claims without source; `blocked/partial/stale/source_reference` are distinct and stable. |
| Chickenbro completeness | 12 | Chat states and evidence explanation are designed, not deferred. |
| Route smoke readiness | 10 | Candidate names routes and transitions that must be smoked. |
| Adaptation fit | 10 | Compact, standard and large viewports have explicit density rules. |

`target_locked` requires:

- One chosen candidate or a declared hybrid with exact borrowed pieces.
- Surface-by-surface target notes for news, builds, workbench, talents, gear, SimC, Chickenbro, tasks and profile.
- Component decomposition list.
- Asset slicing brief and production/quarantine manifest plan.
- Route smoke checklist.
- Explicit "not runtime_verified" status until real mini-program screenshots and overlays exist.

## Recommended Next Move

Recommended direction for the next design round: start with Candidate A as the main structure, borrow Candidate B evidence rows, and borrow Candidate C's Chickenbro/task treatment. This is not a target lock; it is the strongest starting hypothesis because it preserves fast scanning while fixing the missing first-class chat and evidence systems.

Next artifact should be a `target_candidate` contact sheet with:

- Current screenshot strip.
- Candidate A/B/C wireframes for news, builds, workbench and Chickenbro.
- Shared fixture facts visible on every candidate.
- Notes showing which elements become `AppShell`, `PageFrame`, `WowPanel`, `StatusVisual`, `EvidenceLedger`, `ModuleCard`, `RankedFeed`, `ChannelDock`, `ActionButton`, `GameObjectIcon` and `ChatShell`.

## Target Candidate Artifact

Phase 3 first contact sheet:

- Contact sheet: `artifacts/ui-system-rebuild/20260707-phase3-target-candidates/phase3-target-candidate-contact-sheet.png`
- Manifest: `artifacts/ui-system-rebuild/20260707-phase3-target-candidates/manifest.json`
- Generator: `artifacts/ui-system-rebuild/20260707-phase3-target-candidates/render_phase3_target_candidates.py`

Status remains `target_candidate_reference`:

- It compares A/B/C against archived current evidence.
- It is not `target_locked`.
- It is not `runtime_verified`.
- It does not authorize implementation.
- It does not replace future imagegen material slicing, component decomposition, route smoke or real WeChat mini-program screenshots.

## Target Lock Proposal Artifact

The first proposed hybrid target direction is documented in:

- Proposal: `docs/design/2026-07-07-wow-ui-system-target-lock-proposal.md`
- Manifest: `artifacts/ui-system-rebuild/20260707-target-lock-proposal/manifest.json`

The proposal status is `target_lock_proposal`, not `target_locked`. It still needs user confirmation or written modification before implementation permits can exist.
