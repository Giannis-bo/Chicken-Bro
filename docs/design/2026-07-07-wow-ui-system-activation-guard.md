# WOW UI System Activation Guard

Status: `activation_guard_blocked_waiting_for_target_lock`

Date: 2026-07-07

This guard records the current implementation gate for the WOW mini-program UI system rebuild. It exists because the project has a target-lock decision request and an activation packet draft, but it does not yet have an explicit user-confirmed `target_locked` decision record or an active implementation permit.

This document is not `target_locked`, not an active implementation permit, not page integration, not runtime verification, and not final acceptance.

## Gate Snapshot

- activationAllowed=false
- pageIntegrationAllowed=false
- targetLocked=false
- activePermit=false
- runtimeVerified=false
- finalAccepted=false
- devtoolsTouched=false
- targetLockedDecisionRecordPath=`docs/design/2026-07-07-wow-ui-system-target-locked-decision.md`
- targetLockedDecisionRecordExists=false
- firstActivePermitPath=`docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md`
- firstActivePermitExists=false

## Blocking Reasons

- `missing_target_locked_decision_record`
- `missing_active_implementation_permit`
- `continuation_turn_is_not_confirmation`

## Guard Rules

1. If `docs/design/2026-07-07-wow-ui-system-target-locked-decision.md` is absent, no active implementation permit may be created.
2. If `docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md` is absent, no page WXML/WXSS implementation is allowed.
3. Continuation turns, `继续`, passing tests, browser/component precheck, Codex confidence, silence, or ambiguous approval do not unlock target lock.
4. Browser/component precheck can remain useful source evidence, but it cannot unlock runtime verification, final acceptance, or page edits.
5. Any future active permit must name exactly one surface, allowed files, forbidden files, owner components, data boundary, asset manifest entries, route smoke scenes, pre-integration checks, stop conditions, and post-integration runtime evidence.

## Automated Preflight

Run `node scripts/ui-system-activation-preflight.js --json` to inspect the current gate.

Run `node scripts/ui-system-activation-preflight.js --require-activation --json` before page implementation entrypoints. While this guard is blocked, the command exits non-zero and reports the missing target-locked decision record, missing active implementation permit, and continuation-turn insufficiency.

Run `node scripts/ui-system-diff-scope-audit.js --summary-json` to classify the current dirty worktree. Current source evidence is recorded in [WOW UI System Diff Scope Audit](2026-07-07-wow-ui-system-diff-scope-audit.md), where page/app/navigation changes are quarantined until target lock and active permit exist.

Run `node scripts/ui-system-target-lock-decision-preflight.js --require-decision --json` after the user explicitly confirms target lock. The template-only input is [WOW UI System Target-Locked Decision Template](2026-07-07-wow-ui-system-target-locked-decision-template.md); the real decision record remains absent until explicit confirmation exists.

Run `node scripts/ui-system-active-permit-preflight.js --surface news_list_detail --require-active-permit --json` before the first page implementation. The template-only input is [News List Detail Active Implementation Permit Template](../plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit-template.md); the real active permit remains absent until a valid target-locked decision record exists.

Run `node scripts/ui-system-implementation-gate.js --require-implementation --json` as the single implementation entrypoint. It aggregates activation, target decision, active permit and diff-scope gates.

## Allowed While Blocked

- Update roadmap, ideas, plans, design docs, tests, manifests, harnesses, and evidence registers.
- Tighten component owner contracts, asset boundaries, route smoke plans, and verification scripts.
- Re-run source-level or browser/component prechecks that do not touch page integration or DevTools state.

## Not Allowed While Blocked

- No page WXML/WXSS implementation is allowed.
- No conversion from draft permit to active permit is allowed.
- No `target_locked`, `runtime_verified`, or `final_accepted` claim is allowed.
- No WeChat DevTools capture is required by this guard, and this guard does not touch DevTools.

## Next Valid Transition

The next valid transition is explicit user target-lock confirmation or written modification. After that confirmation exists, the project may write a `target_locked` decision record and then convert exactly one draft implementation permit to active.

This guard can only prove `activation_guard_blocked_waiting_for_target_lock`; it cannot prove `target_locked`, `active_implementation_permit`, `page_integration`, `runtime_verified`, or `final_accepted`.

## Evidence Links

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Two-Part Goal Sync](../plans/2026-07-07-wow-ui-system-two-part-goal-sync.md)
- [Phase 1/2 Closure Audit](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-phase1-2-closure-audit.md)
- [Target Lock Decision Request](2026-07-07-wow-ui-system-target-lock-decision-request.md)
- [Target Lock Readiness Review](2026-07-07-wow-ui-system-target-lock-readiness-review.md)
- [Target Lock Decision And News List Detail Activation Packet](../plans/2026-07-07-wow-ui-system-target-lock-decision-and-news-list-detail-activation-packet.md)
- [Permit Coverage Matrix](2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
