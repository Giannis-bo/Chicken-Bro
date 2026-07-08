# Profile Templates Owner Skeleton Source Precheck

Status: `owner_skeleton_source_precheck`
Created: 2026-07-07

This document records the source-level owner skeleton for the `profile_templates` surface. It does not authorize edits to `pages/profile/profile.*`.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Profile Templates Permit Draft](../plans/2026-07-07-wow-ui-system-profile-templates-implementation-permit-draft.md)
- [Surface Owner Contracts](2026-07-07-wow-ui-system-surface-owner-contracts.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-profile-templates-owner-skeleton/manifest.json`
- Fixture matrix: `artifacts/ui-system-rebuild/20260707-profile-templates-owner-skeleton/fixtures.json`

## Design Read

Reading this as: a local-first personal asset surface for WoW players, where identity, template library, sync limits and destructive deletion must be clearer than decorative profile chrome.

## Owners Added

| Owner | Component | Owns | Page Must Not Own |
| --- | --- | --- | --- |
| `ProfileIdentityPanel` | `components/profile-identity-panel` | avatar socket, nickname draft input, guest/formal status, local-first save state, sync evidence, profile metrics | avatar geometry, nickname field sizing, fake sync badge, local/remote explanation layout |
| `TemplateLibraryBoard` | `components/template-library-board` | talent/gear modules, recent template cards, meta chips, empty states, delete confirmation hooks, sync/fallback evidence | template card geometry, delete button geometry, raw template preview, local/remote fallback language |

## Fixture Matrix

`ProfileIdentityPanel` fixtures:

- `profile_guest_local_only`
- `profile_formal_synced`
- `profile_remote_sync_loading`
- `profile_remote_sync_fallback`
- `profile_local_draft_dirty`
- `profile_save_failed`
- `profile_long_nickname`
- `profile_missing_avatar`

`TemplateLibraryBoard` fixtures:

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

## Data Trust Rules

- Profile edits stay local-first; remote failure cannot clear nickname or avatar.
- Template counts and cards are read-model inputs, not hard-coded decoration.
- Remote fallback is visible as local-only or sync-limited, never as cloud synced.
- Template cards do not expose `rawString`, `simcLines`, raw imported talent codes or raw gear profiles.
- Deletion remains a confirmation flow and cannot be represented as a plain card action.

## Non-Promotion

This precheck proves only `owner_skeleton_source_precheck`. It is not:

- `target_locked`
- `active_implementation_permit`
- `surface_component_precheck`
- page integration
- runtime verification
- final acceptance

Next required evidence is a browser/component precheck with crops for `ProfileIdentityPanel` and `TemplateLibraryBoard`, followed by target lock and active permit conversion before any page integration.
