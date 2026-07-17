# Winner-Driven Attribute Rule Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the daily community gear Release elects a genuinely new observed-player winner, asynchronously compare a fully matched official character panel with the sealed deterministic attribute calculation, without delaying Release promotion, template import, manual gear changes, or any SimulationCraft workflow.

**Architecture:** A pure audit contract decides eligibility, immutable input identity, deduplication key, input matching and field-level comparison. A dedicated PostgreSQL audit ledger owns intent/lease/result state. The existing Release refresh writes intents only after sealing a candidate Manifest and does so fail-open. A separate systemd worker, started after a successful refresh, reads at most the bounded queued work, calls the official Battle.net profile endpoint read-only, and writes one terminal audit result. Health/admin consumes bounded ledger summaries; the mini-program and public calculator never consume audit liveness.

**Tech Stack:** Python 3 standard library; existing PostgreSQL/`psycopg` repository conventions; existing Blizzard OAuth/profile helper in `server/websim_payload.py`; existing deterministic attribute engine/rule validation; PostgreSQL migration; systemd; Python `unittest`; Node `node:test`; repository-native Harness.

## Global Constraints

- This is Strict work. The current sources of truth are `docs/project-state.json`, `docs/roadmap.md`, `docs/harness.md`, `docs/project-owner-map.json`, the two attribute-engine design documents, and the current Release train modules.
- The normal equipment-simulator path remains entirely local/deterministic: no winner audit, HTTP call, queue state, worker status, or SimC snapshot may gate or delay a player-visible attribute refresh.
- `gear_release_refresh` may **only enqueue durable intent after** candidate Release/Manifest sealing. It must never call Battle.net, wait for the audit worker, mutate an election, alter a Manifest/pointer decision, or turn an audit-write error into a Release failure.
- A community winner is an external comparison candidate, never a formula source. A profile fetch is authoritative only after the exact class/spec/race/level, slot instances, item levels, bonus IDs, gems, enchants and stable-effect input match the sealed winner input.
- No source identity may be guessed from display text, screenshot labels, item names or a Raider.IO URL. Missing identity/input evidence is a terminal `blocked_missing_evidence` outcome and makes no external request.
- Audit worker execution is read-only with respect to Blizzard and must not call SimC, mutate catalog/template/release tables, move the active Manifest pointer, publish a rule, or backfill another source.
- Runtime currently has no source-ledger-backed production attribute rulebook. The first implementation must remain fail-closed: `fixture_only`, missing or non-`verified` contexts produce `not_applicable` and do not call Blizzard. This plan must not invent a production formula merely to exercise the worker.
- `confirmed_mismatch` blocks only a **future** promotion carrying the same `attributeRuleRevision`; it does not automatically hide an existing rule or change player-facing behavior. Any public-rule change remains a separately reviewed revision/feature-hide decision.
- Store raw ratings and formatted percent/effect values in internal comparison evidence, but never expose character name, realm, raw source URL, OAuth material, or full equipment payload in the public `/api/data/health` response.
- Preserve the user-owned `project.config.json` change. Do not stage, modify, revert, or include it in any commit.
- No dependency install, local download or unapproved data download is part of this plan. Candidate deployment later uses the existing approved project deployment path, with `WOW_DEPLOY_START_ASYNC_SYNCS=0` unless the candidate procedure explicitly needs another existing service.

---

## Impact Map and Delivery Contract

| Classification | Surface | Required outcome |
| --- | --- | --- |
| `must_change` | `server/attribute_rule_audit.py`, PostgreSQL audit ledger/store, `server/gear_release_refresh.py`, independent worker/unit, health projection, deployment unit installation, schema/deploy tests | One owner for audit state; normal Release and player interaction stay non-blocking. |
| `must_not_change` | `server/gear_release.py` election policy, Resolver legality, public community-template eligibility, active Manifest semantics, `gear_stat_snapshot_*`, SimC workers, mini-program local attribute interpreter | Tests prove audit outcomes cannot change these results or create a SimC call. |
| `risk_unknown` | Whether a future observed winner has a fully reconstructable character/equipment identity and an actually published `verified` rule context | Conservatively terminalize as `blocked_missing_evidence` / `not_applicable`; do not fetch or infer. |
| `evidence_required` | Candidate Release with changed winner, official profile exact-input match, field-level expected/actual result, independent worker outcome, player interaction timing, migration and rollback proof | Only a same-input panel mismatch may create a rule finding. |

User-visible acceptance remains: importing a community template and changing one item refresh the local non-combat panel immediately; audit availability is not displayed as a spinner, error or prerequisite. Operator-visible acceptance is: a new eligible winner yields no more than one deduplicated audit record; a profile mismatch is inconclusive; a true same-input mismatch is traceable and blocks a later rule promotion.

## Task 1: Create the pure audit contract, fixture, and comparison boundaries

**Files:**

- Create: `server/attribute_rule_audit.py`
- Create: `tests/fixtures/attribute-rule-audit-v1.json`
- Create: `tests/attribute_rule_audit_test.py`
- Modify: `tests/gear_attribute_engine_test.py` only if a public result-shape invariant needs one additional assertion

- [x] **Step 1: Write failing pure-contract tests before implementation.**

  Cover the following fixture-driven cases without a database, HTTP client, clock or SimC import:

  1. unchanged active/candidate `profileHash` and `gearHash` produce no intent;
  2. a changed observed `winner` with complete sealed identity/input and a `verified` rule yields one deterministic `pending` intent;
  3. non-observed source, `fixture_only`/missing rule, missing region/realm/name, missing character context, incomplete 15/16-slot canonical input, or missing enhancement identity yields exactly `not_applicable` or `blocked_missing_evidence` and marks `externalFetchAllowed: false`;
  4. reordering candidate rows or equipment slots does not change `canonicalInputSignature` or `auditKey`;
  5. release/manifest/rule/input hash changes change the key; duplicate eligible rows for one rule context are bounded to one deterministic intent per refresh;
  6. a slot/item level/bonus/gem/enchant/stable-effect or race/level mismatch yields `inconclusive_input_mismatch`, never `confirmed_mismatch`;
  7. field equality within the context's declared precision returns `pass`, while only an exact-input field over tolerance returns `confirmed_mismatch` and includes expected/actual/raw/display metadata.

  Example test shape:

  ```python
  intents = build_winner_audit_intents(
      active_winners=fixture["activeWinners"],
      candidate_rows=fixture["candidateRows"],
      candidate_context=fixture["candidateContext"],
      rulebook=fixture["verifiedRulebook"],
  )
  self.assertEqual([row["status"] for row in intents], ["pending"])
  self.assertTrue(intents[0]["externalFetchAllowed"])
  self.assertTrue(intents[0]["auditKey"].startswith("attribute-audit:sha256:"))
  ```

- [x] **Step 2: Run the new test to prove the RED state.**

  Run:

  ```bash
  python3 -m unittest -q tests.attribute_rule_audit_test
  ```

  Expected: import/module failures or assertion failures for the absent contract functions. Record this only in the implementation evidence, not as a completion result.

- [x] **Step 3: Implement one pure, bounded module.**

  In `server/attribute_rule_audit.py`, expose and document these narrow functions:

  ```text
  ATTRIBUTE_RULE_AUDIT_SCHEMA_REVISION = winner-attribute-rule-audit-v1
  canonical_input_signature(audit_input) -> sha256 signature
  audit_key(intent) -> attribute-audit:sha256 signature
  build_winner_audit_intents(active_winners, candidate_rows, candidate_context, rulebook) -> ordered audit records
  match_official_profile(sealed_input, official_profile) -> match report
  compare_attribute_panel(rule, expected, observed) -> terminal comparison report
  ```

  Normalize only already-sealed structured fields. `canonical_input_signature()` must include class, spec, race, level, canonical 15/16 slot map, item instance/item level, bonus IDs, gems, enchants, stable effects, resolver/static attribute signature, and rule revision. Use canonical JSON (`sort_keys=True`, compact separators) and `sha256`; never include source display strings or credentials.

  `build_winner_audit_intents()` must select only `role == "winner"` rows from allowed observed source keys, compare by class/spec against active winners, retain the deterministic first eligible context after sorting, and return terminal no-fetch records for evidence/rule gaps. It must not silently drop a blocked/new eligible candidate.

  `match_official_profile()` must return a structured match report before any calculator comparison:

  The report has `status` (`matched` or `inconclusive_input_mismatch`), a bounded `mismatches` list, and bounded official-capture identity fields.

  `compare_attribute_panel()` must flatten primary, stamina, resource and secondary rows into keyed values. For every secondary, retain `rawRating`, `displayValue`, `displayUnit` and rule precision. It must compare non-combat values only and return one of `pass` / `confirmed_mismatch`; it must reject an unmatched input instead of comparing it.

- [x] **Step 4: Run focused regression checks.**

  Run:

  ```bash
  python3 -m unittest -q tests.attribute_rule_audit_test tests.gear_attribute_engine_test tests.gear_attribute_rules_test
  ```

  Expected: all tests pass; no test starts an HTTP request, opens a database, imports SimC, or alters an existing engine result.

## Task 2: Add a durable PostgreSQL audit ledger and fenced repository

**Files:**

- Create: `server/migrations/postgres/0016_websim_attribute_rule_audits.sql`
- Create: `server/attribute_rule_audit_store.py`
- Create: `tests/attribute_rule_audit_store_test.py`
- Modify: `tests/postgres_schema_test.py`

- [x] **Step 1: Write failing repository/migration tests.**

  Tests must assert all of the following before store code exists:

  - migration `0016` declares `ops.websim_attribute_rule_audits`, valid status checks, a single immutable `audit_key`, bounded JSON columns, Release/Manifest foreign keys, queue/claim indexes and least-privilege grants;
  - enqueue is idempotent for the same key and cannot replace a prior terminal result;
  - claim uses one transaction with `FOR UPDATE SKIP LOCKED`, lease token fencing and bounded attempt reclaim;
  - only the matching running lease can complete a record; terminal records cannot be reopened by a duplicate intent;
  - health summary returns bounded counts/latest terminal finding and never returns full input JSON/source identity.

- [x] **Step 2: Run the RED checks.**

  ```bash
  python3 -m unittest -q tests.attribute_rule_audit_store_test tests.postgres_schema_test
  ```

  Expected: failures reference the absent `0016` migration/store methods.

- [x] **Step 3: Define the audit ledger in `0016_websim_attribute_rule_audits.sql`.**

  Use one append-preserving operational table rather than overloading `cache.websim_sync_state`:

  ```sql
  CREATE TABLE IF NOT EXISTS ops.websim_attribute_rule_audits (
      audit_key text PRIMARY KEY CHECK (audit_key ~ '^attribute-audit:sha256:[0-9a-f]{64}$'),
      candidate_community_release_id text NOT NULL REFERENCES cache.websim_release_registry(release_id),
      candidate_gear_release_id text NOT NULL REFERENCES cache.websim_release_registry(release_id),
      manifest_revision text NOT NULL REFERENCES cache.websim_season_manifests(manifest_revision),
      attribute_rule_revision text NOT NULL,
      context_key text NOT NULL,
      status text NOT NULL CHECK (status IN (
          'pending', 'running', 'not_applicable', 'blocked_missing_evidence',
          'blocked_source_unavailable', 'inconclusive_input_mismatch', 'pass', 'confirmed_mismatch'
      )),
      canonical_input_signature text NOT NULL CHECK (canonical_input_signature ~ '^sha256:[0-9a-f]{64}$'),
      input_json jsonb NOT NULL CHECK (octet_length(input_json::text) <= 131072),
      result_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (octet_length(result_json::text) <= 65536),
      attempt integer NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 3),
      locked_by text NOT NULL DEFAULT '', lock_token text NOT NULL DEFAULT '', lease_until timestamptz,
      queued_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, finished_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CHECK ((status = 'running' AND locked_by <> '' AND lock_token <> '' AND lease_until IS NOT NULL)
          OR (status <> 'running' AND lease_until IS NULL))
  );
  ```

  Add a `pending` claim index `(status, queued_at, audit_key)`, a terminal finding index `(attribute_rule_revision, status, finished_at DESC)`, revoke `DELETE` from `wow_app`, grant only `SELECT, INSERT, UPDATE`, and register `0016` in `ops.schema_migrations`. Do not create triggers that update public rules, Releases, Manifests or cache entries.

- [x] **Step 4: Implement `AttributeRuleAuditStore` as the sole SQL owner.**

  Mirror the narrow, testable transactional conventions in `server/gear_stat_snapshot_store.py`, but do not reuse its request queue or health semantics:

  ```text
  AttributeRuleAuditStore.enqueue_intents(intents, now) -> inserted/reused/terminal counts
  AttributeRuleAuditStore.claim_next(worker_id, lock_token, now, lease_seconds=90) -> fenced record or empty object
  AttributeRuleAuditStore.finish(audit_key, lock_token, outcome, now) -> stored terminal record
  AttributeRuleAuditStore.health_summary(now) -> bounded status counts and finding contexts
  ```

  Validate the `attribute-audit:sha256:` key, permitted status transition and bounded payloads before SQL. `enqueue_intents()` inserts `pending`, `not_applicable`, or `blocked_missing_evidence`; an `ON CONFLICT DO NOTHING` must preserve the original capture/result. `claim_next()` only claims `pending`; it may reclaim an expired `running` record up to three attempts and otherwise terminalizes as `blocked_source_unavailable` with a bounded code. `finish()` accepts only the four worker outcomes (`blocked_source_unavailable`, `inconclusive_input_mismatch`, `pass`, `confirmed_mismatch`) and requires the lease token.

- [x] **Step 5: Run focused storage checks.**

  ```bash
  python3 -m unittest -q tests.attribute_rule_audit_store_test tests.postgres_schema_test
  git diff --check
  ```

  Expected: all focused tests pass, migration syntax/string constraints are covered, and the diff has no whitespace errors.

## Task 3: Emit audit intents only after a sealed Release/Manifest decision

**Files:**

- Modify: `server/gear_release_refresh.py`
- Modify: `tests/gear_release_refresh_test.py`
- Modify: `tests/attribute_rule_audit_test.py`

- [x] **Step 1: Add failing orchestration tests around the existing `FakeStore`.**

  Assert that:

  - no audit-intent writer is called before `seal_manifest()` or `seal_manifest_and_compare_and_swap_pointer()` succeeds;
  - auto-promote and manually sealed candidates may enqueue internal intent, but failed/lease-conflict refreshes do not;
  - a writer exception is recorded only as a bounded `attributeRuleAudit` detail in the completed refresh event and does not change `status`, pointer, Manifest or `decision`;
  - no audit adapter/HTTP/SimC callback is accepted by or invoked from `run_release_refresh()`;
  - existing release-refresh result payload stays backward compatible except for a bounded additive audit summary.

- [x] **Step 2: Run the RED check.**

  ```bash
  python3 -m unittest -q tests.gear_release_refresh_test tests.attribute_rule_audit_test
  ```

  Expected: the new injection/ordering assertions fail before the refresh wiring exists.

- [x] **Step 3: Add a fail-open intent seam after sealing.**

  Extend `run_release_refresh()` with optional injected collaborators, never a network client:

  Add keyword-only `audit_intent_writer=None` and `attribute_rulebook_loader=None` to the existing `run_release_refresh()` signature. Immediately after the existing decision plus `seal_manifest()` or pointer-CAS call, invoke `enqueue_sealed_winner_audits()` with the writer, rulebook loader, `candidate["activeWinners"]`, `candidate["candidateRows"]`, `sealed_candidate_context`, and `now`. `sealed_candidate_context` contains the exact sealed gear/community release IDs, resulting Manifest revision, candidate rule revision and release decision.

  Build candidate input only from the sealed candidate row (`selectionIntent`, import evidence, evidence/source refs, resolved/static facts) and the sealed Manifest/release descriptors. The helper calls Task 1's pure planner, then the store writer. It must catch and bound operational write errors as `{"status": "unavailable", "code": "ATTRIBUTE_AUDIT_INTENT_WRITE_FAILED"}` while leaving the Release result untouched.

  In `_run_from_environment()`, instantiate `AttributeRuleAuditStore` from the same PostgreSQL connection factory, pass `store.enqueue_intents`, and pass an explicit fail-closed published-rulebook loader. Until the production rulebook exists, that loader must return the existing empty/unavailable rulebook; this creates `not_applicable` evidence only and prevents any external fetch.

- [x] **Step 4: Run Release and contract regression checks.**

  ```bash
  python3 -m unittest -q tests.gear_release_refresh_test tests.gear_release_store_test tests.attribute_rule_audit_test
  ```

  Expected: all pass; a simulated ledger write failure leaves candidate promotion/manual sealing and recorded Release status unchanged.

## Task 4: Add the independent official-profile audit worker and post-refresh service trigger

**Files:**

- Create: `server/attribute_rule_audit_source.py`
- Create: `server/attribute_rule_audit_worker.py`
- Create: `server/wow-attribute-rule-audit.service`
- Create: `tests/attribute_rule_audit_worker_test.py`
- Modify: `server/wow-gear-release-refresh.service`
- Modify: `tests/deploy-script.test.js`

- [x] **Step 1: Write failing worker tests using fake store/source/calculator collaborators.**

  Cover this exact sequence:

  1. no pending record exits successfully without obtaining OAuth or calling a profile endpoint;
  2. a `not_applicable`/blocked record is never claimed/fetched;
  3. source timeout/404/credential absence is `blocked_source_unavailable`, with no secrets or raw response in result/log-safe output;
  4. a profile whose canonical input differs is `inconclusive_input_mismatch` and does not call `calculate_noncombat_attributes()`;
  5. only matched input calls `applicable_attribute_rule()` plus `calculate_noncombat_attributes()` and writes `pass` or `confirmed_mismatch`;
  6. one worker invocation processes the configured small maximum (default `1`, hard maximum `3`), respects lease fencing, never imports/starts SimC, and returns a bounded JSON summary.

- [x] **Step 2: Run the RED check.**

  ```bash
  python3 -m unittest -q tests.attribute_rule_audit_worker_test
  ```

  Expected: absent source/worker modules cause the intended failures.

- [x] **Step 3: Implement a source adapter with no persistence authority.**

  `server/attribute_rule_audit_source.py` must wrap, not duplicate, `get_blizzard_access_token()` and `blizzard_get()` from `server/websim_payload.py`. It accepts only normalized `{region, realmSlug, characterName, locale}` identity from a claimed intent and requests the official profile/equipment/stat resources needed for the match. Return a normalized structured snapshot; redact/omit token, authorization header and unbounded upstream body from exceptions and summaries.

  The adapter entry point is `fetch_official_profile(identity) -> normalized profile snapshot`. It raises `AttributeAuditSourceUnavailable` with a stable public-safe code, never derives identity from URL/title text, and never writes a catalog row.

- [x] **Step 4: Implement the one-shot worker.**

  `server/attribute_rule_audit_worker.py` should parse `--json`, construct `AttributeRuleAuditStore`, claim one job at a time, call the Task 1 matcher before any arithmetic, and finish through the store's lease token. Reuse the sealed rule snapshot/revision from the intent rather than reading mutable candidate rows at execution time. Inject `source_fetcher`, `matcher`, `calculator` and `now` for tests.

  The success path is deliberately ordered:

  ```text
  claim pending intent
  -> fetch official profile read-only
  -> exact canonical input match
  -> sealed verified rule lookup + deterministic calculator
  -> field comparison
  -> fenced terminal ledger write
  ```

  No status in this worker is public readiness. Its `confirmed_mismatch` result is an internal finding only.

- [x] **Step 5: Add a detached systemd service.**

  Use `OnSuccess=wow-attribute-rule-audit.service` in `server/wow-gear-release-refresh.service` so systemd schedules the independent audit only after a successful refresh; it must not be an `ExecStart`/`ExecStartPost` child of the refresh process. Create `server/wow-attribute-rule-audit.service` with:

  ```ini
  [Unit]
  Description=Read-only WOW winner attribute-rule audit
  After=network-online.target postgresql.service mihomo.service
  Wants=network-online.target mihomo.service

  [Service]
  Type=oneshot
  User=ubuntu
  WorkingDirectory=/opt/wow-mini-program
  EnvironmentFile=-/etc/wow-backend.env
  Environment=WOW_DATABASE_RUNTIME=postgres_only
  Environment=WOW_ATTRIBUTE_RULE_AUDIT_MAX_JOBS=1
  # full upper/lower-case mihomo proxy and NO_PROXY set, matching other external-source units
  ExecStart=/usr/bin/flock -n /run/lock/wow-attribute-rule-audit.lock /usr/bin/python3 /opt/wow-mini-program/server/attribute_rule_audit_worker.py --json
  TimeoutStartSec=5min
  NoNewPrivileges=true
  PrivateTmp=true
  ProtectHome=read-only
  ProtectSystem=strict
  ReadWritePaths=/run/lock
  ```

  Do **not** add a timer and do **not** start this service on deploy: its durable queue is created only after an election and `OnSuccess` provides the daily trigger. Extend deploy-script tests to require proxy configuration, installed unit file, the `OnSuccess` relationship and absence of deploy-triggered start.

- [x] **Step 6: Run worker/unit regression checks.**

  ```bash
  python3 -m unittest -q tests.attribute_rule_audit_worker_test tests.attribute_rule_audit_store_test tests.gear_release_refresh_test
  node --test tests/deploy-script.test.js
  ```

  Expected: all pass; tests demonstrate that audit worker failure cannot fail the release refresh and that the external-source worker has proxy/lock/sandbox coverage.

## Task 5: Project bounded audit truth into health/admin and future rule promotion gates

**Files:**

- Modify: `server/news_backend.py`
- Modify: `server/gear_attribute_rules.py`
- Create: `tests/attribute_rule_audit_health_test.py`
- Modify: `tests/news_backend_test.py`
- Modify: `tests/gear_attribute_rules_test.py`

- [x] **Step 1: Add failing health and promotion-gate tests.**

  Required cases:

  - missing ledger reader is a truthful `blocked` component, not a backend failure;
  - no audit yet / only `not_applicable` is `partial` or `verified` according to the explicit details contract, never a false rule verification;
  - source unavailable/inconclusive data does not make `/api/data/health` globally block normal gear/template use;
  - `confirmed_mismatch` appears as a bounded internal finding count + rule revision/context, omits source identity/full equipment, and prevents validation/promotion of a **new** rulebook carrying that revision;
  - an existing published rule remains returned unchanged until a separately explicit rule revision/feature-hide action occurs;
  - public `attributeCalculator` output and mini-program local context do not gain a dependency on audit liveness.

- [x] **Step 2: Run the RED check.**

  ```bash
  python3 -m unittest -q tests.attribute_rule_audit_health_test tests.news_backend_test tests.gear_attribute_rules_test
  ```

  Expected: failures show the absent component/gate; do not weaken existing rulebook validation to make tests pass.

- [x] **Step 3: Implement bounded health projection and a future-promotion guard.**

  Follow the existing `gear_stat_snapshot_health_component()` shape in `server/news_backend.py` with a new `attribute_rule_audit_data_store()` factory and `attribute_rule_audit_health_component()`. Details may include only:

  ```text
  queue: pending/running counts
  terminalCounts: pass/confirmedMismatch/inconclusive/sourceUnavailable counts
  latestCheckedAt: latest terminal audit timestamp
  findingRuleContexts: bounded {attributeRuleRevision, contextKey} entries only
  trigger: {unit: wow-gear-release-refresh.service, onSuccessUnit: wow-attribute-rule-audit.service}
  ```

  Add the component to both PostgreSQL-only and compatible health payload paths. `confirmed_mismatch` should make the component `blocked`, but overall data health must retain the normal Release/template component truth rather than rewriting it.

  Add a narrowly injected `promotion_findings_reader` to the *future rule publication/validation* seam in `gear_attribute_rules.py`; it defaults to no findings for current public calculation. If the reader declares a matching confirmed mismatch, return an explicit validation issue such as `ATTRIBUTE_RULE_AUDIT_MISMATCH_BLOCKS_PROMOTION`. Do not import database code into the pure rule validator, and do not change `applicable_attribute_rule()` behavior for already published rules.

- [x] **Step 4: Run focused health/contract tests.**

  ```bash
  python3 -m unittest -q tests.attribute_rule_audit_health_test tests.news_backend_test tests.gear_attribute_rules_test tests.gear_attribute_api_test
  ```

  Expected: all pass; API tests prove public calculation remains fail-closed and independent of audit worker state.

## Task 6: Wire migration/deploy safety, update the Harness packet, and prove candidate behavior

**Files:**

- Modify: `server/deploy_lighthouse.sh`
- Modify: `tests/deploy-script.test.js`
- Modify: `artifacts/releases/2026-07-17-real-time-gear-stat-engine/requirement.json`
- Create: `artifacts/releases/2026-07-17-real-time-gear-stat-engine/evidence/winner-attribute-rule-audit-candidate.json`
- Modify: `docs/roadmap.md`
- Modify: `docs/gear-simulation-full-chain-runbook.md`
- Modify: `docs/builds-architecture.md`

- [x] **Step 1: Add failing deploy/document contract tests.**

  Extend the Node deploy tests to require copying `wow-attribute-rule-audit.service`, preserving all external-source proxy settings, and never enabling/starting it directly on deployment. Extend Harness/document tests only where an existing machine-readable contract validates release evidence fields.

- [x] **Step 2: Run the RED check.**

  ```bash
  node --test tests/deploy-script.test.js tests/project-harness.test.js
  ```

  Expected: missing unit installation and evidence contract assertions fail before the wiring/document updates.

- [x] **Step 3: Make deployment additive and dormant.**

  `server/deploy_lighthouse.sh` copies the service unit and runs `daemon-reload`, but must not issue `enable --now`, `start`, an external query, a winner refresh or any SimC command for this service. The next successful scheduled Release refresh remains the first possible trigger.

  Update the requirement packet with the new owner, data/timer/health implications and explicit no-impact claim. Update the roadmap/runbook/architecture docs to distinguish:

  - immediate local attribute display (player-critical);
  - asynchronous winner audit (operator evidence only);
  - SimC simulation/stat snapshot (separate performance/complex-effect path).

  Record candidate evidence only after the actual candidate run; do not prefill live values or call a test fixture “official confirmation.”

- [x] **Step 4: Run final local verification before candidate deployment.**

  ```bash
  python3 -m unittest -q \
    tests.attribute_rule_audit_test \
    tests.attribute_rule_audit_store_test \
    tests.attribute_rule_audit_worker_test \
    tests.attribute_rule_audit_health_test \
    tests.gear_release_refresh_test \
    tests.gear_attribute_rules_test \
    tests.gear_attribute_engine_test \
    tests.gear_attribute_api_test \
    tests.postgres_schema_test \
    tests.news_backend_test
  node --test tests/deploy-script.test.js tests/project-harness.test.js
  node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-17-real-time-gear-stat-engine --base origin/main
  git diff --check
  ```

  Expected: all targeted checks plus the single final Harness full profile pass. Do not claim live behavior from these local tests.

- [ ] **Step 5: Run one final-commit candidate deployment and smoke.**

  On the candidate branch/commit only, first capture the commit SHA and a recoverable PostgreSQL backup. Apply migration `0016` atomically, verify `ops.schema_migrations`, table constraints/indexes/grants, deploy with `WOW_DEPLOY_START_ASYNC_SYNCS=0`, and verify file/unit parity.

  Candidate smoke must demonstrate:

  1. the regular gear Release service can finish/publish a candidate without waiting on the audit service;
  2. an eligible changed winner creates at most one ledger intent, while unchanged/missing evidence creates no external fetch;
  3. a deliberately unavailable official source records `blocked_source_unavailable` but leaves Release/Manifest/winner unchanged;
  4. an exact fixture/profile match creates `pass`; an equipment mismatch creates `inconclusive_input_mismatch`; a controlled same-input field mismatch creates `confirmed_mismatch` in the internal ledger;
  5. `/api/data/health` exposes only the bounded audit summary; `/api/websim/gear` and the mini-program immediate attribute calculation remain responsive if the audit service is stopped;
  6. `systemctl stop wow-attribute-rule-audit.service` plus a subsequent refresh leaves player-visible import/switch behavior normal, establishing rollback by disablement; database rows remain as audit history.

  Write only verified command outputs, SHA, migration identity, unit status, API results, timing trace, rollback result and known limitations into `winner-attribute-rule-audit-candidate.json`.

## Task 7: Local CR, acceptance, merge closure, and post-merge parity

**Files:**

- Modify: `artifacts/releases/2026-07-17-real-time-gear-stat-engine/evidence/winner-attribute-rule-audit-candidate.json` only with real post-merge evidence, if candidate evidence is still current
- Modify: `docs/roadmap.md` only to record actual status/evidence after results exist

- [ ] **Step 1: Perform the required local CR against the implementation plan.**

  Inspect the final diff for these high-risk findings:

  - a network call, worker wait, audit status or SimC call has entered any resolver/API/page/gear-change path;
  - an audit result can mutate a Release, winner, Manifest pointer or existing public rule;
  - identity/input matching allows missing slot, bonus, gem, enchant, race, level, rule revision or source identity;
  - health leaks character identity/full payload or turns ordinary `blocked`/`inconclusive` into a player-facing dependency;
  - migration grants deletion/unbounded JSON/rewrite behavior or deploy starts the worker eagerly.

  Re-run the smallest affected test command for each finding fixed, then rerun the final Task 6 verification set.

- [ ] **Step 2: Wait for explicit user acceptance after candidate/manual verification.**

  Do not merge merely because the user approved the design or this plan. The required closure signal is an explicit post-test acceptance such as `我已测试通过`, `可以收尾`, or `合入吧`.

- [ ] **Step 3: On explicit closure, follow the repository Harness sequence.**

  Commit the task branch, sync/merge `main` without history rewrite, rerun the scoped verification on merge result, push `main`, compare local and `origin/main` SHA, and remove the task branch/worktree only if no conflict/failed verification/scope expansion occurs. Record the actual evidence links/status; never write a fictitious “live” result.

## Plan Coverage Review

- Every outcome from the approved design has an owner: pure contract (`Task 1`), ledger (`Task 2`), Release boundary (`Task 3`), external worker (`Task 4`), health/future promotion gate (`Task 5`), candidate/deploy (`Task 6`).
- The two must-not-change user promises are tested explicitly: no player path waits for audit, and no audit result changes winner/Release/Manifest/SimC behavior.
- Current runtime lacks a production verified rulebook; this plan intentionally produces `not_applicable` rather than fabricating formulas or silent external traffic. Enabling an actual rule context remains a later source-ledger/rule-publication change and will reuse the same audited contract.
- The plan does not contain placeholder actions: every task names files, tests, interfaces, state transitions and expected verification output.
