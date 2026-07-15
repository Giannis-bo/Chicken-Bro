# Harness v0.6 Efficiency Design

**Status:** User-approved B approach; docs/tooling-only delivery.

## Goal

Keep the repository's fail-closed runtime release discipline while removing verification and coordination work that does not add a new safety signal.

## Decisions

1. **Risk decides verification, not the `Strict` label alone.** Development starts with targeted tests. Docs, evidence and archive-only changes use the `harness` profile. Normal runtime changes use one exact-final-head CI `full`; write paths, migrations and data repair may add one local `full` before candidate deployment.
2. **CI has one complete entrypoint.** The `full` profile already includes Node, Python, JSON, syntax, packet and diff checks, so CI no longer runs a separate `harness` profile first.
3. **One final runtime head, one candidate deployment.** The final compatible binary proves both old and new reader behavior unless a real rolling-upgrade or schema-compatibility requirement justifies an intermediate deployment.
4. **A small candidate window replaces a concurrency platform.** Before final CI/candidate, sync with `main`; while a runtime candidate is active, do not merge an overlapping runtime PR. If manual acceptance waits too long, release the window and defer expensive final validation.
5. **Merge and archive are distinct.** A PR merges after candidate/CI/scoped live evidence. Documentation closure follows and, when no runtime tree changed, runs only `harness` rather than business `full`.
6. **Review and cleanup are bounded.** One independent whole-branch review is the default. Only the task's own branch/worktree is a merge concern; global branch/worktree hygiene is separate work.

## Non-goals

- Do not remove candidate deployment, live smoke, rollback evidence or real DevTools evidence when a change needs them.
- Do not change backend, PostgreSQL, mini-program, deployment or production data behavior.
- Do not introduce a lane registry, resource lease system or external CI dependency.

## Verification

- TDD: prove CI has one profile run and that the read-only Harness manifest exposes every v0.6 rule.
- Control plane: validate the new release packet, current truth and roadmap entry.
- Local closure: run the Harness profile and the focused project-harness/project-state/verify-project test set. No production deployment is applicable.
