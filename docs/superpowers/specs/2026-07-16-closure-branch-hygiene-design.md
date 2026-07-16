# Closure Branch Hygiene Design

**Date:** 2026-07-16  
**Status:** user-approved design; documentation implementation pending written-spec review  
**Scope:** Repository governance only. No product, runtime, deployment, data or remote-history semantics change.

## Goal

After a user explicitly authorizes closure (for example, `可以收尾` or `合入吧`), leave the local repository in a known, tidy state as well as merging and pushing `main`. The agent must inspect local branch and worktree residue after `main`/`origin/main` parity is proven, safely return no-longer-needed clean worktrees to `main`, and remove branches that are already merged.

The goal is not to delete every non-`main` branch. It is to remove only residue with a concrete proof that it is no longer needed, while preserving in-progress work and user-local configuration.

## Placement in the closure sequence

The new hygiene sweep runs **after** the existing final local CR, merge-result verification, `main` push, and local/remote `main` SHA parity check. It therefore cannot delay a successful functional merge or cause a candidate deployment to become stale.

The existing task-branch/worktree cleanup remains first. The hygiene sweep then examines any remaining local residue across all registered worktrees.

## Safe decision rules

1. Read `git worktree list --porcelain`, `git branch -vv`, and each worktree's `git status --short --branch`.
2. A local branch is eligible only if it is not `main` and `git merge-base --is-ancestor <branch> main` succeeds.
3. A branch checked out by a **clean** worktree is eligible only after that worktree switches to `main`; deletion uses ordinary `git branch -d`, never `-D`.
4. A merged branch with no checked-out worktree is deleted with ordinary `git branch -d`.
5. A worktree with uncommitted changes, an unmerged branch, or a detached HEAD is never force-switched, removed, reset, or deleted. The agent preserves it and reports the exact reason as a hygiene exception.
6. `main`, active non-merged work, and remote history are not rewritten. The established post-merge deletion of the published task branch continues to use ordinary remote branch deletion only after `main` contains it.

## Expected report

The closure report states one of the following for every discovered non-`main` worktree/branch:

- `cleaned`: switched safely to `main` and removed because it was merged;
- `preserved`: explains whether it has local changes, is unmerged, or is detached;
- `not applicable`: no residue exists.

The report also confirms the final local `main` and `origin/main` SHA pair. A preserved exception does not invalidate a completed product release; it simply prevents destructive cleanup.

## Documentation changes and verification

The implementation updates both repository instruction surfaces:

- `AGENTS.md` gains the post-parity local branch-hygiene step and its preservation boundaries.
- `docs/harness.md` expands User Acceptance Closure, replaces the old task-only/historical-branch exclusion with this non-blocking sweep, and records a v0.7 policy entry.
- `docs/roadmap.md` records the confirmed governance decision.

Because this is documentation-only governance, verification is `git diff --check`, the Harness documentation checks (`node --test tests/project-harness.test.js`), and `node scripts/verify-project.js --profile harness --release <active release> --base origin/main` if the active release packet accepts the documentation change. No deploy, sync, service restart, candidate runtime smoke, or branch deletion is part of this documentation change.

## Non-goals

- No automatic deletion of unmerged, dirty, or detached work.
- No `git branch -D`, `git reset --hard`, force push, rebase, remote rewrite, or forced worktree removal.
- No pre-merge global cleanup that blocks a valid feature release.
- No change to task scope, user acceptance, candidate deployment, or runtime verification gates.
