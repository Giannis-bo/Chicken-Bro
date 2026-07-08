# Profile Templates Implementation Permit Draft

Status: `implementation_permit_draft`
Surface: `profile_templates`
Primary route: `/pages/profile/profile`
Created: 2026-07-07

This document is not `target_locked`, not an active implementation permit, and does not authorize page WXML/WXSS edits. It records the constraints required before rebuilding the personal profile and template-library surface in the WOW mini-program UI system rebuild.

## Why This Permit Exists

`profile_templates` is the next missing permit after `tasks` in the implementation permit coverage matrix. It owns user assets rather than only presentation:

- WeChat avatar and nickname draft state.
- Local-first profile persistence.
- Local talent and gear template library.
- Remote template fetch, merge, sync and delete fallback.
- Guest/formal boundary and authenticated request safety.
- Destructive template deletion confirmation.
- Future template entry routes back into talent, gear or SimC flows.

This surface must not be treated as a decorative "我的" page pass. A UI rebuild that loses local drafts, sends bearer tokens over insecure HTTP, hides remote fallback as verified sync, or deletes templates without confirmation is a product regression even if the screen looks better.

## Current Source Findings

- `pages/profile/profile.wxml` directly composes `profile-shell`, generated background material, `profile-cockpit`, avatar button, nickname input, metric strip, template modules, template cards, delete buttons and settings rows.
- `pages/profile/profile.wxss` owns shell, cockpit, avatar, metric, template module, template card, delete button and settings geometry as page-private CSS.
- `pages/profile/profile.js` imports `currentProfile` / `saveProfileDraft` from `../common/auth-client` and `buildTemplateSummary` / `fetchBuildTemplates` / `deleteBuildTemplateRemote` from `../common/build-template-storage`.
- `hydrateUser()` reads `currentProfile()` and maps the local/remote profile into the page metrics.
- `hydrateTemplates()` renders local `buildTemplateSummary()` first, then calls `fetchBuildTemplates()` and re-renders after remote merge or fallback.
- `onChooseAvatar()` and nickname handlers save through `saveProfileDraft()`, which persists local profile state before attempting remote auth/profile save.
- `deleteTemplate()` requires `wx.showModal` confirmation when available, then calls `deleteBuildTemplateRemote(id)` and rehydrates templates.
- `pages/common/build-template-storage.js` owns local storage key `wow_build_templates_v1`, `talent` / `gear` filtering, type plus rawString dedupe, updatedAt sorting, local-first sync, remote merge and local-delete-plus-remote-fallback delete.
- `pages/common/auth-client.js` owns auth token/profile storage, WeChat login, local profile fallback and profile draft save behavior.
- `tests/profile-auth.test.js` protects avatar/nickname bindings, profile template modules, saved-time display, generated material references and delete wiring.
- `tests/build-template-storage.test.js` protects missing/bad storage fallback, local save/sort/dedupe/delete, string-only template preservation, insecure HTTP bearer blocking and authenticated HTTPS remote merge.
- `tests/frontend-api-client.test.js` protects profile drafts persisting locally when remote auth is unavailable and authorized requests not sending bearer over insecure HTTP.

## Target Dependency

Before this draft can become active, the following must exist:

- A user-confirmed `target_locked` direction for profile identity and template library, derived from the UI system target lock rather than page-local patching.
- Owner contracts for `ProfileIdentityPanel` and `TemplateLibraryBoard`, now supported by source-level owner skeleton and component precheck evidence.
- An accepted asset manifest entry for profile/page materials, avatar socket, template module surfaces and delete affordances.
- Fixture coverage for guest local-only, formal synced, remote fallback, empty template library, loaded template library, long template title, missing metadata and destructive delete confirmation. Current owner skeleton and component precheck cover these as browser/component evidence.
- Route smoke plan entries for template library read, delete confirmation/cancel/success/fallback and any future template-entry route.

Current supporting evidence:

- [Profile Templates Owner Skeleton Source Precheck](../design/2026-07-07-wow-ui-system-profile-templates-owner-skeleton-precheck.md)
- [Profile Templates Component Precheck](../design/2026-07-07-wow-ui-system-profile-templates-component-precheck.md)
- `artifacts/ui-system-rebuild/20260707-profile-templates-owner-skeleton/manifest.json`
- `artifacts/ui-system-rebuild/20260707-profile-templates-component-precheck/manifest.json`

## Owner Components

Future implementation must compose existing foundation owners and add profile-specific owners instead of rebuilding geometry in page classes.

- `PageFrame`: owns registered route frame, bottom tab spacing, safe area and page gutter.
- `WowPanel`: owns panel shell, border, inset, title/action alignment and dense section spacing.
- `MaterialImage`: owns low-semantic generated material fit, opacity and quarantine/production manifest checks.
- `GameObjectIcon`: owns real object icon treatment when a template has class/spec/gear/talent source evidence; it must not generate fake WoW icons.
- `StatusVisual`: owns local-only, synced, fallback, destructive and unknown state visuals.
- `ActionButton`: owns avatar/nickname save affordances, template entry actions and destructive delete affordance states.
- `ModuleCard`: owns template module/card density and stable slot geometry.
- `EvidenceLedger`: owns readable sync evidence, checkedAt/fallback explanation and source rows.
- `ProfileIdentityPanel`: new or revised owner for avatar socket, nickname input, profile status, guest/formal label, save state and profile metrics.
- `TemplateLibraryBoard`: new or revised owner for talent/gear modules, recent template cards, meta chips, empty states, saved time, sync state, delete confirmation hooks and optional entry actions.

## Data Boundary

Allowed data sources:

- `currentProfile()`
- `saveProfileDraft(profile)`
- `buildTemplateSummary()`
- `listBuildTemplates(type)`
- `fetchBuildTemplates(type)`
- `deleteBuildTemplateRemote(id)`
- `syncBuildTemplate(record)` only through existing save flows or explicitly permitted template actions.
- Existing local storage and remote merge behavior in `pages/common/build-template-storage.js`.

Allowed UI-facing fields:

- Profile display: `nickname`, `avatarUrl`, local/formal profile status derived from `openid` or auth state.
- Template identity: `id`, `type`, `title`, `className`, `classKey`, `specName`, `specKey`, `heroLabel`, `heroKey`, `scenarioTitle`, `status`, `statusLabel`, `source`, `createdAt`, `updatedAt`, `remote`.
- Counts and summaries produced by `buildTemplateSummary()` or equivalent read-model helpers.
- Explicit local/remote/fallback state returned by existing request helpers, if surfaced as user-facing language.

Forbidden UI exposure:

- Auth token, refresh token, raw openid, unionid, internal user id or database row id.
- Full `rawString`, full `simcLines`, raw imported talent code or raw gear profile unless a separate redacted preview design and permit explicitly allows it.
- Full request/response payloads from `/api/me/profile` or `/api/me/build-templates`.
- Any claim that local fallback is cloud synced.
- Any claim that templates are SimC-ready unless the existing template status/readiness source says so.

## Product Rules

- Local profile edits must remain local-first. Remote auth/profile failure may show a fallback status, but it must not erase the local nickname/avatar.
- Template reads must render local data first and may merge remote data when authenticated/available.
- Remote fallback must be visible as local-only or sync-limited state; it cannot be labeled "已同步".
- Deleting a template is destructive and must keep a confirmation path. Cancel must not delete.
- Delete fallback may remove local state first, matching current storage behavior, but the UI must explain retry/fallback state if remote delete fails.
- Template counts must come from `buildTemplateSummary()` or an equivalent normalized read model, not hard-coded display numbers.
- Talent and gear template modules must remain distinct.
- Future template-entry routes must preserve source context: talent templates may enter the talent simulator/import flow, gear templates may enter gear detail/import flow, and SimC may only use templates that pass its own template gate.
- No DPS, ranking, S/A grade, "提升优先级", "云端验证" or "官方推荐" claim may appear on this page without a specific upstream evidence contract.

## Allowed Files After Active Conversion

Only after this draft is explicitly converted to an active permit:

- `pages/profile/profile.wxml`
- `pages/profile/profile.wxss`
- `pages/profile/profile.js`
- `pages/profile/profile.json`
- `pages/common/auth-client.js` only for UI-facing profile result fields, not auth contract changes.
- `pages/common/build-template-storage.js` only for UI-facing summary/sync-state fields, not storage or backend contract changes.
- New or revised foundation/profile components: `ProfileIdentityPanel`, `TemplateLibraryBoard`, `PageFrame`, `WowPanel`, `MaterialImage`, `GameObjectIcon`, `StatusVisual`, `ActionButton`, `ModuleCard`, `EvidenceLedger`.
- Targeted tests for profile auth, build-template storage, frontend API client, UI system goal, component precheck and route smoke artifacts.
- `artifacts/ui-system-rebuild/*profile-templates*` evidence.

## Forbidden Actions

- Do not edit `app.json`, tabBar, `project.config.json`, appid, DevTools settings or route registration from this permit.
- Do not close, restart, clear cache, switch project, switch appid, delete DevTools user directories or run broad DevTools automation from this permit.
- Do not modify backend API contracts or database schema.
- Do not change unrelated pages such as news, builds, workbench, talent, gear, SimC, chickenbro or tasks.
- Do not keep profile shell, avatar, nickname, metric, template card, meta chip, delete button, setting row or material geometry as page-private one-off CSS after active implementation.
- Do not use whole-page target images, old pass screenshots, quarantine assets, generated avatars or generated fake class/spec/template/source icons as production UI facts.
- Do not weaken local-first save, remote merge, insecure HTTP bearer blocking, guest/formal boundary, delete confirmation, local fallback, template dedupe/sort, `rawString` preservation or `simcLines` preservation.

## Required State Mapping

The future page and fixture matrix must cover:

- `profile_loading`
- `profile_guest_local_only`
- `profile_formal_synced`
- `profile_remote_fallback`
- `profile_save_avatar`
- `profile_save_nickname`
- `profile_save_local_fallback`
- `template_library_empty`
- `template_library_loaded`
- `template_module_talent`
- `template_module_gear`
- `template_card_local`
- `template_card_remote`
- `template_long_title`
- `template_missing_meta`
- `template_delete_confirm`
- `template_delete_cancel`
- `template_delete_success`
- `template_delete_remote_fallback`
- `template_entry_talent`
- `template_entry_gear`

If `template_entry_talent` or `template_entry_gear` is not implemented in vNext, the implementation must explicitly mark those scenes as deferred and prove that existing delete/read behavior was not confused with entry behavior.

## Route Smoke Scenes

- `profile_tab_top`: open `/pages/profile/profile` from the bottom tab without duplicate chrome.
- `profile_local_draft`: edit nickname/avatar and keep local draft when remote auth is unavailable.
- `profile_formal_user`: show formal profile status only when auth/current profile proves it.
- `profile_remote_sync_loading`: show bounded loading state without blocking local templates.
- `profile_remote_sync_fallback`: show local-only/fallback state after remote template fetch fallback.
- `profile_template_empty`: show empty talent and gear modules without fake counts.
- `profile_template_library_loaded`: show both module counts and recent template cards.
- `profile_template_long_title`: long title/meta chips do not overflow.
- `profile_template_missing_meta`: missing class/spec/hero metadata degrades without blank layout holes.
- `profile_delete_confirm`: destructive delete asks confirmation.
- `profile_delete_cancel`: cancel leaves the template in the list.
- `profile_delete_success`: confirmed delete removes and rehydrates.
- `profile_delete_remote_fallback`: remote delete failure/fallback is represented without pretending cloud sync succeeded.
- `profile_template_entry_talent`: if active design includes entry, talent card route preserves context.
- `profile_template_entry_gear`: if active design includes entry, gear card route preserves context.

## Required Evidence Before Runtime Acceptance

- Browser/component precheck for `ProfileIdentityPanel`, `TemplateLibraryBoard`, `StatusVisual`, `ActionButton`, `ModuleCard` and `EvidenceLedger`.
- Real WeChat mini-program screenshots for local-only, synced, remote fallback, empty library, loaded library, long title and delete confirmation scenes.
- Component crops for identity panel, template module, template card, delete affordance and sync/fallback status.
- Target vs implementation overlay/red-zone comparisons for page gutter, panel geometry, avatar socket, card spacing, button hit areas and bottom tab/safe area.
- Scorecard that fails on fake sync, raw token/openid leakage, raw template leakage, missing delete confirmation, hard-coded counts, page-private card geometry and direct quarantine asset usage.
- Route smoke manifest for the scenes above.
- DevTools action ledger proving low-disturbance capture; if `captureSafe=false`, only browser/component evidence may be recorded.

## Stop Conditions

Stop and do not implement this surface if:

- `target_locked` is absent or still contested.
- `ProfileIdentityPanel` / `TemplateLibraryBoard` owner contracts are missing.
- The design requires page-private geometry to align avatar, metrics, cards, delete buttons or sync badges.
- The design requires fake login, fake cloud sync, fake verified status or generated WoW object icons.
- A backend contract or schema change is needed to express required sync state.
- Tests would need to weaken local-first save, insecure HTTP bearer blocking, delete confirmation, remote merge, template dedupe/sort, `rawString` preservation or `simcLines` preservation.
- Real mini-program screenshot shows duplicate chrome, bottom tab collision, text overflow, card overflow or destructive action ambiguity.
- DevTools is not capture-safe and the required evidence cannot be gathered through browser/component precheck.

## Non-Promotion Rule

This draft plus the current owner skeleton and browser/component precheck prove only `implementation_permit_draft` and `surface_component_precheck` evidence for `profile_templates`. They cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- `runtime_verified`;
- `final_accepted`.
