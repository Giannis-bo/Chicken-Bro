# Scheduled Sync Log Bounding Plan

**Harness slice:** Strict scheduled-job/runtime safety correction.

**Goal:** Stop `wow-websim-sync` and `wow-stat-weights-sync` from writing full
nested sync payloads into journald/syslog while preserving the complete state in
PostgreSQL and retaining enough bounded summary/progress evidence for operators.

## Current evidence

- `/var/log` is 4.3 GiB; current and previous syslog files account for about
  2.8 GiB and persistent journal for about 816 MiB.
- among the latest 50,000 journal records, 37,500 belong to
  `wow-stat-weights-sync.service` and 8,770 to `wow-websim-sync.service`;
- both scripts currently pretty-print the complete nested result to stdout;
- the jobs are inactive now, but their timers remain scheduled, so deleting
  logs without bounding output would only defer recurrence.

## Contract

- Full sync state remains persisted by the existing PostgreSQL owners.
- stdout emits one compact JSON summary with stable status, runner, revision,
  scalar counts, and bounded diagnostics only.
- stderr progress events retain stage/status/duration and bounded scalar counts;
  nested payloads, profile rows, full errors, source responses, and credentials
  never enter the log.
- Each JSON line is at most 8 KiB; strings and component counts are bounded.
- Sync behavior, source limits, timers, PostgreSQL writes, and job exit status do
  not change.

## Tasks

1. [x] RED tests for a large nested result and progress event.
2. [x] Add one shared pure summary/sanitization owner.
3. [x] Route both scheduled scripts through it.
4. [x] Run targeted sync/deploy tests and local CR.
5. [ ] Build an immutable candidate or equivalent source-parity smoke without
   launching the expensive scheduled jobs.
6. [ ] Deploy the reviewed scripts, then rotate/vacuum old logs and verify growth
   remains bounded before reconsidering the cloud disk gate.

Observed local verification: 35 targeted sync, PostgreSQL-only, deploy, and
bounded-log tests pass. Existing SQLite `ResourceWarning` and module-run
`RuntimeWarning` diagnostics remain visible and are not represented as clean
resource evidence.

## Stop lines

- do not run WebSim/stat-weight sync as a smoke;
- do not delete historical databases or project backups;
- do not suppress `blocked`/`partial` status;
- do not alter timer cadence, ingestion limits, persisted state, or source
  behavior;
- do not vacuum logs until the deployed script identity is verified.
