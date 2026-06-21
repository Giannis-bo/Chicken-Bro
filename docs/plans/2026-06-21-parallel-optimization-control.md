# Parallel Optimization Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start three safe parallel optimization lanes for gear simulation, SimC, and ZhaJi Captain without letting shared contracts drift.

**Architecture:** Keep `main` stable, create a small coordination commit, then work in three isolated worktrees. Gear integrates before SimC, and SimC integrates before ZhaJi Captain because each lane feeds evidence to the next one.

**Tech Stack:** Git worktrees, WeChat mini-program pages, Python stdlib backend, SQLite-backed service code, Node tests, Python `unittest`.

---

## File Structure

- Modify `.gitignore` to keep local `.worktrees/` directories out of version control.
- Create `docs/superpowers/specs/2026-06-21-parallel-optimization-lanes-design.md` as the approved design record.
- Create this control plan at `docs/plans/2026-06-21-parallel-optimization-control.md`.
- Update `docs/roadmap.md` and `docs/roadmap/ideas.md` to record the confirmed startup direction without claiming implementation is complete.
- Do not modify feature code in the coordination branch.

## Task 1: Prepare Worktree Guardrails

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Verify main checkout and clean status**

Run:

```powershell
git branch --show-current
git status --short
```

Expected: branch is `main`, status has no unrelated changes.

- [ ] **Step 2: Add local worktree ignore rule**

Add this block to `.gitignore`:

```gitignore
# Local parallel worktrees
.worktrees/
```

- [ ] **Step 3: Verify ignore behavior**

Run:

```powershell
git check-ignore .worktrees/
```

Expected output:

```text
.worktrees/
```

## Task 2: Record The Approved Design

**Files:**
- Create: `docs/superpowers/specs/2026-06-21-parallel-optimization-lanes-design.md`
- Create: `docs/plans/2026-06-21-parallel-optimization-control.md`

- [ ] **Step 1: Save the design record**

The design must name the three lanes:

```text
Gear Simulator Optimization
SimC Optimization
ZhaJi Captain Evidence Coach v0
```

It must also state the integration order:

```text
gear first, SimC second, ZhaJi Captain third
```

- [ ] **Step 2: Save the implementation control plan**

The plan must specify:

```text
coordination branch
three isolated worktrees
lane ownership boundaries
lane verification commands
integration order
```

- [ ] **Step 3: Check for incomplete marker language**

Run:

```powershell
rg -n "T[B]D|T[O]DO|待[写]|place[Hh]older" docs/superpowers/specs/2026-06-21-parallel-optimization-lanes-design.md docs/plans/2026-06-21-parallel-optimization-control.md
```

Expected: no matches.

## Task 3: Update Roadmap System

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `docs/roadmap/ideas.md`

- [ ] **Step 1: Update current progress language**

In `docs/roadmap.md`, update the active progress snapshot so it includes:

```text
装备模拟体验优化、SimC 固定模板解释性优化、炸鸡队长证据教练 v0 启动
```

- [ ] **Step 2: Add ZhaJi Captain v0 milestone row**

Add a `正在推进` row for:

```text
炸鸡队长证据教练 v0
```

The row must make clear that v0 is evidence-bound and does not fabricate rankings, DPS/HPS, WCL findings, or player percentile claims.

- [ ] **Step 3: Update ideas status**

In `docs/roadmap/ideas.md`, update the existing ZhaJi Captain idea from `候选` to `已采纳`, and add the 2026-06-21 startup note to its source.

## Task 4: Commit Coordination Layer

**Files:**
- Stage only coordination files:
  - `.gitignore`
  - `docs/superpowers/specs/2026-06-21-parallel-optimization-lanes-design.md`
  - `docs/plans/2026-06-21-parallel-optimization-control.md`
  - `docs/roadmap.md`
  - `docs/roadmap/ideas.md`

- [ ] **Step 1: Review diff**

Run:

```powershell
git diff -- .gitignore docs/superpowers/specs/2026-06-21-parallel-optimization-lanes-design.md docs/plans/2026-06-21-parallel-optimization-control.md docs/roadmap.md docs/roadmap/ideas.md
```

Expected: only coordination and roadmap changes.

- [ ] **Step 2: Stage files**

Run:

```powershell
git add .gitignore docs/superpowers/specs/2026-06-21-parallel-optimization-lanes-design.md docs/plans/2026-06-21-parallel-optimization-control.md docs/roadmap.md docs/roadmap/ideas.md
```

- [ ] **Step 3: Commit**

Run:

```powershell
git commit -m "docs: start parallel optimization lanes"
```

Expected: commit succeeds on `codex/parallel-optimization-contracts`.

## Task 5: Create Isolated Worktrees

**Files:**
- No tracked file edits.

- [ ] **Step 1: Create gear simulator lane**

Run:

```powershell
git worktree add .worktrees/gear-sim-opt -b codex/gear-sim-opt codex/parallel-optimization-contracts
```

Expected: new worktree at `.worktrees/gear-sim-opt`.

- [ ] **Step 2: Create SimC lane**

Run:

```powershell
git worktree add .worktrees/simc-opt -b codex/simc-opt codex/parallel-optimization-contracts
```

Expected: new worktree at `.worktrees/simc-opt`.

- [ ] **Step 3: Create ZhaJi Captain lane**

Run:

```powershell
git worktree add .worktrees/zhaji-captain-start -b codex/zhaji-captain-start codex/parallel-optimization-contracts
```

Expected: new worktree at `.worktrees/zhaji-captain-start`.

- [ ] **Step 4: Verify worktrees**

Run:

```powershell
git worktree list
```

Expected: `main` plus the three new `.worktrees/*` paths are listed.

## Task 6: Lane Verification Commands

**Files:**
- No tracked file edits.

- [ ] **Step 1: Gear lane baseline commands**

Run inside `.worktrees/gear-sim-opt` when implementation starts:

```powershell
node --test tests/builds-page.test.js tests/frontend-api-client.test.js
python -m unittest tests.websim_payload_test
```

- [ ] **Step 2: SimC lane baseline commands**

Run inside `.worktrees/simc-opt` when implementation starts:

```powershell
node --test tests/simulator-page.test.js
python -m unittest tests.news_backend_test tests.websim_payload_test
```

- [ ] **Step 3: ZhaJi Captain lane baseline commands**

Run inside `.worktrees/zhaji-captain-start` when implementation starts:

```powershell
node --test tests/simulator-page.test.js
python -m unittest tests.news_backend_test
```

- [ ] **Step 4: Final integration commands**

Run before merging any lane:

```powershell
node --test tests/*.test.js
python -m unittest discover -s tests -p '*_test.py'
```

Expected: all targeted lane tests pass before lane merge; full tests pass before integration is called complete.
