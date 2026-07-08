# Tasks Owner Skeleton Source Precheck

Status: `owner_skeleton_source_precheck`
Created: 2026-07-07

This document records the source-level owner skeleton for the `tasks` surface. It does not authorize edits to `pages/simulator/tasks.*` or `pages/simulator/task-detail.*`.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Tasks Permit Draft](../plans/2026-07-07-wow-ui-system-tasks-implementation-permit-draft.md)
- [Surface Owner Contracts](2026-07-07-wow-ui-system-surface-owner-contracts.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-tasks-owner-skeleton/manifest.json`
- Fixture matrix: `artifacts/ui-system-rebuild/20260707-tasks-owner-skeleton/fixtures.json`

## Design Read

Reading this as: a dense task-history and result-report surface for WoW players, with a high-confidence evidence ledger and no fake result shortcuts.

## Owners Added

| Owner | Component | Owns | Page Must Not Own |
| --- | --- | --- | --- |
| `TaskQueueBoard` | `components/task-queue-board` | task list hero, status rail, task cards, tags, time rows, empty-state actions, guest/fallback evidence | status chips, task card geometry, empty-state steps, duplicate actions |
| `TaskResultReport` | `components/task-result-report` | detail hero, final result gate, context rows, stat rows, combat prep rows, localized failure rows, handoff actions | final metric gate, failure row localization, raw diagnostic hiding, report row geometry |

## Fixture Matrix

`TaskQueueBoard` fixtures:

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

`TaskResultReport` fixtures:

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

## Data Trust Rules

- List cards do not show preview strong metrics, fake ranks, fake grades or upgrade priority.
- `TaskResultReport` only exposes final result rows when `isFinal=true`.
- Preview, missing, blocked and failed states explain the gate instead of showing numbers.
- Raw command/profile/diagnostic text is localized before visible output.
- Guest state is presented as a read boundary, not as a fake account sync state.

## Non-Promotion

This precheck proves only `owner_skeleton_source_precheck`. It is not:

- `target_locked`
- `active_implementation_permit`
- `surface_component_precheck`
- page integration
- runtime verification
- final acceptance

Next required evidence is a browser/component precheck with crops for `TaskQueueBoard` and `TaskResultReport`, followed by target lock and active permit conversion before any page integration.
