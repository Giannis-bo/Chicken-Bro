# WOW 小程序 UI 系统重建 Target Lock Proposal

Status: `target_lock_proposal`
Created: 2026-07-07

Linked evidence:

- [UI 系统重建 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Phase 1/2 Inventory](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md)
- [Phase 3 Design Candidates](2026-07-07-wow-ui-system-phase3-design-candidates.md)
- [Foundation Component Contracts](2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Asset Manifest Draft](2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Route Smoke And Runtime Verification Plan](2026-07-07-wow-ui-system-route-smoke-plan.md)
- [Foundation Harness Draft](2026-07-07-wow-ui-system-foundation-harness-draft.md)
- [Production Component Precheck](2026-07-07-wow-ui-system-production-component-precheck.md)
- [Browser Component Precheck](2026-07-07-wow-ui-system-browser-component-precheck.md)
- `artifacts/ui-system-rebuild/20260707-phase3-target-candidates/manifest.json`
- `artifacts/ui-system-rebuild/20260707-foundation-component-contracts/manifest.json`
- `artifacts/ui-system-rebuild/20260707-asset-manifest-draft/manifest.json`
- `artifacts/ui-system-rebuild/20260707-route-smoke-plan/manifest.json`
- `artifacts/ui-system-rebuild/20260707-foundation-harness/manifest.json`

This proposal is not `target_locked` until the user confirms it. It is not an implementation permit and does not authorize page WXML/WXSS edits.

## Proposal

Lock the product direction as a hybrid:

- Use Candidate A `Evidence Cockpit` as the app shell and first-screen structure.
- Borrow Candidate B `Evidence Ledger` for evidence rows, source freshness and veteran-player details.
- Borrow Candidate C `Party Operations` for Chickenbro, task queue and novice next-action language.

Short name: `A-Cockpit + B-Ledger + C-Captain`.

## Why This Hybrid

| Requirement | Selected Source | Reason |
| --- | --- | --- |
| Preserve first-screen fast scanning | Candidate A | The user repeatedly called out lost quick information on the workbench. |
| Avoid fake conclusions and preserve proof | Candidate B | Evidence rows make blockers, checkedAt, coverage and source_reference visible. |
| Make Chickenbro first-class | Candidate C | Chat, task context and next-question prompts become surfaces, not leftover widgets. |
| Keep App feeling | Candidate A + C | Strong shell and operational flow avoid a plain list app. |
| Reduce over-decoration risk | Candidate B | Ledger rows constrain material use to evidence and state. |

## Surface Targets

### 1. News Home

Target: `Evidence Cockpit` with `Evidence Ledger` rows.

- First screen: compact intelligence header, source status strip, hero story only when a real article visual exists, six-channel dock, ranked feed preview.
- Scrolled screen: ranked feed becomes the dominant object: rank, real thumbnail or low-semantic fallback, channel, title, source/date, save affordance, source_reference state.
- Component owners: `AppShell`, `PageFrame`, `ChannelDock`, `RankedFeed`, `GameObjectIcon`, `MaterialImage`.
- Forbidden: fake read counts, fake hotness, fake official logo, imagegen story thumbnails that imply real article imagery.

### 2. News List And Detail

Target: ledger-first reading flow.

- List: channel filter, source freshness, loading/empty/source_reference rows.
- Detail: title, original title/source, date, content blocks, source proof, related action.
- Component owners: `PageFrame`, `WowPanel`, `EvidenceLedger`, `ActionButton`, `RankedFeed`.
- Forbidden: LLM commentary replacing source translation, hidden source state, manual refresh controls on user-facing pages.

### 3. Builds Tab

Target: `Evidence Cockpit` main entry plus compact legacy workflow.

- First screen: current spec console, workbench entry as primary route, account/template strip, four old entries downranked but reachable.
- Switchers: class/spec/hero/scenario use compact controls, never large card grids.
- Component owners: `AppShell`, `PageFrame`, `WowPanel`, `GameObjectIcon`, `StatusVisual`, `ActionButton`, `ModuleCard`.
- Forbidden: deleting old talent/gear/SimC/task entrances, hiding template counts, decorative class/spec icons not backed by source.

### 4. Current Spec Workbench

Target: A structure, B evidence, C next-action language.

- First screen: identity cockpit, readiness verdict, blocker action, four-module status dock, evidence summary visible below.
- States: `ready_to_simulate`, `blocked`, `partial`, `stale`, `source_reference`, `unknown`.
- Component owners: `PageFrame`, `WowPanel`, `StatusVisual`, `ActionButton`, `ModuleCard`, `EvidenceLedger`, `GameObjectIcon`, `MaterialImage`.
- Forbidden: DPS, comprehensive score, S/A grade, upgrade priority, split shield/glyph state visuals, page-private status geometry.

### 5. Talent Simulator

Target: preserve real tree, wrap it in system shell.

- Keep the existing talent tree interaction and verified import/apply/save logic.
- Add workbench context strip, source/coverage summary, blocker row and return-to-workbench action.
- Component owners: `PageFrame`, `WowPanel`, `GameObjectIcon`, `EvidenceLedger`, `ActionButton`, `StatusVisual`.
- Forbidden: imagegen talent icons, fake frost-spec icon, decorative tree nodes that do not map to real selected nodes.

### 6. Gear Simulator / Detail

Target: equipment readiness checklist plus real item picker.

- First screen: 16-slot status, missing-slot group, catalog/source state, selected item/variant/enchant/socket entry.
- Detail sheets keep real item icon/name/source and safe fallback.
- Component owners: `PageFrame`, `GameObjectIcon`, `StatusVisual`, `EvidenceLedger`, `ActionButton`, `ModuleCard`.
- Forbidden: item artwork from imagegen, implied BiS, unverified slot priority, generic fake equipment visuals.

### 7. SimC

Target: handoff verification cockpit.

- From workbench: carry class/spec/hero/scenario context.
- Page body: template pair summary, missing input gate, scenario/buff controls, confirm summary, task lock.
- Component owners: `PageFrame`, `WowPanel`, `StatusVisual`, `ActionButton`, `EvidenceLedger`, `ModuleCard`.
- Forbidden: running or displaying result in workbench, fake DPS preview, submitting without explicit ready gate.

### 8. Chickenbro

Target: first-class `ChatShell` with evidence language.

- Entry modes: direct tab entry and workbench-context entry.
- States: empty, generating, completed reply, failed/fallback reply, evidence explanation, topic drawer, new topic, input focus, long-message scroll.
- Reply shape: short answer, evidence rows in user language, next-question suggestions. Raw `answerSource`, `confidence`, `job.status`, SimC profile and logs are never shown directly.
- Component owners: `ChatShell`, `PageFrame`, `StatusVisual`, `EvidenceLedger`, `ActionButton`.
- Forbidden: treating Chickenbro as old chat shell, hidden evidence source, freeform unsupported scoring, raw backend fields in visible text.

### 9. Tasks

Target: mission history with evidence status.

- List: task status, scenario, createdAt/finishedAt, source/result state, retry/continue action.
- Detail: deterministic report, allowedNumbers boundary, SimC status, evidence state and back links to workbench/SimC/Chickenbro.
- Component owners: `PageFrame`, `ModuleCard`, `StatusVisual`, `EvidenceLedger`, `ActionButton`.
- Forbidden: task status color drift, task rows that look final when still queued/running/failed.

### 10. Profile / My Templates

Target: personal vault that mirrors workbench template state.

- First screen: user identity, local/remote boundary, template counts, recent talent/gear templates, sync/delete actions.
- Template entry points jump back to talent/gear/SimC/workbench where appropriate.
- Component owners: `PageFrame`, `ModuleCard`, `GameObjectIcon`, `EvidenceLedger`, `ActionButton`, `StatusVisual`.
- Forbidden: mixing guest/formal owner state, hiding sync boundary, destructive delete without clear action state.

## Foundation Component Ownership

Detailed draft contracts live in [Foundation Component Contracts](2026-07-07-wow-ui-system-foundation-component-contracts.md). The table below is the target-lock summary.

| Component | Owner Contract |
| --- | --- |
| `AppShell` | Overall app background, tab-safe content floor, no fake system chrome. |
| `PageFrame` | Page gutters, safe-area, scroll padding, title slot and route-level spacing. |
| `WowPanel` | Bordered material panels with one radius/spacing contract. |
| `MaterialImage` | Low-semantic material placement, opacity, fit, quarantine boundary. |
| `GameObjectIcon` | Real object icon, source fallback, missing/fallback state. |
| `StatusVisual` | `blocked/partial/ready/stale/source_reference/unknown` base + glyph + text contract. |
| `ActionButton` | CTA geometry, disabled/loading/pressed states, no wrapping labels. |
| `ModuleCard` | Talent/gear/SimC/Chickenbro/task/template compact status modules. |
| `ChannelDock` | News channels, icon slot, selected state, count/fallback boundary. |
| `RankedFeed` | News ranked rows with rank, thumbnail, source and save slot. |
| `EvidenceLedger` | Coverage, checkedAt, source_reference, blockers and explanation rows. |
| `ChatShell` | Chat page layout, message list, evidence drawer, topic drawer, input and keyboard avoidance. |

Pages may compose these components but may not restyle component internals for local layout fixes.

## Material And Asset Boundary

Production material classes:

- `panel`
- `border`
- `texture`
- `socket`
- `state-base`
- `state-atomic`
- `decorative`

Reference/quarantine classes:

- Whole-page target images.
- Design boards.
- Images with visible text.
- Images with fact-bearing icons, fake logos, fake item art, fake class/spec/talent/gear/source objects.
- Any generated state image that combines status base and glyph without a component-owned layout contract.

Real object source map required before implementation:

- Class/spec/hero icons.
- Talent node/spell icons.
- Equipment/item icons.
- News/source icons and official/source labels.
- Dungeon/raid/affix icons if surfaced.

## Route Smoke Proposal

Detailed draft coverage lives in [Route Smoke And Runtime Verification Plan](2026-07-07-wow-ui-system-route-smoke-plan.md). The table below is the target-lock summary.

| Surface | Smoke Scenarios |
| --- | --- |
| News | tab enter, channel switch, scrolled feed, open detail, back, source_reference row. |
| Builds | tab enter, class/spec/hero switch, workbench entry, old four entries reachable. |
| Workbench | five states, scenario switch, evidence expand/collapse, jump to talent/gear/SimC/Chickenbro. |
| Talent | load, import, apply, save, empty/source_reference, return workbench. |
| Gear | load, missing slot, item select, variant/enchant/socket, save, return workbench. |
| SimC | from workbench, blocked missing templates, ready submit gate, task created, task detail. |
| Chickenbro | direct tab entry, context entry, empty, generating, done, failed, evidence, drawer, new topic, input focus, long scroll. |
| Tasks | empty/list, detail, retry/refresh, back to SimC/workbench. |
| Profile | guest/formal boundary, local template list, remote sync boundary, delete, template jump. |

## Target Lock Checklist

Before this proposal can become `target_locked`, evidence must include:

- User confirmation of this hybrid or a written modification.
- A target visual set for news, builds, workbench and Chickenbro at minimum.
- Surface notes for talent, gear, SimC, tasks and profile.
- Component decomposition accepted for all owners above.
- Asset manifest draft accepted or revised into a production-ready manifest with production, quarantine and source-map sections.
- Route smoke checklist accepted.

After target lock, implementation still requires a separate implementation permit. No page WXML/WXSS edits are allowed from this proposal alone.
