# Data Health Sync Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop unchanged health blockers from automatically rerunning heavyweight collection while adding a controlled SimC-only talent graph recovery path.

**Architecture:** Reuse the existing PostgreSQL JSONB sync-state repository for a revision-gated action ledger. The health-followup script is only an orchestrator: it records a first-seen baseline, allows one action per changed domain revision or explicit refresh request, and never starts full WebSim. A dedicated systemd unit invokes the existing WebSim runner with both remote collection stages disabled for manual talent recovery.

**Tech Stack:** Python 3 standard library, PostgreSQL `cache.websim_sync_state`, systemd units, Node/Python unittest Harness.

## Global Constraints

- Keep PostgreSQL-only runtime and existing public health truth boundaries.
- Do not introduce a migration, dependency install, external download, deploy-triggered async sync, or full Journal rewrite.
- `wow-websim-sync.timer` remains the daily full reconciliation path; health follow-up must not start it.
- All recovery writes require the existing global sync lock; the talent graph unit is manual-only.
- Candidate deployment, backup, read-only preflight, smoke and rollback proof are required before merge.

---

### Task 1: Revision-gated follow-up policy

**Files:**

- Modify: `server/data_health_followup.py`
- Test: `tests/data_health_followup_test.py`

**Interfaces:**

- Produces `plan_followup_actions(health, *, prior_state=None, force_actions=()) -> dict`.
- Produces `followup_state_after_plan(prior_state, plan) -> dict` for the sync-state repository.
- `plan["actions"]` retains the existing action dictionaries and adds `inputRevision` and `decision`.

- [ ] **Step 1: Write failing tests for the policy**

```python
plan = plan_followup_actions(health_with_gear_revision("gear-r1"), prior_state={})
self.assertEqual(plan["actions"], [])
self.assertIn("gear_observed_backfill:baseline_recorded", plan["reportOnly"])

plan = plan_followup_actions(
    health_with_gear_revision("gear-r2"),
    prior_state={"actions": {"gear_observed_backfill": {"lastSeenRevision": "gear-r1"}}},
)
self.assertEqual([action["key"] for action in plan["actions"]], ["gear_observed_backfill"])
self.assertEqual(plan["actions"][0]["inputRevision"], "gear-r2")
self.assertNotIn("websim_sync", [action["key"] for action in plan["actions"]])
```

- [ ] **Step 2: Run the focused test and confirm it fails because the revision-gated interface is absent**

Run: `python3 -m unittest tests.data_health_followup_test.DataHealthFollowupTest.test_changed_gear_revision_starts_only_observed_backfill`

- [ ] **Step 3: Implement the minimal pure policy**

```python
def plan_followup_actions(health, *, prior_state=None, force_actions=()):
    state = normalize_followup_state(prior_state)
    actions, report_only, manual_blockers = [], [], []
    evaluate_revision_gated_action(actions, report_only, manual_blockers, state, "gear_observed_backfill", gear_revision(health))
    evaluate_revision_gated_action(actions, report_only, manual_blockers, state, "stat_weights_sync", stat_weights_revision(health))
    evaluate_revision_gated_action(actions, report_only, manual_blockers, state, "simc_runtime_update", simc_update_revision(health))
    add_forced_actions(actions, manual_blockers, force_actions)
    return {"actions": actions, "manualBlockers": manual_blockers, "reportOnly": report_only}
```

The helper must record first-seen values without action, treat explicit `refreshNeeded` as a one-time action for its explicit revision, and return report-only for missing revisions. Do not call `_append_action(..., "websim_sync")` from the new policy.

- [ ] **Step 4: Run focused policy tests**

Run: `python3 -m unittest tests.data_health_followup_test`

- [ ] **Step 5: Commit the task**

Run: `git add server/data_health_followup.py tests/data_health_followup_test.py && git commit -m "feat: gate health followup by revision"`

### Task 2: Durable ledger and health observability

**Files:**

- Modify: `server/data_health_followup.py`
- Modify: `server/news_backend.py`
- Test: `tests/data_health_followup_test.py`
- Test: `tests/news_backend_test.py`

**Interfaces:**

- Consumes `PostgresCacheStore.get_sync_state("data_health_followup_v1")` and `save_sync_state(...)`.
- Produces a consumer-only `/api/data/health` component with key `data_health_followup`.

- [ ] **Step 1: Write failing persistence and health-component tests**

```python
with patch("server.data_health_followup.followup_state_store", return_value=fake_store):
    exit_code = main(["--health-url", url, "--execute"])
self.assertEqual(fake_store.saved_key, "data_health_followup_v1")
self.assertEqual(fake_store.saved_value["actions"]["gear_observed_backfill"]["lastSeenRevision"], "gear-r1")

component = data_health_followup_health_component(fake_store)
self.assertEqual(component["key"], "data_health_followup")
self.assertEqual(component["details"]["mode"], "revision_gated")
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `python3 -m unittest tests.data_health_followup_test tests.news_backend_test`

- [ ] **Step 3: Implement store adapter, claim-before-start, and consumer health component**

```python
FOLLOWUP_STATE_KEY = "data_health_followup_v1"

def persist_followup_plan(store, prior_state, plan):
    next_state = followup_state_after_plan(prior_state, plan)
    store.save_sync_state(FOLLOWUP_STATE_KEY, next_state)
    return next_state
```

`main()` must load and persist the ledger before executing any action. If the store cannot be created or read, it must output `manualBlockers=["data_health_followup_state_unavailable"]`, execute no heavy action, and return a nonzero result only for an explicit `--execute` request. `news_backend.py` may read this state but must not modify it or reinterpret catalog quality.

- [ ] **Step 4: Run focused Python tests**

Run: `python3 -m unittest tests.data_health_followup_test tests.news_backend_test tests.postgres_cache_store_test`

- [ ] **Step 5: Commit the task**

Run: `git add server/data_health_followup.py server/news_backend.py tests/data_health_followup_test.py tests/news_backend_test.py && git commit -m "feat: persist health followup decisions"`

### Task 3: Manual SimC-only talent recovery unit

**Files:**

- Create: `server/wow-talent-graph-recovery.service`
- Modify: `server/data_health_followup.py`
- Modify: `tests/data_health_followup_test.py`
- Modify: `tests/deploy-script.test.js`
- Modify: `tests/deploy_lighthouse_test.py`

**Interfaces:**

- `--force-action talent_graph_recovery` is the only policy route to `wow-talent-graph-recovery.service`.
- The unit uses `/run/lock/wow-mini-program-sync.lock`, `WOW_WEBSIM_SKIP_BLIZZARD=1`, and `WOW_WEBSIM_SKIP_RAIDERIO=1`.

- [ ] **Step 1: Write failing tests for forced recovery and unit constraints**

```python
plan = plan_followup_actions({}, force_actions=("talent_graph_recovery",))
self.assertEqual([action["key"] for action in plan["actions"]], ["talent_graph_recovery"])
self.assertTrue(plan["actions"][0]["manualOnly"])
```

```javascript
assert.match(recoveryUnit, /WOW_WEBSIM_SKIP_BLIZZARD=1/)
assert.match(recoveryUnit, /WOW_WEBSIM_SKIP_RAIDERIO=1/)
assert.match(recoveryUnit, /wow-mini-program-sync\.lock/)
```

- [ ] **Step 2: Run focused tests and confirm the new assertions fail**

Run: `python3 -m unittest tests.data_health_followup_test && node --test tests/deploy-script.test.js && python3 -m unittest tests.deploy_lighthouse_test`

- [ ] **Step 3: Add the unit and force-action validation**

```ini
[Service]
Type=oneshot
Environment=WOW_WEBSIM_SKIP_BLIZZARD=1
Environment=WOW_WEBSIM_SKIP_RAIDERIO=1
ExecStart=/usr/bin/flock -w 7200 /run/lock/wow-mini-program-sync.lock /usr/bin/python3 /opt/wow-mini-program/server/websim_sync.py
```

The unit must carry the same PostgreSQL/SimC/TraitEdge environment boundary as the normal WebSim unit. The deploy script must install it without starting it. Unknown `--force-action` values must be rejected before store persistence or systemd execution.

- [ ] **Step 4: Run focused runner/deployment tests**

Run: `python3 -m unittest tests.data_health_followup_test tests.websim_sync_test tests.deploy_lighthouse_test && node --test tests/deploy-script.test.js`

- [ ] **Step 5: Commit the task**

Run: `git add server/wow-talent-graph-recovery.service server/data_health_followup.py tests/data_health_followup_test.py tests/deploy-script.test.js tests/deploy_lighthouse_test.py && git commit -m "feat: add manual talent graph recovery unit"`

### Task 4: Harness packet, runbook, and verification

**Files:**

- Create: `artifacts/releases/2026-07-15-data-health-sync-governance/evidence.json`
- Create: `artifacts/releases/2026-07-15-data-health-sync-governance/manifest.json`
- Modify: `docs/roadmap.md`
- Modify: `docs/roadmap/ideas.md`
- Modify: `docs/talent-simulation-full-chain-runbook.md`

- [ ] **Step 1: Record exact scope, current trigger chain, unit command, candidate smoke, and rollback sequence**

The runbook must require `backup -> read-only LKG/candidate validation -> systemctl start wow-talent-graph-recovery.service -> API/data/timer/log smoke`; it must prohibit full WebSim, Blizzard, and Raider.IO for this recovery.

- [ ] **Step 2: Verify doc/packet gate**

Run: `node scripts/verify-project.js --profile harness --release artifacts/releases/2026-07-15-data-health-sync-governance --base origin/main`

- [ ] **Step 3: Run final write-path verification**

Run: `node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-15-data-health-sync-governance --base origin/main`

- [ ] **Step 4: Review, candidate deployment, and evidence promotion**

Perform one whole-branch local CR, deploy the final candidate with `WOW_DEPLOY_START_ASYNC_SYNCS=0`, capture runtime file parity and PostgreSQL backup, run one forced SimC-only recovery only after read-only validation, and record health/API/unit/timer/journal/rollback evidence before merge.

- [ ] **Step 5: Commit the task**

Run: `git add artifacts/releases/2026-07-15-data-health-sync-governance docs/roadmap.md docs/roadmap/ideas.md docs/talent-simulation-full-chain-runbook.md && git commit -m "docs: record data health sync governance evidence"`

## Plan self-review

- Scope coverage: policy, persistent state, observability, narrow unit, deployment install, runbook, verification, and rollback are each assigned to a task.
- No migration or full ingestion rewrite is included; that would exceed the approved first delivery.
- The policy names and store key are consistent across all tasks.

## Execution choice

The user explicitly requested immediate implementation. Developer coordination restricts this task to inline execution, so the next step is `superpowers:executing-plans` in this isolated worktree.
