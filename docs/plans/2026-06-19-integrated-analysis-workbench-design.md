# Integrated Analysis Workbench Design And Implementation Plan

## Goal

Deliver the remaining roadmap work items 1-4 as one coherent product increment while leaving the previously deprioritized items alone:

1. Personal data foundation and account-owned CRUD.
2. Data trust, acquisition validation, and health status.
3. SimC evidence state machine and schema-checked AI reports.
4. Log-driven player analysis foundations.

This plan intentionally does not implement product naming, tab-weight repositioning, or deep Codex Worker expansion.

## Current Evidence

- `docs/roadmap.md` frames the product as a WoW player analysis workbench whose conclusions need source, freshness, validation status, and fallback boundaries.
- `docs/roadmap/ideas.md` has already accepted account-owned CRUD, database governance, data trust, SimC evidence boundaries, and WCL/log review as formal directions.
- `docs/plans/2026-06-17-database-architecture-governance.md` already defines the SQLite governance shape: migration tracking, foreign keys, durable user data, rebuildable cache, and analytics boundaries.
- `docs/plans/2026-06-11-simc-flow-risk-avoidance.md` already defines the SimC evidence-state direction: profile source, run policy, structured stages, guarded LLM output, and reference freshness.
- Baseline verification on 2026-06-19:
  - `node --test tests/*.test.js` passes.
  - `python -m unittest discover -s tests -p '*_test.py'` currently fails before new work. Failures cluster around news seed translation-gate expectations and WebSim gear stats fake SimC execution on Windows. Phase 0 below must stabilize this before broad feature work.
- External source research confirms:
  - Warcraft Logs v2 is OAuth-backed and GraphQL based, so production log ingestion must be credential-gated and schema-validated.
  - Raider.IO exposes a developer API and is already partially integrated through `server/raiderio_payload.py`; it can feed M+ samples and community templates but cannot replace WCL rotation/log evidence.
  - Blizzard Game Data APIs require Battle.net credentials and locale/namespace-aware requests; missing credentials must produce blocked or pending audit status, not silent verified data.

## Priority Order

### Priority 0: Stabilize The Existing Baseline

Before adding production behavior, fix the currently failing Python baseline so future regressions are attributable.

Scope:
- Restore tests around trusted news seeds and refresh-run translation quality.
- Fix WebSim gear stats tests so fake SimC scripts execute reliably on Windows and temporary SQLite handles close cleanly.

Acceptance:
- `python -m unittest discover -s tests -p '*_test.py'` passes.
- `node --test tests/*.test.js` still passes.

### Priority 1: Personal Data Foundation

This must land before remote template sync, role profiles, favorites, subscriptions, log reports, or saved analysis.

Architecture:
- Keep SQLite for the near term.
- Add `schema_migrations` and enable `PRAGMA foreign_keys = ON` in production DB connections.
- Add account-owned `user_build_templates` and minimal endpoints under `/api/me/build-templates`.
- Keep mini-program local template storage as offline drafts, and add explicit remote sync methods rather than silently mixing local and account state.
- All writes require Bearer auth. No Bearer token is sent to insecure HTTP except explicitly guest-safe read paths already supported by the API client.

User-facing behavior:
- Existing “我的” template cards remain available offline.
- When authenticated over HTTPS, saved templates can sync to the account.
- Local-to-account migration is explicit and idempotent.

Acceptance:
- Template CRUD cannot cross accounts.
- Local template save/list/delete still works.
- Remote template sync fails closed without auth.
- Database architecture docs and migration/runbook docs describe owner and backup rules.

### Priority 2: Data Trust And Health

This turns current Raider.IO/stat weight work into a reusable data health surface.

Architecture:
- Add a backend health payload that summarizes independent evidence planes: backend, database migrations, Raider.IO cache, stat-weight cache, WebSim sync, SimC version/probe, and WCL credentials.
- Expose it as a read-only endpoint that never leaks secrets.
- Use normalized statuses: `verified`, `partial`, `stale`, `blocked`, `missing_credentials`, `pending_official_audit`.
- Surface low-sample and stale conditions in existing builds/PVE payloads without creating strong claims.

User-facing behavior:
- Pages that already show source status keep their compact presentation.
- The “智能分析” area gets a concise evidence readiness summary when useful, not a noisy admin console.

Acceptance:
- Health endpoint reports per-source status and checked time.
- Missing WCL credentials are explicit and non-fatal.
- Stale Raider.IO/stat-weight cache is marked stale rather than verified.
- Existing PVE/builds tests still reject legacy or incomplete payloads.

### Priority 3: SimC Evidence State And AI Report Schema

This makes the simulator result report auditable rather than prose-only.

Architecture:
- Add a backend `evidenceState` and `report` object to simulator responses while preserving existing fields.
- Define `runPolicy` from `profileSource`, `confirmOnly`, `runSimulation`, and validation output.
- Build `allowedNumbers` from parsed SimC metrics and trusted reference rows.
- Normalize LLM output into a schema-like report: `topFindings`, `nextActions`, and `limitations`.
- If the LLM output is absent or fails numeric guardrails, return deterministic report content.

User-facing behavior:
- SimC page and task detail render the structured report first.
- Generated templates remain preview-only.
- Failed/blocked SimC runs show the reason and the next useful action, not a fake DPS claim.

Acceptance:
- Confirm-only requests do not call SimC or LLM.
- Generated/template preview does not display as a real character baseline.
- Unsupported numbers are removed or the LLM report is replaced by deterministic fallback.
- Existing task-detail and simulator-page tests pass with new report fields.

### Priority 4: Log-Driven Analysis Foundations

This is a minimal, safe foundation for “炸鸡队长” style analysis without pretending full WCL ingestion is done.

Architecture:
- Add a WCL analysis request mode that accepts report URL/code and optional fight/context text.
- Parse and store only deterministic request metadata locally: report code, source URL, user question, class/spec/context, and evidence status.
- Add a `logEvidence` section with `status`, `sourceStatus`, `missingInputs`, and `nextActions`.
- If WCL credentials are missing, return a blocked report explaining what is needed.
- Do not scrape pages or make uncredentialed claims from WCL statistics.

User-facing behavior:
- Existing WCL mini-program page continues to submit through simulator analysis.
- Response tells the player whether the system can analyze the log now and what input is missing.
- No personal ranking, percentile, or DPS/HPS comparison is invented without actual WCL evidence.

Acceptance:
- WCL mode is route-tested through `/api/simulator/analyze`.
- Missing report code, unsupported URL, and missing credentials each produce distinct deterministic guidance.
- Saved tasks preserve the log evidence status under the requesting owner.

## Review Strategy

After each priority:
- Run the narrow tests for that priority.
- Run all Node tests.
- Run all Python tests once the narrow suite is green.
- Review `git diff` for cross-account data leaks, status overclaiming, stale evidence presented as verified, and UI copy that implies unavailable facts.
- Update roadmap/docs only with evidence-backed status changes.

## Deployment And Manual Verification Strategy

Deployment path:
- Use `server/deploy_lighthouse.sh`.
- Use hot deploy mode only when the remote already has required packages and SimC.
- After deploy, verify `/health`, core API endpoints, and simulator smoke.

Computer Use verification:
- Open the existing WeChat DevTools window for `wow`.
- Compile/refresh if needed.
- Click through:
  - “我的” template module and template state.
  - “职业专精” to “天赋构筑” and template save/load/sync affordances.
  - “PVE专区” and source status rendering.
  - “智能分析” SimC and WCL paths.
- Capture screenshots after each repair cycle.
- Repeat until the visible behavior matches this design and all relevant tests pass.

## Implementation Notes

- Preserve existing user work in the dirty tree.
- Do not rewrite historical `docs/plans/*`; add new evidence docs or roadmap status changes only.
- Do not introduce Postgres, a new frontend framework, or a standalone admin app in this goal.
- Do not send secrets or tokens from the mini program to insecure HTTP.
- Treat all external logs, comments, URLs, and report content as untrusted input.
