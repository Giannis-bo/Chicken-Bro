# WOW UI System Surface Owner Contracts

Status: `surface_owner_contract_draft`
Created: 2026-07-07

This document defines the missing surface-specific owners required by the WOW mini-program UI system rebuild. It is not `target_locked`, not `component_precheck`, not an active implementation permit, and does not authorize page WXML/WXSS edits.

Design read: dense native WeChat mini-program product UI for WoW players, with an evidence cockpit language, high visual density, restrained motion and a dark Azeroth component system.

Dial settings for this contract pass:

- `DESIGN_VARIANCE: 6`
- `MOTION_INTENSITY: 3`
- `VISUAL_DENSITY: 9`

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Foundation Component Contracts](2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Implementation Permit Coverage Matrix](2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
- [Target Lock Proposal](2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Asset Manifest Draft](2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Route Smoke And Runtime Verification Plan](2026-07-07-wow-ui-system-route-smoke-plan.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-surface-owner-contracts/manifest.json`

## Why This Exists

Foundation owners define the shared primitives: `PageFrame`, `WowPanel`, `StatusVisual`, `ActionButton`, `GameObjectIcon`, `MaterialImage`, `EvidenceLedger`, `ChatShell` and related base components.

They are not enough for the hard surfaces. The UI failures called out in the current work happened where page files owned complex geometry directly:

- article rows and reader body blocks;
- talent tree node/link geometry;
- 16-slot equipment boards and candidate sheets;
- task rails and result reports;
- coach conversation route shell, topic drawer and evidence explanation;
- profile identity and template libraries.

This document assigns those geometries to surface owners. Pages may compose these owners, pass read-model props and handle route events. Pages may not patch owner internals, add private gutters, split status base/glyph layers, compress buttons, reimplement rows, or place generated material behind content.

## Global Contract Rules

- Surface owners sit above foundation owners and below pages.
- Surface owners own layout geometry, density, overflow behavior, touch targets, long text behavior and state placement for their domain.
- Surface owners must consume `PageFrame`, `WowPanel`, `StatusVisual`, `ActionButton`, `GameObjectIcon`, `MaterialImage`, `ModuleCard`, `RankedFeed`, `EvidenceLedger` or `ChatShell` instead of rebuilding those primitives.
- Real WoW object imagery must flow through `GameObjectIcon`.
- Low-semantic generated materials must flow through `MaterialImage`.
- Status base, glyph, label and state color must flow through `StatusVisual`.
- Buttons must flow through `ActionButton` and keep stable height, single-line labels and disabled/loading states.
- Evidence rows, blockers, source references and checkedAt must flow through `EvidenceLedger`.
- Pages own data fetching, route params, route actions and analytics only.
- Every owner must support compact, standard and large viewports before page integration.
- Every owner must expose loading, empty, error and long-text fixtures before active implementation.
- Generated images may not contain factual text, WoW class/spec/talent/item art, source logos, official badges, task numbers, DPS values, verification labels or publication dates.

## Owner Inventory

| Owner | Primary Surface | Replaces Page-Private Geometry |
| --- | --- | --- |
| `NewsHomeSurface` | `news_home` | first-viewport news cockpit, channel dock, focus feed, latest feed, news evidence |
| `ArticleListBoard` | `news_list_detail` list route | list header, query title/count, loading/empty/fallback slabs, article rows |
| `ArticleReader` | `news_list_detail` detail route | title stack, original/source/date, translated body blocks, source footer |
| `BuildsTabSurface` | `builds_tab` | current spec console, compact class/spec/hero switchers, workbench primary entry, old entry grid, entry evidence |
| `ChickenbroCoachSurface` | `chickenbro` tab and stack routes | coach header, workbench context, suggested prompts, answer evidence, topic drawer, retry/error slab |
| `TalentTreeCanvas` | `talent_simulator` | tree viewport, node/link geometry, choice node frame, rank and touch target placement |
| `GearLoadoutBoard` | `gear_detail` | 16-slot board, slot card size, icon sockets, enhancement/status badges |
| `GearConfigSheet` | `gear_detail` | source filters, candidate rows, variant/crafted selectors, enhancement groups, fixed sheet actions |
| `SimcSubmitSurface` | `simc` | submit readiness, profile context, module checks, action rail, SimC evidence |
| `TaskQueueBoard` | `tasks` list route | task list hero, queue/status rail, task cards, empty-state steps |
| `TaskResultReport` | `tasks` detail route | final result gate, context rows, stat rows, combat buff rows, localized failure rows |
| `ProfileIdentityPanel` | `profile_templates` | avatar socket, nickname draft, guest/formal status, save/sync state |
| `TemplateLibraryBoard` | `profile_templates` | talent/gear template modules, recent cards, meta chips, delete hooks, empty states |

## ArticleListBoard

Role: owns the news list reading path for channel and metric queries.

Inputs:

- `query`: `{ type, key, value }`
- `title`
- `count`
- `articles[]`: `id`, `channel`, `publishedAt`, `title`, `summary`, `sourceName`, `sourceUrl`, `thumbnail`, `state`
- `loading`
- `empty`
- `fromFallback`
- `requestError`
- `density`: `compact | standard`

Events:

- `openArticle(articleId)`

Uses:

- `PageFrame` for route spacing.
- `WowPanel` for list shell and fallback/empty slabs.
- `RankedFeed` for row geometry when ranked rows are shown.
- `EvidenceLedger` for fallback and source_reference explanation.
- `ActionButton` for row actions when needed.
- `MaterialImage` only for low-semantic row or panel material.

Owns:

- Header title/count alignment.
- Loading skeleton dimensions.
- Empty and fallback state layout.
- Article row height, thumbnail slot, metadata row, long-title line clamp and source URL wrapping.
- Row hit target and open action affordance.

Forbidden:

- Fake read counts, heat scores, rankings, source logos, official badges or generated article thumbnails.
- Hidden fallback or hidden request error.
- Page-private row paddings or thumbnail sockets.
- Manual refresh controls under this owner contract.

Required fixtures:

- `news_list_loading`
- `news_list_ready`
- `news_list_empty`
- `news_list_fallback`
- `news_list_incomplete_payload_fallback`
- `news_list_official_channel`
- `news_list_long_title`
- `news_list_long_source_url`

Measured invariants:

- No horizontal overflow on long Chinese or English source URLs.
- Header count never collides with title.
- Row action hit target remains at least 44px high.
- Fallback state is visible above the first row or in the empty slab.

## ArticleReader

Role: owns verified article detail rendering and source proof.

Inputs:

- `article`: `title`, `originalTitle`, `summary`, `channel`, `category`, `publishedAt`, `sourceName`, `sourceUrl`, `sourceBadges`, `metaChips`, `tagItems`, `bodyBlocksZh`
- `loading`
- `missingId`
- `notFound`
- `fromFallback`
- `requestError`
- `homeButton`

Events:

- `copySourceUrl(sourceUrl)`

Uses:

- `PageFrame` for stack route spacing and back/home area.
- `WowPanel` for reader shell and source footer.
- `EvidenceLedger` for source proof and fallback state.
- `ActionButton` for copy source.
- `StatusVisual` for verification/source_reference badges.

Owns:

- Title stack, original title, source/date row and tag chip wrapping.
- Body block rendering for paragraph, heading, list and quote.
- Source footer and copy-source action placement.
- Missing id, not found, loading and fallback states.

Forbidden:

- LLM commentary replacing source translation.
- Raw collector, translator, admin or backend payloads.
- Generated source logos, fake official badges or fake publication dates.
- Blank page on missing id or not-found.

Required fixtures:

- `news_detail_loading`
- `news_detail_ready`
- `news_detail_missing_id`
- `news_detail_not_found`
- `news_detail_fallback`
- `news_detail_original_title`
- `news_detail_source_badges`
- `news_detail_body_paragraph`
- `news_detail_body_heading`
- `news_detail_body_list`
- `news_detail_body_quote`
- `news_detail_long_title`
- `news_detail_long_source_url`
- `news_detail_copy_source`

Measured invariants:

- Body text has readable minimum size on compact viewport.
- Long URLs wrap inside the source footer.
- List and quote body blocks keep distinct spacing and do not look like decorative cards.
- Copy action cannot wrap or compress below the action height.

## BuildsTabSurface

Role: owns the职业专精 tab as the upstream entry to workbench, talent simulator, gear detail, SimC, tasks and Chickenbro.

Inputs:

- `state`
- `selectedClassLabel`
- `selectedSpecLabel`
- `selectedHeroLabel`
- `currentSpecTitle`
- `currentSpecDesc`
- `classOptions[]`
- `specOptions[]`
- `heroOptions[]`
- `overviewChips[]`
- `workbenchEntry`
- `workflowCards[]`
- `evidenceRows[]`
- `evidenceExpanded`

Events:

- `workbenchtap`
- `classchange`
- `specchange`
- `herochange`
- `entrytap`
- `evidencetoggle`
- `refresh`

Uses:

- `WowPanel` for console, workbench, workflow and evidence shells.
- `GameObjectIcon` for real class/spec icons or text fallback.
- `StatusVisual` for readiness and workbench state.
- `ActionButton` for workbench and refresh actions.
- `ModuleCard` for old entry cards and Chickenbro entry.
- `EvidenceLedger` for entry evidence and source-reference rows.
- `MaterialImage` only for low-semantic manifest material.

Owns:

- Current spec console geometry.
- Compact class/spec/hero switcher rows.
- Workbench primary entry without hiding old entry routes.
- Workflow grid for `talents`, `gear`, `simc`, `tasks` and optional `chickenbro`.
- Long-label handling and missing-icon fallback.

Forbidden:

- Page-private hero, workbench entry, card, status, icon socket, switcher or material geometry.
- Removing or hiding old `talents`, `gear`, `simc` or `tasks` entries.
- Imagegen class/spec/hero/talent/item/source icons.
- Strong claims such as DPS, comprehensive score, S/A grade, ranking or upgrade priority.
- Fake host chrome, time, battery, Wi-Fi or WeChat capsule.

Required fixtures:

- `builds_tab_ready`
- `builds_tab_loading`
- `builds_tab_source_reference`
- `builds_tab_blocked_workbench`
- `builds_tab_long_labels`
- `builds_tab_missing_icons`

Measured invariants:

- No horizontal overflow on compact / standard / large viewports.
- Old four entry keys `talents`, `gear`, `simc`, `tasks` remain visible in every fixture.
- Long class/spec/hero labels stay inside owner slots.
- Missing real icons show text fallback and do not use generated fake WoW objects.

## ChickenbroCoachSurface

Role: owns Chickenbro as a first-class coach conversation surface across smart-analysis tab and stack/workbench-context routes.

Inputs:

- `entryMode`: `tab | workbench_context`
- `title`
- `desc`
- `contextTitle`
- `contextMeta`
- `suggestedPrompts[]`
- `messages[]`: `messageId`, `role`, `content`, `status`, `statusText`
- `assistantPayload`: `answerSource`, `confidence`, `priorityActions[]`, `evidenceRefs[]`, `limitations[]`
- `job`: status snapshot
- `generationStatus`
- `generationStatusText`
- `requestError`
- `topicDrawerVisible`
- `sessionTitle`
- `inputValue`
- `loading`

Events:

- `send(value)`
- `inputchange(value)`
- `inputfocus`
- `inputblur`
- `newtopic`
- `opendrawer`
- `closedrawer`
- `suggestedprompt(index, value)`
- `retry`
- `evidencetoggle(expanded)`

Uses:

- `ChatShell` for message list, empty state, context strip, input safe-area and chat actions.
- `EvidenceLedger` for answer evidence, limitations and next-action rows.
- `StatusVisual` for generating, failed, fallback and source-reference states.
- `ActionButton` for topic, suggested prompt, retry and drawer close actions.
- `MaterialImage` only for low-semantic material under manifest control.

Owns:

- Coach header and state placement.
- Workbench context summary and suggested prompt row.
- Mapping of backend-facing evidence vocabulary into player-facing labels.
- Evidence summary slab and request-error retry slab.
- Topic drawer geometry, close action and long-title behavior.
- Entry consistency between `/pages/simulator/simulator` and `/pages/simulator/chickenbro`.

Forbidden:

- Page-private chat bubble, evidence row, status badge, input bar, topic drawer or material geometry.
- Visible raw `answerSource`, `confidence` or `job.status`.
- Raw SimC profile, raw WCL log payload, token, openid, user id, database id or secret-like values.
- Unsupported DPS, ranking, percentile, S/A grade, comprehensive score or upgrade-priority claims.
- Generated portraits, source logos, class/spec/talent/item icons or whole-page target images.
- Fake phone chrome, time, battery, Wi-Fi or WeChat capsule.

Required fixtures:

- `chickenbro_tab_empty`
- `chickenbro_workbench_context`
- `chickenbro_generating`
- `chickenbro_done_with_evidence`
- `chickenbro_failed`
- `chickenbro_topic_drawer`
- `chickenbro_input_focus`
- `chickenbro_long_message_scroll`

Measured invariants:

- Input bar stays inside `ChatShell` and respects safe-area values.
- Long assistant answers wrap inside the message scroll lane without horizontal overflow.
- Topic drawer stays inside the owner bounds and does not cover the input contract unexpectedly.
- Evidence rows show user-language source and strength labels, not backend field names.
- Workbench context never requires raw profile data to render.

## TalentTreeCanvas

Role: owns WebSim talent tree layout, node/link geometry and touch behavior.

Inputs:

- `tree`: normalized class/spec/hero tree nodes and links
- `selectedNodes`
- `grantedNodes`
- `choiceState`
- `pointBudget`
- `nodeStates`: selectable, selected, locked, granted, blocked
- `viewport`: compact, standard, large
- `panZoomState`

Events:

- `toggleNode(nodeId)`
- `selectChoice(nodeId, choiceId)`
- `focusNode(nodeId)`

Uses:

- `GameObjectIcon` for real talent/spell icons.
- `StatusVisual` only for non-node state labels outside the node frame.
- `MaterialImage` for low-semantic node/socket materials.
- `ActionButton` for fixed actions outside the canvas.
- `EvidenceLedger` for blockers outside the canvas.

Owns:

- Tree viewport dimensions.
- Node coordinates, link lines, granted root rendering and locked path opacity.
- Node shape semantics: passive/circle, active/rounded rectangle, choice/octagon or accepted local equivalent.
- Rank badge placement, choice switch affordance and touch target size.
- Pan/scroll bounds and compact viewport collapse.

Forbidden:

- Page-private node absolute positions.
- Generated talent icons.
- Fake save-readiness, DPS, grade or upgrade labels.
- Choice node arrows or rank badges positioned outside owner bounds.

Required fixtures:

- `talent_tree_loading`
- `talent_tree_ready`
- `talent_tree_missing_icon`
- `talent_tree_locked_path`
- `talent_tree_choice_node`
- `talent_tree_long_tooltip`
- `talent_tree_cross_spec_template`
- `talent_save_blocked`
- `talent_save_ready`

Measured invariants:

- Node icon and frame stay centered across compact, standard and large viewports.
- Links remain under nodes and never cover labels/actions.
- Choice node affordance fits inside the node touch target.
- Fixed action area never overlaps the tree on compact devices.

## GearLoadoutBoard

Role: owns the 16-slot equipment layout and readiness perception.

Inputs:

- `slots[]`: canonical slot id, item, iconUrl, slotState, simcReady, enhancementSummary, blockers
- `selectedSlot`
- `readiness`: ready_to_simulate, blocked, partial, stale, source_reference, unknown
- `statSummary`
- `density`: compact, standard

Events:

- `selectSlot(slotId)`
- `openConfig(slotId)`

Uses:

- `GameObjectIcon` for item icons.
- `StatusVisual` for slot state and board readiness.
- `ModuleCard` only for compact board summaries when needed.
- `EvidenceLedger` for blockers outside the board.
- `MaterialImage` for slot/socket materials only.

Owns:

- 16-slot grid or compact grouped layout.
- Slot card size, icon socket, slot label, item title, enhancement badges and status placement.
- Missing-slot and selected-slot states.
- Readiness strip alignment above or below the board.

Forbidden:

- Page-private slot card CSS.
- Item icons from generated assets.
- Fake BiS, fake DPS, fake ranking, fake S/A grades or fake upgrade priority.
- Enhancement badges that overflow slot cards.

Required fixtures:

- `gear_slots_loading`
- `gear_slots_empty`
- `gear_slots_16_complete`
- `gear_slots_missing_16`
- `gear_slots_partial_variant`
- `gear_slots_crafted_selected`
- `gear_slots_enhancement_cap`
- `gear_slots_long_item_name`
- `gear_slots_missing_icon`

Measured invariants:

- 16 canonical slots remain scannable on compact viewport.
- Slot icon, label and status badge stay inside the measured card.
- Board action targets stay at least 44px high.
- Stat/readiness strip does not invent strong conclusions when blockers exist.

## GearConfigSheet

Role: owns item candidate, variant and enhancement selection.

Inputs:

- `slotId`
- `candidates[]`
- `sourceFilters[]`
- `variantTracks[]`
- `craftedStatOptions[]`
- `socketOptions[]`
- `enchantOptions[]`
- `embellishmentOptions[]`
- `communityTemplates[]`
- `selectedCandidate`
- `applyState`: ready, partial, blocked, loading
- `blockers[]`

Events:

- `selectSource(sourceId)`
- `selectCandidate(candidateId)`
- `selectVariant(variantKey)`
- `selectCraftedStat(optionId)`
- `selectEnhancement(kind, optionId)`
- `applySelection()`
- `importTemplate(templateId)`

Uses:

- `WowPanel` for sheet sections.
- `GameObjectIcon` for candidate and item icons.
- `StatusVisual` for candidate readiness.
- `ActionButton` for apply/import/fixed actions.
- `EvidenceLedger` for blockers and source explanations.

Owns:

- Sheet header, source filter geometry, candidate rows, item detail, variant/crafted selectors and enhancement groups.
- Fixed bottom action and disabled/loading states.
- Candidate row density and long item names.

Forbidden:

- Applying partial candidates without visible blocker.
- Page-private fixed action buttons.
- Raw `bonus_id`, `gem_id`, `enchant_id`, `crafted_stats` leakage in player-facing text.
- Fake source counts or fake verified state.

Required fixtures:

- `gear_sheet_loading`
- `gear_sheet_empty`
- `gear_sheet_candidate_ready`
- `gear_sheet_candidate_partial`
- `gear_sheet_variant_required`
- `gear_sheet_crafted_stat_required`
- `gear_sheet_enhancement_limit`
- `gear_sheet_community_import`
- `gear_sheet_apply_blocked`

Measured invariants:

- Fixed sheet action stays reachable and does not cover the last row.
- Candidate icon/title/source/status align in one row without overlap.
- Long item names wrap within the row while action/state remain visible.
- Blocked apply state explains what is missing before the button.

## TaskQueueBoard

Role: owns SimC task list, status rail and empty-state actions.

Inputs:

- `tasks[]`: id, status, title, context, createdAt, updatedAt, scenario, summary, isPreview
- `loading`
- `empty`
- `error`
- `activeCounts`
- `guestState`

Events:

- `openTask(taskId)`
- `goSimc()`
- `goWorkbench()`

Uses:

- `PageFrame` for task route spacing.
- `WowPanel` for task cards and empty-state slab.
- `StatusVisual` for task status.
- `ActionButton` for navigation actions.
- `EvidenceLedger` for guest/fallback and queue explanations.

Owns:

- List hero, status rail, task cards, tag chips, time rows, empty-state steps and list actions.
- Queued/running/completed/failed visual grammar.
- Preview/generated suppression language.

Forbidden:

- Preview DPS, generated-profile DPS or fake rankings.
- Raw SimC command, raw profile, traceback or crash strings.
- Page-private task rail, status chips or empty steps.

Required fixtures:

- `tasks_loading`
- `tasks_empty`
- `tasks_error`
- `tasks_list_ready`
- `task_card_queued`
- `task_card_running`
- `task_card_completed`
- `task_card_failed`
- `tasks_guest_read`
- `tasks_empty_to_simc`
- `tasks_empty_to_workbench`

Measured invariants:

- Task status rail remains readable at compact width.
- Cards keep status, title and time rows inside bounds.
- Empty-state actions do not duplicate the same intent.
- No raw diagnostic text is visible in list cards.

## TaskResultReport

Role: owns task detail and final result presentation.

Inputs:

- `task`
- `analysis`
- `simcReport`
- `isPreview`
- `isFinal`
- `contextRows[]`
- `statRows[]`
- `combatBuffRows[]`
- `failureRows[]`
- `loading`
- `missingId`
- `notFound`

Events:

- `goBack()`
- `goSimc()`
- `askChickenbro(contextId)`

Uses:

- `PageFrame` for stack route spacing.
- `WowPanel` for report shell and result sections.
- `StatusVisual` for task/result status.
- `ActionButton` for handoff actions.
- `EvidenceLedger` for result source, blockers and localized failures.

Owns:

- Detail hero, final result metric, run context, stat rows, combat buffs, localized failure rows and no-result states.
- Final result gate: only non-preview completed SimC tasks may show DPS/damage metrics.

Forbidden:

- DPS or damage metric from preview/generated/confirm-only data.
- Raw `sim_signal_handler`, segmentation fault or command/profile text.
- Fake percentile, rank, grade, comprehensive score or upgrade priority.

Required fixtures:

- `task_detail_loading`
- `task_detail_missing_id`
- `task_detail_not_found`
- `task_detail_preview_no_dps`
- `task_detail_final_result`
- `task_detail_failed_timeout`
- `task_detail_failed_raw_diagnostic`
- `task_detail_context`
- `task_detail_combat_buffs`
- `task_detail_guest_read`

Measured invariants:

- Final metric appears only under `isFinal=true`.
- Failure rows localize raw diagnostics and keep raw text hidden.
- Context and combat buff rows stay readable without forming nested cards.
- Handoff actions remain one-line and do not collide with bottom safe area.

## ProfileIdentityPanel

Role: owns the personal identity and sync header of the profile tab.

Inputs:

- `profile`: avatarUrl, nickname, role, loginState, isGuest, lastSavedAt
- `draftState`: clean, dirty, saving, saved, failed
- `syncState`: local_only, syncing, synced, remote_failed, auth_required
- `metrics`: talentTemplateCount, gearTemplateCount

Events:

- `chooseAvatar()`
- `updateNickname(value)`
- `saveProfile()`
- `login()`

Uses:

- `PageFrame` for tab spacing.
- `WowPanel` for identity cockpit.
- `GameObjectIcon` only for real/avatar/fallback socket where appropriate.
- `StatusVisual` for guest/formal/sync state.
- `ActionButton` for save/login actions.
- `EvidenceLedger` for local-only and sync-limited explanation.

Owns:

- Avatar socket, nickname field, guest/formal label, save state, sync state and profile metrics.
- Local-first state explanation.

Forbidden:

- Raw token, raw openid, unionid, internal user id or database id.
- Fake cloud sync, fake verified account, fake official membership.
- Page-private avatar/socket geometry.

Required fixtures:

- `profile_guest_local_only`
- `profile_formal_synced`
- `profile_remote_sync_loading`
- `profile_remote_sync_fallback`
- `profile_local_draft_dirty`
- `profile_save_failed`
- `profile_long_nickname`
- `profile_missing_avatar`

Measured invariants:

- Avatar, nickname and sync status remain aligned on compact viewport.
- Save/login actions keep stable height and do not wrap.
- Local-only or remote-failed state remains visible.
- Metrics come from template summary, not invented values.

## TemplateLibraryBoard

Role: owns the user's talent and gear template library.

Inputs:

- `talentTemplates[]`
- `gearTemplates[]`
- `loading`
- `empty`
- `remoteState`
- `deleteState`
- `entryState`

Events:

- `openTalentTemplate(templateId)`
- `openGearTemplate(templateId)`
- `confirmDelete(templateId)`
- `cancelDelete()`
- `deleteTemplate(templateId)`

Uses:

- `WowPanel` for library sections.
- `ModuleCard` for talent/gear module summaries.
- `StatusVisual` for sync/delete/template state.
- `ActionButton` for entry/delete actions.
- `EvidenceLedger` for local/remote sync notes.

Owns:

- Talent/gear module layout, recent template cards, meta chips, saved time, sync state, delete confirmation hooks and empty states.
- Safe display of template summary without exposing raw strings.

Forbidden:

- Full `rawString`, full `simcLines`, raw imported talent code or raw gear profile in visible UI.
- Fake SimC-ready, fake official recommendation or fake cloud sync.
- Deleting without confirmation.
- Page-private template card and delete button geometry.

Required fixtures:

- `template_empty`
- `template_library_loaded`
- `template_long_title`
- `template_missing_meta`
- `template_remote_sync_fallback`
- `template_delete_confirm`
- `template_delete_cancel`
- `template_delete_success`
- `template_delete_remote_fallback`
- `template_entry_talent`
- `template_entry_gear`

Measured invariants:

- Template cards show title, type, saved time and sync state without raw payload.
- Delete confirmation cannot be bypassed by layout.
- Long titles do not push actions off card bounds.
- Empty state offers clear next actions without duplicate intent.

## Activation Impact

These owner contracts remove the current contract-level blockers from permit drafts, but they do not activate implementation. Each surface still needs:

- user-confirmed or revised target lock;
- accepted asset manifest entries;
- owner component skeletons if the owner is new;
- fixture matrix in source or harness;
- production component precheck;
- browser component precheck;
- active implementation permit for exactly one surface;
- real mini-program screenshots, crops, overlay/red-zone, scorecard, route smoke and DevTools action ledger after implementation.

## Anti-Regression Mapping

| Previous Failure | Owning Contract |
| --- | --- |
| status shield and exclamation split apart | `StatusVisual`, then domain owner only positions the component box |
| page gutters hit screen edge | `PageFrame`, then domain owner internal inset tokens |
| compressed gold CTA button | `ActionButton`; domain owner cannot override button height |
| workflow cards stack icon/text without hierarchy | `ModuleCard` or domain owner card contract |
| generated material sits behind factual content | `MaterialImage` with low-semantic asset classes only |
| fake or guessed WoW icons | `GameObjectIcon` only with real source map |
| reader/list fallback hidden | `ArticleListBoard`, `ArticleReader`, `EvidenceLedger` |
| talent nodes drift or choice affordance breaks | `TalentTreeCanvas` |
| equipment slot badges overflow | `GearLoadoutBoard` |
| task result shows preview DPS | `TaskResultReport` final result gate |
| profile page exposes raw identity/template data | `ProfileIdentityPanel`, `TemplateLibraryBoard` |

## Non-Promotion Rule

This document can only prove `surface_owner_contract_draft`. It cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- `component_precheck`;
- `runtime_verified`;
- `final_accepted`.
