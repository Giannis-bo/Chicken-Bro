# WOW 小程序 UI 系统 Asset Manifest Draft

Status: `asset_manifest_draft`

This document is a material and real-asset boundary draft for the WOW mini-program UI system rebuild. It is not `target_locked`, not `runtime_verified`, and not an implementation permit.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Phase 1/2 Inventory](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md)
- [Target Lock Proposal](2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Foundation Component Contracts](2026-07-07-wow-ui-system-foundation-component-contracts.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-asset-manifest-draft/manifest.json`

## Purpose

The previous passes mixed several asset roles: whole-page visual targets, generated panel materials, generated product glyphs, fallback thumbnails, real WoW object icons, and status symbols. This caused page-level patching, fake object risk, broken state visuals, and material that competed with content.

This draft separates those roles before any new page implementation:

- Imagegen output may become low-semantic material only after manifest review.
- Real WoW objects must come from verified source maps, not generated images.
- State visuals must be owned by `StatusVisual`, including base, glyph, center point, size and transparent boundary.
- Page WXML/WXSS must not reference new material until a later implementation permit names the component owner, asset id and allowed surface.

## Allowed Production Material Classes

These classes may become production material only after component precheck and implementation permit.

| Class | Allowed Owner | Allowed Use | Forbidden Use |
| --- | --- | --- | --- |
| `panel` | `WowPanel`, `PageFrame` | Low-semantic panel surface, inner well, section backing. | Text, source labels, fake data rows, true object art. |
| `border` | `WowPanel`, `PageFrame`, `ActionButton` | Edge trim, corner detail, button frame. | Fake system chrome, fake WeChat capsule, fake source logo. |
| `texture` | `MaterialImage`, `WowPanel` | Quiet background texture behind real content. | Readability competition, page-level full bleed replacing layout. |
| `socket` | `GameObjectIcon`, `ModuleCard`, `ChannelDock` | Empty object/icon holder with real icon or text fallback above it. | Generated class/spec/talent/item/source icon. |
| `state-base` | `StatusVisual` | Neutral state body such as shield, seal, badge base. | Any implied readiness, score, blocker, or severity by itself. |
| `state-atomic` | `StatusVisual` | Single complete generated state emblem when base and glyph cannot be safely layered. | Splitting into page-owned base and glyph. |
| `decorative` | `AppShell`, `PageFrame`, `WowPanel` | Low-opacity ornament, divider, glint. | Content slot, status, factual icon, route affordance. |

## Quarantine Classes

These asset classes must not appear in production WXML/WXSS/JS.

| Class | Examples | Reason |
| --- | --- | --- |
| `whole-page target image` | Full target screens, contact sheets, design boards. | Reference only; cannot adapt to real safe-area, tabBar or content. |
| `image with visible text` | Generated titles, labels, buttons, numbers. | Text must come from data/view model and scale responsively. |
| `fact-bearing generated icon` | Generated class, spec, talent, item, source logo, dungeon, raid, affix. | Real objects require verified source map. |
| `fake chrome` | Clock, battery, Wi-Fi, phone frame, WeChat capsule. | Mini-program must use real host chrome. |
| `pass-named asset pending recut` | `*pass36*`, `pass37*`, pass-specific fallback thumbnails. | Old pass evidence cannot become new system production by filename inertia. |
| `legacy surface material` | `assets/generated/ui-redesign/20260701/*`, `ui-v2-restoration/*`, `ui-v3-1/*`. | May be reference or migration debt only until reclassified. |
| `reference source image` | `*source.png`, `*reference.png`, `*atlas.png`, design boards. | Source/slicing input, not runtime render target. |

## Existing Asset Policy

| Path | Current Policy | Notes |
| --- | --- | --- |
| `assets/generated/ui-v3/20260701/*-material-mobile.jpg` | `candidate_low_semantic_input` | Good input because existing manifest says no text, logo or real WoW object. Must still be re-cut into component-owned slices before production. |
| `assets/generated/ui-v2-1-slices/20260703/panel_*_v2.png` | `candidate_low_semantic_input` | Can inform panel/socket/button contracts, but pass line cannot auto-authorize production use. |
| `assets/generated/ui-v2-1-slices/20260703/socket_*_v2.png` | `candidate_socket_input` | Only `GameObjectIcon`/`ModuleCard` may own after precheck. |
| `assets/generated/ui-v2-1-slices/20260705/verdict_status_*` | `candidate_status_input` | Must be re-owned by `StatusVisual`; no page may place base and glyph independently. |
| `assets/generated/ui-v2-1-slices/20260703/news_tab_icon_*pass36*` | `quarantine_pass_named_product_glyph` | Pass-named generated glyphs may not enter new production manifest without rename, review and component precheck. |
| `assets/generated/ui-v2-1-slices/20260703/news_thumb_fallback_*pass36*` | `quarantine_pass_named_fallback` | Fallback thumbnails need separate policy because they can be mistaken for article evidence. |
| `assets/generated/ui-redesign/20260701/*` | `quarantine_legacy_surface_material` | Existing simulator/SimC/Chickenbro/task/profile references are migration debt, not new target evidence. |
| `assets/generated/ui-v2-restoration/**` | `quarantine_reference_material` | Earlier target-restoration inputs only. |
| `assets/generated/ui-v3-1/**` | `quarantine_rejected_direction` | Rejected heavy shell direction. |

## Real WoW Source Map

`GameObjectIcon` is the only component allowed to render real WoW object icons. It may use these source classes:

| Entity Type | Allowed Sources | Required Fields | Fallback |
| --- | --- | --- | --- |
| `class` | `/api/builds/home`, `server/builds/home-payload.js`, verified official icon-name mapping. | `entityType`, `entityId`, `iconUrl`, `source`, `status`. | 1-2 Chinese/English characters. |
| `spec` | `/api/builds/home`, WebSim/Battle.net read model, verified official icon-name mapping. | `entityType`, `entityId`, `iconUrl`, `semanticTags`. | Spec initials / localized first character. |
| `hero` | WebSim talents payload or verified mapping. | `entityType`, `entityId`, `iconUrl`, `status`. | Hero label fallback. |
| `talent` | `/api/websim/talents nodes[].gameAsset.iconUrl`. | `gameAsset.iconUrl`, `source`, `status`, `fallbackText`. | `天`. |
| `spell` | `server/websim_payload.py` spell detail and asset registry. | `entityType=spell`, `iconUrl`, `source`, `status`. | `法`. |
| `item` | `/api/websim/gear equippedSet/replacementCandidates[].gameAsset.iconUrl`, Battle.net item metadata. | `entityType=item`, item id, `iconUrl`, `metadataStatus`. | Slot label. |
| `source` | Source registry / approved product IA mapping. | Source id/name/status. | Text badge, not generated logo. |
| `dungeon` | Season data cache / verified official icon-name mapping. | Dungeon id/name/icon status. | Dungeon initials. |
| `raid` | Season data cache / verified official icon-name mapping. | Raid id/name/icon status. | Raid initials. |
| `affix` | Season data cache / verified official icon-name mapping. | Affix id/name/icon status. | Affix initials. |

Source classes allowed by policy:

- `api`: runtime payload has `gameAsset.iconUrl` and status metadata.
- `battlenet`: Battle.net Game Data or render CDN provenance.
- `websim`: WebSim read model has object id and icon.
- `repo_verified`: checked-in mapping or asset registry with review evidence.
- `user_provided`: user-supplied asset with explicit approval and source note.

Source classes not allowed:

- `imagegen`
- `target_screenshot_crop`
- `random_cdn_without_mapping`
- `generated_product_glyph`
- `page_private_fallback_art`

## Component Ownership Rules

| Component | Owns | Must Not Own |
| --- | --- | --- |
| `MaterialImage` | Low-semantic material fit, opacity, clipping, loading/error fallback. | Real object icons, status glyphs, factual labels. |
| `GameObjectIcon` | Real icon, socket fit, text fallback, source/status metadata. | Generated object-like art or page private icon fallback. |
| `StatusVisual` | State base/glyph/atomic art, center point, size, transparent bounds. | DPS, score, S/A grade, readiness conclusion. |
| `WowPanel` | Panel material, border, content padding slots. | Page-specific status badges or buttons. |
| `ActionButton` | Button frame/material, min height, disabled/loading state. | Page-specific compressed CTA geometry. |
| `ChatShell` | Chickenbro evidence chips, message surfaces, input safe-area. | Raw backend field names or page-owned chat bubble geometry. |

## Fit And Size Strategy

- `panel`: stretch by 9-slice or fixed aspect wrapper; never distort content slots.
- `border`: `scaleToFill` only when the source is explicitly border-only; otherwise use component-owned 9-slice.
- `texture`: `aspectFill` or CSS background cover at low opacity; content contrast must pass precheck.
- `socket`: `contain`; real icons render above socket with defined inset and fallback text.
- `state-base`: `contain`; glyph center is component data, not page positioning.
- `state-atomic`: `contain`; no separate glyph overlay unless owned by `StatusVisual`.
- `decorative`: low opacity and non-interactive; must not affect layout rects.

Draft budgets:

- Mobile material: target `<= 350KB` per asset.
- Small socket/state atom: target `<= 96KB` per asset.
- Real icon cache: source-owned and optimized separately; no package-wide budget is accepted until measured.
- Package budget status: `packageBudgetPending=true`.

## Promotion Gates

An asset can move from draft to production only when all are true:

1. It is listed in the UI system asset manifest with class, owner, path, file size, fit mode and allowed surfaces.
2. It contains no visible text, fake data, fake chrome, source logo, or real WoW object unless it is a verified real source asset.
3. It has component fixture crops for compact, standard and large viewports.
4. It passes text-overlap and slot-fit checks in the component harness.
5. It is referenced by an implementation permit naming owner component and page surface.
6. It is verified in real mini-program screenshot evidence before any `runtime_verified` claim.

## Forbidden Promotion

This draft cannot be promoted to any of these statuses by itself:

- `target_locked`
- `component_precheck`
- `implementation_permit`
- `runtime_verified`
- `final_accepted`

## Next Required Evidence

- User confirmation or revision of the target lock proposal.
- Component harness that renders `MaterialImage`, `GameObjectIcon` and `StatusVisual` fixtures.
- Re-cut material manifest with exact files, dimensions, sizes and owners.
- Static scan that production WXML/WXSS/JS does not use quarantine assets.
- Route smoke plan that ties assets to real surfaces without touching DevTools high-disturbance actions.
