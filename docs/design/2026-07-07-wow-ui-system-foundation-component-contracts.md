# WOW 小程序 UI 系统重建 Foundation Component Contracts

Status: `component_contract_draft`
Created: 2026-07-07

Linked evidence:

- [UI 系统重建 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Phase 1/2 Inventory](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md)
- [Target Lock Proposal](2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Asset Manifest Draft](2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Route Smoke And Runtime Verification Plan](2026-07-07-wow-ui-system-route-smoke-plan.md)
- [Foundation Harness Draft](2026-07-07-wow-ui-system-foundation-harness-draft.md)
- [Production Component Precheck](2026-07-07-wow-ui-system-production-component-precheck.md)
- [Browser Component Precheck](2026-07-07-wow-ui-system-browser-component-precheck.md)
- [Surface Owner Contracts](2026-07-07-wow-ui-system-surface-owner-contracts.md)

This document is a component decomposition draft for the proposed `A-Cockpit + B-Ledger + C-Captain` direction. It is not `target_locked`, not `runtime_verified`, and not an implementation permit.

## Contract Rules

- Pages compose components, bind data and handle route events only.
- Pages may pass props, slots and event handlers; pages may not patch component internals, geometry, status glyphs, material fit, gutters, button shape, chat bubbles or evidence rows.
- Component geometry must be validated in component harnesses before page integration; source-level component precheck and browser rect measurement must also be clean before a page implementation permit.
- Every component must support compact, standard and large viewport contracts before it can be used by a core surface.
- Real object icons must flow through `GameObjectIcon`; low-semantic generated material must flow through `MaterialImage`.
- `StatusVisual` owns every state badge, status emblem and glyph layout. No page may split base and glyph.
- `ChatShell` owns Chickenbro layout, input safe-area and long-message behavior.
- Native WeChat `tabBar` owns fixed bottom tab icon slots through `app.json` `iconPath` and `selectedIconPath`; pages and generated material may not fake a fixed bottom tab.
- Legacy pass aliases and legacy `status-badge` references may remain only as historical evidence; foundation components may not depend on them.

## Shared State Vocabulary

| State | Meaning | Visual Owner |
| --- | --- | --- |
| `ready_to_simulate` | Required evidence is complete enough to enter SimC submit flow. | `StatusVisual` |
| `blocked` | Missing required evidence or input prevents the next action. | `StatusVisual`, `EvidenceLedger` |
| `partial` | Evidence exists but is incomplete or has coverage gaps. | `StatusVisual`, `EvidenceLedger` |
| `stale` | Evidence exists but freshness is outside acceptable window. | `StatusVisual`, `EvidenceLedger` |
| `source_reference` | Reference/source-only information, not a strong local conclusion. | `StatusVisual`, `EvidenceLedger` |
| `unknown` | Loading, absent, or not yet resolved. | `StatusVisual` |
| `loading` | UI is waiting for data or async action. | owning component |
| `empty` | Valid state with no local user data. | owning component |
| `error` | Recoverable load or action failure. | owning component |

## Components

### AppShell

Role: app-level background, tab-safe content floor and global material mood.

Inputs:

- `surface`: `news | builds | workbench | talent | gear | simc | chickenbro | tasks | profile`
- `theme`: locked dark Azeroth theme
- `tabSafe`: whether bottom tab padding is required

Owns:

- App background color and global low-opacity decorative texture.
- Tab bar avoidance and bottom content floor.
- No fake system status bar, time, Wi-Fi, battery or capsule.

Forbidden page overrides:

- Rendering fake WeChat chrome.
- Rendering fake fixed bottom tab icons or labels.
- Adding page-private full-screen background materials.
- Adjusting bottom safe-area per page.

Native tabBar boundary:

- `app.json` owns the fixed bottom tab list, label, `iconPath` and `selectedIconPath`.
- Tab icons must be local runtime assets under `assets/tabbar/`.
- Tab visuals must not be implemented as page WXML, generated full-page material or a floating in-page dock.

### PageFrame

Role: route-level spacing, scroll padding, content width and section rhythm.

Inputs:

- `title`
- `subtitle`
- `routeKind`: `tab | stack | sheet`
- `density`: `compact | standard | ledger`
- `safeAreaTop`
- `safeAreaBottom`

Owns:

- Horizontal gutters.
- Page title slot.
- First-section top spacing.
- Scroll and keyboard avoidance baseline.

Forbidden page overrides:

- Ad hoc page gutters.
- Section margins that break the global rhythm.
- Page-level fixes for overflow caused by children.

### WowPanel

Role: reusable dark-metal panel with controlled border, radius and inset layers.

Inputs:

- `variant`: `plain | cockpit | ledger | danger | success | source`
- `density`: `compact | standard`
- `interactive`: boolean

Owns:

- Radius, border, inner stroke and material inset.
- Panel min/max padding.
- Focus and pressed state if interactive.

Forbidden page overrides:

- Nested card-like panels inside panels unless the child is a repeated row.
- One-off borders or corner ornaments in page WXSS.
- Material images placed directly behind panel content.

### MaterialImage

Role: low-semantic imagegen/material rendering with fit and quarantine boundary.

Inputs:

- `assetId`
- `assetClass`: `panel | border | texture | socket | state-base | state-atomic | decorative`
- `fit`: `cover | contain | stretch9`
- `opacity`
- `quarantine`: boolean

Owns:

- Image fit, opacity, clipping and pointer behavior.
- Rejection of reference-only and quarantine assets in production mode.

Forbidden page overrides:

- Direct `<image>` references to generated full-page targets.
- Imagegen output inside real object slots.
- Generated images with visible facts, text, logos, class icons, item art or source marks.

### GameObjectIcon

Role: real WoW object icon and fallback rendering.

Inputs:

- `entityType`: `class | spec | hero | talent | spell | item | dungeon | raid | affix | source`
- `entityId`
- `iconUrl`
- `source`: `api | battlenet | websim | repo_verified | user_provided`
- `fallbackLabel`
- `size`: `sm | md | lg | xl`
- `state`: shared state vocabulary

Owns:

- Icon socket, crop, fallback label, missing state and source marker.
- Icon aspect ratio and safe clipping.

Forbidden page overrides:

- Decorative generated object icons.
- Hardcoded fake frost/spec/talent/item icons.
- Page-private circle/hex sockets.

### StatusVisual

Role: all status badges, emblems, labels and glyph composition.

Inputs:

- `state`: shared state vocabulary
- `label`
- `tone`: `compact | badge | emblem | slab`
- `glyph`: `check | exclamation | info | clock | lock | question`
- `mode`: `layered | atomic`

Owns:

- State color, glyph center point, transparent boundary, base/glyph layering and text placement.
- Ready/blocked/partial/stale/source_reference/unknown consistency across pages.

Forbidden page overrides:

- Separate shield base and exclamation glyph outside component.
- Page-level CSS to reposition state glyphs.
- New color meanings for existing states.

### ActionButton

Role: primary, secondary and contextual actions with stable geometry.

Inputs:

- `variant`: `primary | secondary | ghost | danger | inline`
- `label`
- `icon`
- `state`: `default | pressed | loading | disabled`
- `routeAction`

Owns:

- Height, padding, icon position, label single-line fit, loading state and disabled affordance.
- Press feedback without layout shift.

Forbidden page overrides:

- Page-private gold button images.
- Text wrapping inside CTA.
- Buttons compressed by parent flex rules.

### ModuleCard

Role: compact status module for workflow units.

Inputs:

- `module`: `talent | gear | simc | chickenbro | task | template | source`
- `title`
- `metric`
- `state`
- `actionLabel`
- `icon`

Owns:

- Module layout, icon socket, status chip, metric placement and action affordance.
- Grid behavior in compact/standard/large viewports.

Forbidden page overrides:

- Four workflow cards rebuilt in each page.
- Vertical content stacks with no metric/action hierarchy.
- Local status labels that contradict shared state.

### ChannelDock

Role: news channel filter and channel status dock.

Inputs:

- `channels[]`: id, label, state, icon, count, disabled
- `selectedId`
- `layout`: `six-dock | compact-rail`

Owns:

- Equal channel sizing, selected state, icon socket and label fit.
- Count visibility only when payload provides real count.

Forbidden page overrides:

- Fake channel counts.
- Text-only replacement when icon slots are expected.
- Decorative dots that do not convey state.

### RankedFeed

Role: ranked/news feed rows with source boundary.

Inputs:

- `items[]`: rank, title, channel, source, date, thumbnail, state, isOpenable, saved
- `density`: `hero | list | compact`

Owns:

- Rank column, thumbnail fit, fallback thumbnail, title wrapping, metadata and save slot.
- Source_reference and blocked row presentation.

Forbidden page overrides:

- Empty thumbnail boxes.
- Fake read counts or heat metrics.
- Row-specific layout patches for long titles.

### EvidenceLedger

Role: coverage, blockers, checkedAt, source and explanation rows.

Inputs:

- `rows[]`: id, label, value, state, source, checkedAt, blocker, action
- `mode`: `summary | expanded | chat`
- `audience`: `novice | advanced`

Owns:

- Row geometry, state chip, source badge, timestamp, action affordance and expand/collapse grouping.
- Novice summary and advanced expansion.

Forbidden page overrides:

- Raw backend fields in visible text.
- Evidence hidden behind decorative cards.
- Mixing blocker, source_reference and verified colors.

### ChatShell

Role: Chickenbro page shell and conversation system.

Inputs:

- `entryMode`: `tab | workbench_context`
- `contextSummary`
- `messages[]`: role, status, content, evidenceRows, nextQuestions
- `topics[]`
- `inputState`: `idle | focused | disabled | submitting`
- `safeAreaBottom`

Owns:

- Context header, message list, evidence drawer, topic drawer, input bar, keyboard avoidance and long-message scroll.
- Empty, generating, completed, failed/fallback and new-topic states.

Forbidden page overrides:

- Fixed input bars outside `ChatShell`.
- Chat input outside ChatShell.
- Raw `answerSource`, `confidence`, `job.status`, SimC profile or raw logs in visible text.
- Message bubbles styled per page instead of shared chat contract.

## Fixture Matrix

Every owner must be tested against:

| Dimension | Required Cases |
| --- | --- |
| Viewport | compact, standard, large |
| Content | short, long Chinese text, long English token, missing icon/image |
| State | ready_to_simulate, blocked, partial, stale, source_reference, unknown, loading, empty, error |
| Interaction | pressed, disabled, loading, expanded, collapsed, focused |
| Evidence | no rows, one blocker, multiple blockers, checkedAt visible, source_reference visible |

## Pre-Integration Gates

Before any page implementation permit:

- Component contract must be accepted or explicitly modified.
- Surface-specific owner contracts must exist for complex geometry before activating a surface permit.
- Component harness must render all required owners and states; the current static draft is recorded in [Foundation Harness Draft](2026-07-07-wow-ui-system-foundation-harness-draft.md) and still needs production-code precheck.
- Component crops/contact sheet must exist.
- Static scan must prove no core page reimplements panel/status/button/module/evidence/chat internals.
- Asset manifest draft must be accepted or revised, and the resulting manifest must separate production, quarantine and real source-map assets.
- Route smoke plan must be ready for the surface being implemented, including browser precheck, runtime capture, route actions and DevTools action ledger.

## Status Boundary

This contract is `component_contract_draft`. It cannot be used to claim:

- `target_locked`
- `component_precheck`
- `runtime_verified`
- `final_accepted`
- Implementation permission for page WXML/WXSS
