# Data Loading Performance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce user-visible data loading latency for the mini-program WebSim/build pages and the admin gate console without weakening the existing fail-closed data trust boundaries.

**Architecture:** Treat this as a read-path optimization, not a data-rule rewrite. First remove wasted transfer and repeated work, then make PostgreSQL the real hot read path for WebSim gear, then split large payloads so the first screen only loads what it can display immediately. Expensive evidence audits remain available, but they must be cached, async, or explicitly requested instead of running on default health/admin loads.

**Tech Stack:** Python `http.server` backend in `server/news_backend.py`, PostgreSQL cache runtime in `server/postgres_cache_store.py`, SQLite fallback in `server/websim_payload.py`, nginx deployment template in `server/deploy_lighthouse.sh`, WeChat mini-program JS in `pages/builds/*`, Python `unittest`, Node `node --test`.

## Current Baseline

Measured on 2026-07-01 against `http://124.223.51.33`:

- Public `/api/websim/gear?class=mage&spec=frost&compact=1`: p50 `2.43s`, server loopback p50 `1.22s`, raw `1,073,947` bytes.
- Public `/api/websim/talents?class=mage&spec=frost&hero=spellslinger`: p50 `0.50s`, server loopback p50 `0.09s`, raw `414,636` bytes.
- Public `/api/data/health`: p50 `13.5s`, full local profile showed default template evidence audit can take `55s`.
- Admin loopback `/api/admin/gates/summary`: p50 `4.5s`.
- Admin loopback `/api/admin/gates/queue?limit=80`: p50 `4.2s`.
- Admin loopback `/api/admin/gates/records?domain=gear&page=1&pageSize=20`: p50 `2.0s`.
- Admin loopback `/api/admin/gates/records?domain=gear_templates&page=1&pageSize=20`: p50 `1.6s`.

Key evidence from profiling:

- `PostgresCacheStore.get_websim_gear("mage", "frost", compact=True)` currently returns `dataStatus=blocked` because `cache.websim_season_state.expires_at` is stale, so `runtime_websim_gear_payload()` falls back to SQLite and spends `1.1-1.6s` building the compact gear payload.
- Gear SQL itself is not the bottleneck: the variants query explain was about `67ms`; most time is JSON decoding plus Python compatibility/readiness shaping.
- `admin_gate_summary_payload()` calls `admin_gate_queue_payload()`, and the page also calls queue separately. Queue builds all records. Gear and gear_templates both invoke `PostgresCacheStore.admin_gate_gear_records()`, so gear variants are queried/decoded even when only 65 gear templates are needed.
- `json_response()` and nginx currently return uncompressed JSON. Local gzip estimates: gear compact `1,073,947 -> 77,162` bytes, talents `414,636 -> 39,099`, data health `262,064 -> 17,570`.

## Target SLO

- Mini-program common first screens: p50 below `800ms`, p95 below `1.5s`.
- Mini-program gear switch by class/spec: p50 below `800ms`; initial gear JSON below `300KB` raw and below `100KB` compressed.
- Admin gate console HTML: below `300ms`.
- Admin summary and queue: p50 below `1s`.
- Admin single-domain records: p50 below `500ms`.
- Default `/api/data/health`: below `1s`. Full template evidence audit is allowed to be slower only behind explicit `?audit=1` or a dedicated detail endpoint.

## Non-Goals

- Do not change evidence semantics, SimC readiness, publication gates, or fail-closed behavior.
- Do not silently treat stale PG data as verified.
- Do not remove the SQLite fallback until PG public/cache read parity is verified.
- Do not make admin-only logic diverge from mini-program-visible read models.

## Task 1: Add A Repeatable Performance Probe

**Files:**
- Create: `scripts/perf_probe.py`
- Modify: `docs/plans/2026-07-01-data-loading-performance-design.md`
- Test: no unit test required; this is an operator script with deterministic output.

**Step 1: Create the probe script**

Create `scripts/perf_probe.py` with endpoints matching the baseline:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import subprocess


PUBLIC_ENDPOINTS = [
    ("health", "/health"),
    ("builds_home", "/api/builds/home"),
    ("news_home", "/api/news/home"),
    ("data_health", "/api/data/health"),
    ("websim_bootstrap", "/api/websim/bootstrap"),
    ("websim_gear_initial", "/api/websim/gear?class=mage&spec=frost&compact=1&mode=initial"),
    ("websim_gear_slot_head", "/api/websim/gear?class=mage&spec=frost&compact=1&mode=slot&slot=head"),
    ("websim_talents", "/api/websim/talents?class=mage&spec=frost&hero=spellslinger"),
]


def curl_once(base_url: str, path: str) -> tuple[int, float, int]:
    output = subprocess.check_output(
        [
            "curl",
            "-sS",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code} %{time_total} %{size_download}",
            f"{base_url.rstrip('/')}{path}",
        ],
        text=True,
    ).strip()
    code, elapsed, size = output.split()
    return int(code), float(elapsed), int(size)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://124.223.51.33")
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    rows = []
    for name, path in PUBLIC_ENDPOINTS:
        results = [curl_once(args.base_url, path) for _ in range(args.repeat)]
        rows.append(
            {
                "name": name,
                "code": results[-1][0],
                "p50Seconds": statistics.median(item[1] for item in results),
                "maxSeconds": max(item[1] for item in results),
                "bytes": results[-1][2],
            }
        )
    print(json.dumps({"baseUrl": args.base_url, "repeat": args.repeat, "rows": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Step 2: Run the probe**

Run:

```bash
python3 scripts/perf_probe.py --repeat 2
```

Expected: JSON output with `code=200` for public endpoints.

**Step 3: Use this script as before/after evidence**

Run before optimization, after local changes, and after deploy smoke. Do not turn this into a strict unit test because live network timing is variable.

## Task 2: Enable JSON Compression

**Files:**
- Modify: `server/news_backend.py:9809`
- Modify: `server/deploy_lighthouse.sh:453`
- Test: `tests/news_backend_test.py`
- Test: `tests/deploy-script.test.js`

**Step 1: Write backend gzip tests**

Add tests around the HTTP server in `tests/news_backend_test.py`:

```python
def test_json_response_gzips_large_json_when_client_accepts_gzip(self):
    server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/websim/bootstrap",
            headers={"Accept-Encoding": "gzip"},
        )
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.headers.get("Content-Encoding"), "gzip")
            body = gzip.decompress(response.read())
            self.assertIn(b"classes", body)
    finally:
        server.shutdown()
        thread.join(timeout=2)
```

Expected red result before implementation: `Content-Encoding` is missing.

**Step 2: Implement gzip in `json_response()`**

In `server/news_backend.py`, update `json_response()` so it compresses JSON only when:

- `Accept-Encoding` contains `gzip`
- body is larger than a small threshold, for example `1024` bytes

Implementation shape:

```python
import gzip


def client_accepts_gzip(handler):
    return "gzip" in str(handler.headers.get("Accept-Encoding", "")).lower()


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    should_gzip = len(body) >= 1024 and client_accepts_gzip(handler)
    output = gzip.compress(body, compresslevel=6) if should_gzip else body
    try:
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        if should_gzip:
            handler.send_header("Content-Encoding", "gzip")
            handler.send_header("Vary", "Accept-Encoding")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Wow-Client-Id, X-Wow-Session-Id, X-Wow-Platform")
        handler.send_header("Content-Length", str(len(output)))
        handler.end_headers()
        handler.wfile.write(output)
        return True
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        return False
```

**Step 3: Add nginx gzip template**

In `server/deploy_lighthouse.sh`, inside the generated `server {}` block, add gzip for proxied JSON:

```nginx
    gzip on;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_types application/json text/plain text/css application/javascript;
    gzip_vary on;
```

The backend gzip is still useful for direct loopback and tests. nginx gzip covers deployment if backend compression is bypassed or future static JSON is added.

**Step 4: Verify**

Run:

```bash
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_json_response_gzips_large_json_when_client_accepts_gzip -v
node --test tests/deploy-script.test.js
python3 -m py_compile server/news_backend.py
git diff --check
```

Expected: tests pass and `curl -H 'Accept-Encoding: gzip' -I /api/websim/gear?...` shows `Content-Encoding: gzip`.

## Task 3: Make Default Data Health Lightweight

**Files:**
- Modify: `server/news_backend.py:10016`
- Modify: `server/news_backend.py:2329`
- Test: `tests/news_backend_test.py`

**Step 1: Write failing tests**

Add tests:

```python
def test_data_health_route_skips_template_evidence_audit_by_default(self):
    with patch.object(self.backend, "build_data_health_payload", wraps=self.backend.build_data_health_payload) as wrapped:
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/api/data/health", timeout=5) as response:
                self.assertEqual(response.status, 200)
            self.assertEqual(wrapped.call_args.kwargs.get("include_template_evidence_audit"), False)
        finally:
            server.shutdown()
            thread.join(timeout=2)


def test_data_health_route_allows_explicit_template_evidence_audit(self):
    with patch.object(self.backend, "build_data_health_payload", wraps=self.backend.build_data_health_payload) as wrapped:
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/api/data/health?audit=1", timeout=5) as response:
                self.assertEqual(response.status, 200)
            self.assertEqual(wrapped.call_args.kwargs.get("include_template_evidence_audit"), True)
        finally:
            server.shutdown()
            thread.join(timeout=2)
```

Expected red result: route currently calls `build_data_health_payload()` with default `True`.

**Step 2: Implement query-gated audit**

In the route:

```python
if path == "/api/data/health":
    include_audit = str(query.get("audit", [""])[0]).lower() in {"1", "true", "yes"}
    json_response(self, 200, build_data_health_payload(include_template_evidence_audit=include_audit))
    return
```

Keep `admin_gate_summary_payload()` using `include_template_evidence_audit=False`.

**Step 3: Verify**

Run:

```bash
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_data_health_route_skips_template_evidence_audit_by_default tests.news_backend_test.NewsBackendTest.test_data_health_route_allows_explicit_template_evidence_audit -v
python3 -m py_compile server/news_backend.py
git diff --check
```

Expected: default `/api/data/health` no longer invokes the 40-spec evidence audit.

## Task 4: Stop Admin Summary And Queue From Rebuilding Heavy Records Twice

**Files:**
- Modify: `server/news_backend.py:8610`
- Modify: `server/news_backend.py:8677`
- Test: `tests/news_backend_test.py`

**Step 1: Write failing test for summary avoiding full queue rebuild**

Add a test that patches `admin_gate_queue_payload` and verifies summary no longer delegates to it:

```python
def test_admin_gate_summary_uses_lightweight_queue_summary(self):
    with patch.object(self.backend, "admin_gate_queue_payload", side_effect=AssertionError("summary must not build full queue")):
        payload = self.backend.admin_gate_summary_payload()
    self.assertIn("queueSummary", payload)
    self.assertNotIn("items", payload["queueSummary"])
```

Expected red result: current summary calls `admin_gate_queue_payload({"limit": ["25"]})`.

**Step 2: Add lightweight queue summary**

Add:

```python
def admin_gate_queue_summary_payload(records=None):
    records = records if records is not None else collect_admin_gate_records_from_runtime_stores({"limit": ["200"]})
    if records is None:
        init_db()
        with db_connection() as conn:
            records = collect_admin_gate_records(conn, {"limit": ["200"]})
    counts = {}
    top_blockers = {}
    total = 0
    for record in records:
        if admin_gate_record_passed(record):
            continue
        if record.get("status") not in ADMIN_GATE_QUEUE_STATUSES and not record.get("blockers"):
            continue
        total += 1
        domain = record.get("domain") or "unknown"
        counts[domain] = counts.get(domain, 0) + 1
        for blocker in record.get("blockers") or []:
            text = str(blocker or "").strip()
            if text:
                top_blockers[text] = top_blockers.get(text, 0) + 1
    return {
        "count": total,
        "domainCounts": counts,
        "topBlockers": [
            {"reason": reason, "count": count}
            for reason, count in sorted(top_blockers.items(), key=lambda item: (-item[1], item[0]))[:8]
        ],
    }
```

Then in `admin_gate_summary_payload()`, use this lightweight payload and avoid returning queue items.

**Step 3: Avoid duplicate queue load on overview**

In the admin page script, change `refreshAdminGates()` so overview loads summary only, and queue/diagnoses are loaded only when their views are active:

```javascript
async function refreshAdminGates() {
  try {
    clearAdminGateError();
    const tasks = [loadSummary()];
    if (adminGateShowsRecords()) tasks.push(loadRecords());
    if (currentAdminGateNav === 'queue') tasks.push(loadQueue());
    if (currentAdminGateNav === 'diagnoses') tasks.push(loadDiagnoses());
    await Promise.all(tasks);
    document.getElementById('adminGateMessage').textContent = '已加载线上门禁数据。';
  } catch (error) {
    showAdminGateError(error.message || String(error));
  }
}
```

**Step 4: Verify**

Run:

```bash
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_admin_gate_summary_uses_lightweight_queue_summary -v
python3 -m unittest tests.news_backend_test -v
python3 -m py_compile server/news_backend.py
git diff --check
```

Expected: admin summary no longer blocks on full queue detail construction.

## Task 5: Split Gear Template Admin Store From Gear Variant Store

**Files:**
- Modify: `server/postgres_cache_store.py:865`
- Modify: `server/news_backend.py:7852`
- Modify: `server/news_backend.py:7984`
- Test: `tests/postgres_cache_store_test.py`
- Test: `tests/news_backend_test.py`

**Step 1: Write failing store test**

In `tests/postgres_cache_store_test.py`, add a fake cursor/connection test or extend the existing admin gate cache test to assert that calling the template path does not execute a query against `cache.websim_gear_variants`.

Target behavior:

```python
templates = store.admin_gate_gear_template_records()
self.assertEqual(len(templates["communityGearTemplates"]), 1)
self.assertFalse(any("websim_gear_variants" in sql for sql in executed_sql))
```

Expected red result: there is no separate method; current template collection calls `admin_gate_gear_records()`.

**Step 2: Implement separate methods**

In `server/postgres_cache_store.py`, split:

- `admin_gate_gear_template_records()` only checks/queries `cache.websim_community_gear_templates`.
- `admin_gate_gear_variant_records()` only queries `cache.websim_gear_variants` and item/source data.
- Keep `admin_gate_gear_records()` as a compatibility wrapper returning both, but stop using it from domain-specific admin paths.

**Step 3: Route domain-specific collectors to the narrow methods**

In `server/news_backend.py`:

```python
def collect_admin_gear_template_records_from_store(store):
    if hasattr(store, "admin_gate_gear_template_records"):
        payload = store.admin_gate_gear_template_records()
    else:
        payload = store.admin_gate_gear_records()
    ...


def collect_admin_gear_records_from_store(store):
    if hasattr(store, "admin_gate_gear_variant_records"):
        payload = store.admin_gate_gear_variant_records()
    else:
        payload = store.admin_gate_gear_records()
    ...
```

**Step 4: Verify**

Run:

```bash
python3 -m unittest tests.postgres_cache_store_test tests.news_backend_test -v
python3 -m py_compile server/postgres_cache_store.py server/news_backend.py
git diff --check
```

Expected: gear_templates records no longer decodes all variants.

## Task 6: Fix PG Season Freshness And Stop Silent Slow Fallback

**Files:**
- Modify: `server/postgres_cache_store.py:186`
- Modify: `server/news_backend.py:6020`
- Modify: `server/migrations/postgres/data_copy_plan.py`
- Test: `tests/postgres_cache_store_test.py`
- Test: `tests/news_backend_test.py`

**Step 1: Write failing tests for expired season behavior**

Add a test where `cache.websim_season_state` has `data_status='verified'`, `active=true`, but `expires_at` is in the past. Decide the expected behavior:

- For owner/admin diagnostics, expose `stale` with `dataStatus='stale'`.
- For public gear reads, do not silently fall back to SQLite when PG has public cache tables but the season is stale. Return a compact stale payload with blockers unless an explicit fallback mode is enabled for local development.

Example assertion:

```python
payload = store.get_websim_gear("mage", "frost", compact=True)
self.assertEqual(payload["dataStatus"], "stale")
self.assertIn("season cache expired", payload["catalogBlockers"])
```

Expected red result: current `get_active_season_payload()` returns `{}` and runtime falls back.

**Step 2: Preserve active stale season payload**

In `PostgresCacheStore.get_active_season_payload()`, remove the hard filter `expires_at > now()` from the SQL. After fetching active verified row:

```python
expired = row[6] and row[6] <= now
payload["dataStatus"] = "stale" if expired else row[4]
payload.setdefault("errors", [])
if expired:
    payload["errors"] = [*payload.get("errors", []), "season cache expired"]
```

Do not mark expired data as verified.

**Step 3: Make runtime fallback explicit**

In `runtime_websim_gear_payload()`, only fall back to SQLite when:

- no runtime store exists, or
- runtime store raises an exception before proving cache ownership, or
- an env flag such as `WOW_ALLOW_SQLITE_PUBLIC_CACHE_FALLBACK=1` is set.

If PG store returns a stale/blocked payload, return it with blockers instead of silently doing expensive SQLite work.

**Step 4: Verify public behavior**

Run:

```bash
python3 -m unittest tests.postgres_cache_store_test tests.news_backend_test -v
python3 -m py_compile server/postgres_cache_store.py server/news_backend.py
git diff --check
```

Expected: no silent slow fallback in PG runtime. If production needs data refreshed, run the existing sync/reconcile flow as a deployment operation after approval.

## Task 7: Add Hot In-Memory Cache For PG Gear Payloads

**Files:**
- Modify: `server/postgres_cache_store.py`
- Test: `tests/postgres_cache_store_test.py`

**Step 1: Write failing test for repeated calls**

Add a test that calls `store.get_websim_gear("mage", "frost", compact=True)` twice and asserts the second call does not rerun the full source/variant/mod option queries when the fingerprint is unchanged.

Use a fake connection/cursor or query recorder to assert query count drops on the second call.

**Step 2: Add fingerprint cache**

Add module-level cache:

```python
PG_GEAR_PAYLOAD_CACHE = {}
PG_GEAR_PAYLOAD_CACHE_MAX = 80
```

Fingerprint should include:

- class key
- spec key
- compact boolean
- active season revision
- `gearCatalog` sync state updatedAt/schema revision
- counts/max updated_at for `cache.websim_items`, `cache.websim_gear_sources`, `cache.websim_gear_variants`, `cache.websim_gear_mod_options`, and `cache.websim_community_gear_templates`

Cache only successful payloads with `replacementCandidates` or a clear stale/blocked payload. Do not cache exceptions.

**Step 3: Keep cache scoped to process**

This is acceptable because `wow-backend` is restarted on deploy and sync jobs update `updated_at`/sync state. Do not add Redis or another service.

**Step 4: Verify**

Run:

```bash
python3 -m unittest tests.postgres_cache_store_test -v
python3 -m py_compile server/postgres_cache_store.py
git diff --check
```

Expected: repeated same-spec gear calls become cheap in one process.

## Task 8: Slim Mini-Program Gear First Payload

**Files:**
- Modify: `server/news_backend.py:10137`
- Modify: `server/postgres_cache_store.py:649`
- Modify: `server/websim_payload.py:17928`
- Modify: `pages/builds/websim-api.js:211`
- Modify: `pages/builds/detail.js:4008`
- Test: `tests/websim_payload_test.py`
- Test: `tests/frontend-api-client.test.js`
- Test: `tests/builds-page.test.js`

**Step 1: Add contract test for first payload size/shape**

In `tests/websim_payload_test.py`, assert compact first payload still includes:

- `slots`
- `replacementCandidates` with top candidates per slot
- `equippedSet`
- `slotReadiness`
- `baselineSet`
- `communityTemplates`
- enhancement option summaries needed by the visible page

But it should not include large per-candidate detail rows that are only needed after opening a slot sheet.

**Step 2: Introduce mode parameter**

Add `mode=initial|slot` or `slot=<slot>` to `/api/websim/gear`.

- `mode=initial` returns top N summaries per slot, target raw size below `300KB`.
- `slot=head` returns full candidate details for that slot.
- Existing `compact=1` without mode keeps backward compatibility until the frontend switches.

**Step 3: Update frontend**

In `pages/builds/websim-api.js`:

```javascript
if (options.mode) query.push(`mode=${encodeURIComponent(options.mode)}`)
if (options.slot) query.push(`slot=${encodeURIComponent(options.slot)}`)
```

In `pages/builds/detail.js`:

- Initial page load calls `requestWebsimGear({ classKey, specKey, compact: true, mode: 'initial' })`.
- `openGearSlotSheet()` checks `gearSlotCandidateCache[slot]`; if missing or partial, it calls slot-detail mode before opening or refreshes the sheet once data returns.

**Step 4: Verify**

Run:

```bash
python3 -m unittest tests.websim_payload_test tests.news_backend_test -v
node --test tests/frontend-api-client.test.js tests/builds-page.test.js
python3 -m py_compile server/news_backend.py server/postgres_cache_store.py server/websim_payload.py
git diff --check
```

Expected: first payload is materially smaller while slot sheet still has complete candidates when opened.

## Task 9: Replace Talent Import Lookup With A Small Endpoint

**Files:**
- Modify: `server/news_backend.py`
- Modify: `server/postgres_cache_store.py`
- Modify: `server/websim_payload.py`
- Modify: `pages/builds/websim-api.js`
- Modify: `pages/builds/detail.js:3858`
- Test: `tests/news_backend_test.py`
- Test: `tests/frontend-api-client.test.js`
- Test: `tests/builds-page.test.js`

**Step 1: Write failing API test**

Add a test for:

```text
GET /api/websim/talents/import?class=mage&spec=frost&hero=spellslinger
```

Expected payload:

```json
{
  "classKey": "mage",
  "specKey": "frost",
  "heroKey": "spellslinger",
  "importCode": "websim:...",
  "source": "community_template",
  "status": "verified"
}
```

No `nodes` list. No full `communityTemplates` list.

**Step 2: Implement narrow backend helper**

Reuse the same authority as `get_websim_talents()`, but return only the first SimC-ready community template import code. If unavailable, return `status='blocked'` and blockers.

**Step 3: Update frontend**

Replace `requestWebsimTalents(keys)` inside `loadGearStatsTalentImport()` with `requestWebsimTalentImport(keys)`.

**Step 4: Verify**

Run:

```bash
python3 -m unittest tests.news_backend_test tests.websim_payload_test -v
node --test tests/frontend-api-client.test.js tests/builds-page.test.js
python3 -m py_compile server/news_backend.py server/postgres_cache_store.py server/websim_payload.py
git diff --check
```

Expected: gear page no longer pulls a 415KB talent tree just to get one import code for stat snapshot.

## Task 10: Deploy And Verify Live Performance

**Files:**
- Modify: `docs/roadmap.md`
- Use existing deploy script: `server/deploy_lighthouse.sh`

**Step 1: Run full local verification**

Run:

```bash
python3 -m unittest tests.news_backend_test tests.postgres_cache_store_test tests.websim_payload_test -v
node --test tests/frontend-api-client.test.js tests/builds-page.test.js tests/deploy-script.test.js
python3 -m py_compile server/news_backend.py server/postgres_cache_store.py server/websim_payload.py
git diff --check
```

Expected: pass.

**Step 2: Review diff locally**

Run:

```bash
git diff --stat
git diff -- server/news_backend.py server/postgres_cache_store.py server/websim_payload.py pages/builds/websim-api.js pages/builds/detail.js server/deploy_lighthouse.sh
```

Check:

- No change weakens fail-closed source status.
- PG stale data is labeled stale/blocked, not verified.
- Admin records still match mini-program read model.
- No token or secret printed.

**Step 3: Hot deploy after explicit deploy approval if needed**

If the user asks to deploy, run:

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 ./server/deploy_lighthouse.sh
```

Do not run network installs, git pulls, or dependency installs without explicit approval.

**Step 4: Live smoke**

Run:

```bash
python3 scripts/perf_probe.py --repeat 3
curl -sS -H 'Accept-Encoding: gzip' -D - -o /dev/null 'http://124.223.51.33/api/websim/gear?class=mage&spec=frost&compact=1'
```

Also run server-loopback admin timings:

```bash
ssh ubuntu@124.223.51.33 'python3 /opt/wow-mini-program/scripts/perf_probe.py --base-url http://127.0.0.1:8787 --repeat 3'
```

For admin token endpoints, use a remote script that reads `/etc/wow-backend.env` but never prints the token.

**Step 5: Update roadmap**

Add a top entry to `docs/roadmap.md` with:

- before/after timings
- compressed sizes
- whether PG gear path is hot or intentionally stale/blocked
- backup/deploy path if deployed
- exact verification commands

## Suggested Execution Order

1. Task 2 compression.
2. Task 3 data health default audit gate.
3. Task 4 admin summary/queue duplicate-work reduction.
4. Task 5 admin gear template store split.
5. Task 6 PG season/fallback correctness.
6. Task 7 PG gear cache.
7. Task 8 gear payload split.
8. Task 9 talent import narrow endpoint.
9. Task 10 deploy and roadmap.

The first five tasks should already produce visible wins without changing mini-program UI behavior. Tasks 8 and 9 are the more product-facing contract changes and should be done after backend timing is under control.
