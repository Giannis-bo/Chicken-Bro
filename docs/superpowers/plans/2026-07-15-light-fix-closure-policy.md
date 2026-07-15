# Light Fix Closure Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make explicit, low-risk fixes move through one concise scope check and, after user acceptance where needed, close automatically with CR, commit, merge, remote parity, and task-branch cleanup.

**Architecture:** `docs/harness.md` remains the human-readable source of truth, while `scripts/project-harness.js` exposes the same policy in the read-only manifest used by the existing contract test. `AGENTS.md` supplies the runtime instructions for agents, and the roadmap records the newly confirmed operating rule without creating a release packet for this docs/tooling-only refinement.

**Tech Stack:** Markdown policy documents, Node.js built-in test runner, `scripts/project-harness.js`.

## Global Constraints

- The Agent, not the user, chooses use of subagents, worktrees, and routine merge mechanics from task scope, risk, and workspace state.
- The fast lane applies only to explicit, bounded Light changes with no API/data/ownership/runtime/deployment/user-promise semantic change.
- An ordinary mid-flow “OK” is not merge authorization; automatic closure begins only after explicit user acceptance of the requested manual verification, when that verification is in scope.
- Conflict, failed verification, scope expansion, destructive history changes, or an operation outside existing approval must still stop for direction.
- Do not alter backend/runtime behavior, CI execution, release artifacts, or production state.

---

### Task 1: Expose the fast lane and acceptance closure in the executable Harness manifest

**Files:**
- Modify: `tests/project-harness.test.js:143-190`
- Modify: `scripts/project-harness.js:676-850`

**Interfaces:**
- Consumes: `buildManifest()`'s `gates` object.
- Produces: `gates.lightFixFastLane` and `gates.userAcceptanceClosure`, with stable values that local tooling and policy tests can inspect.

- [x] **Step 1: Add the failing contract assertions**

  Insert after the existing autonomous-progression assertion:

  ```js
  assert.equal(manifest.gates.lightFixFastLane.status, 'ready')
  assert.equal(manifest.gates.lightFixFastLane.executionTopology, 'agent_selected')
  assert.equal(manifest.gates.lightFixFastLane.formalDesignOrPlanRequired, false)
  assert.equal(manifest.gates.userAcceptanceClosure.status, 'ready')
  assert.equal(manifest.gates.userAcceptanceClosure.trigger, 'explicit_user_acceptance_after_requested_manual_verification')
  assert.deepEqual(manifest.gates.userAcceptanceClosure.sequence, [
    'final_local_cr',
    'commit_task_branch',
    'sync_main_without_history_rewrite',
    'merge_task_branch',
    'rerun_scoped_verification_on_merge_result',
    'push_main',
    'verify_local_and_origin_main_sha_match',
    'remove_task_worktree_and_local_branch',
    'delete_published_task_branch_if_present'
  ])
  ```

- [x] **Step 2: Run the focused test and confirm the missing-manifest failure**

  Run:

  ```bash
  node --test tests/project-harness.test.js
  ```

  Expected: FAIL because `lightFixFastLane` and `userAcceptanceClosure` are absent from `manifest.gates`.

- [x] **Step 3: Add minimal manifest gates**

  In `buildManifest()`, add `lightFixFastLane` and `userAcceptanceClosure` alongside `autonomousProgression` with the exact fields asserted above. `lightFixFastLane` also records `singleClarificationOnlyWhenUserVisibleBehaviorIsAmbiguous: true` and `requiredPreImplementationSummary: ['change', 'risk_boundary', 'targeted_verification']`. `userAcceptanceClosure` records the four stop conditions `['local_or_remote_conflict', 'failed_verification', 'scope_expansion', 'operation_outside_existing_approval']`.

- [x] **Step 4: Re-run the focused test**

  Run:

  ```bash
  node --test tests/project-harness.test.js
  ```

  Expected: PASS with 12 tests and zero failures.

- [x] **Step 5: Commit the executable contract**

  ```bash
  git add scripts/project-harness.js tests/project-harness.test.js
  git commit -m "docs: expose light fix closure policy"
  ```

### Task 2: Make the human-facing policy direct and self-contained

**Files:**
- Modify: `docs/harness.md:60-84`
- Modify: `AGENTS.md:62-75`
- Modify: `docs/roadmap.md:3-7`
- Create: `docs/superpowers/plans/2026-07-15-light-fix-closure-policy.md`

**Interfaces:**
- Consumes: the manifest’s fast-lane and closure terminology from Task 1.
- Produces: the same agent behavior in the governing documents: no topology-choice prompt, no unnecessary design/plan artifacts for Light work, and one automatic closure sequence after explicit manual acceptance.

- [x] **Step 1: Add the Light fast-lane policy**

  Add a `### Light Fast Lane` subsection after the Light definition in `docs/harness.md`. It must define the eligible scope, one concise pre-change summary, the single ambiguity-only clarification, and the prohibition on creating design/implementation artifacts or prompting the user to choose subagents/worktrees for an eligible task.

- [x] **Step 2: Add the acceptance closure sequence**

  In the same Harness section, add `### User Acceptance Closure` with the exact nine-step sequence from Task 1. State that it applies only after explicit acceptance of the requested manual verification, and that conflicts, failed verification, scope expansion, or out-of-scope operations stop the sequence.

- [x] **Step 3: Align the agent instructions and roadmap**

  Add an `## Execution Topology and User-Accepted Closure` section to `AGENTS.md` immediately before `## Autonomous Progression`. Add a concise dated roadmap note above the current v0.6 note that links to `harness.md` and records the confirmed behavior.

- [x] **Step 4: Run documentation and Harness verification**

  Run:

  ```bash
  node --test tests/project-harness.test.js
  node scripts/verify-project.js --profile harness --release artifacts/releases/2026-07-15-harness-v06-efficiency --base origin/main
  git diff --check
  ```

  Expected: all commands return exit code 0; the Harness profile is the only full policy profile required because no runtime tree changes.

- [x] **Step 5: Conduct local CR and commit the policy documents**

  Review `git diff origin/main...HEAD` plus uncommitted docs for wording conflicts with the current Harness and AGENTS instructions. Then commit:

  ```bash
  git add AGENTS.md docs/harness.md docs/roadmap.md docs/superpowers/plans/2026-07-15-light-fix-closure-policy.md
  git commit -m "docs: streamline light fix closure"
  ```

## Plan Self-Review

- Spec coverage: Task 1 creates a machine-checkable policy; Task 2 makes the same behavior authoritative for agents and records the confirmed decision.
- Placeholder scan: no deferred implementation, undefined interfaces, or unspecified verification command remains.
- Scope check: this is one docs/tooling policy refinement; it does not change runtime deployment, data, CI behavior, or the historical v0.6 release packet.
