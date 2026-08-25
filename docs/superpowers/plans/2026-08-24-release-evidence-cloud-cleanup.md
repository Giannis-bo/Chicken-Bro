# Release Evidence Cloud Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 S2 文档实际需要的证据发布到不可变云端地址，消除线上运行链路对本地原始产物的误解，并清理本地约 97GB 未跟踪中间产物。

**Architecture:** 在现有 `api.chickenbro.cloud` HTTPS 域名下增加只读的 `/wow-evidence/releases/<release-id>/` 静态目录；发布脚本只接受固定的当前 S2 证据 allowlist，并以不可覆盖的 release id 原子上传。正式 Harness packet 仍保留在 Git 中供 CI 使用，运行时继续从 PostgreSQL/API 读取装备事实，不读取 `artifacts/releases`。

**Tech Stack:** Bash、Nginx、SSH/tar、Node.js 测试、现有 Taro/WOW Harness。

**Spec:** `docs/remote-debugging.md`、`docs/harness.md`、`server/data/midnight-season-2/README.md`、`server/data/midnight-season-2/source-policy.json`。

## Global Constraints

- 常规后端部署继续排除整个 `artifacts/`，不得把本地证据目录打进线上应用包。
- 云端 evidence release 必须是 HTTPS、固定 release id、只读、不可覆盖，并提供文件级 hash/size manifest。
- 只发布当前 S2 文档直接引用的六组原始证据（含 journal DB2）、v73 的三个正式证据文件和 UI closure evidence；不上传历史 compact/SimC matrix/raw staging 全量。
- Git 已跟踪的 Harness requirement/evidence/manifest 仍是 CI 的 task-scoped 输入，不删除、不改成运行时远程读取。
- 任何 `partial`、`blocked`、历史或 waiver 状态必须继续按原状态表达，云端地址不提升证据等级。
- 清理范围只允许是 `artifacts/releases/` 下未跟踪的本地生成物；不得使用 `git clean` 或删除已跟踪文件。

---

### Task 1: Add immutable cloud evidence hosting and bounded publisher

**Files:**
- Modify: `server/deploy_lighthouse.sh:491-500,660-690`
- Create: `server/publish_release_evidence.sh`
- Create: `docs/release-evidence-publishing.md`
- Modify: `tests/deploy_lighthouse.test.js`

**Interfaces:**
- Publisher entrypoint: `WOW_EVIDENCE_RELEASE_ID=<id> server/publish_release_evidence.sh`.
- Publisher target: `https://api.chickenbro.cloud/wow-evidence/releases/<id>/`.
- Publisher source allowlist includes the six current S2 capture roots (including journal DB2), the three tracked v73 evidence files, and `2026-08-24-s2-equipment-library-ui-closure/evidence.json`; it rejects missing paths, symlinks, path traversal, release-id overwrite, and a total payload over 256 MiB.
- Remote release contains `release-manifest.json` with `schemaVersion`, `releaseId`, `immutableRoot`, `fileCount`, `totalBytes`, and sorted `{path, sha256, bytes}` records.

- [x] **Step 1: Add the Nginx location and directory creation**

  Add `/var/www/wow-evidence/releases` creation beside the existing assets/media roots and add a read-only immutable Nginx location for `/wow-evidence/releases/` with `try_files`, `Cache-Control: public, max-age=31536000, immutable`, CORS, and `nosniff` headers. Keep `--exclude 'artifacts'` unchanged in the tar deployment source.

- [x] **Step 2: Implement the bounded publisher**

  Validate `^[a-z0-9][a-z0-9._-]{7,63}$` release ids and an absolute remote root. Copy only the explicit allowlist into a temporary staging directory, reject symlinks, compute SHA-256/byte counts, write sorted `release-manifest.json`, stream a tar archive over the existing `wow-lighthouse` SSH alias, and atomically create the remote release directory only when it does not already exist.

- [x] **Step 3: Document the boundary and rollback**

  Document the public root, exact publish command, manifest verification command, immutable-release rule, rollback by changing the document pointer to a previous release id, and the statement that Harness local paths are CI inputs rather than production runtime dependencies.

- [x] **Step 4: Add static contract tests**

  Extend deployment tests to assert the evidence directory, Nginx route, immutable headers, and `artifacts` exclusion. Test the publisher's allowlist, release-id validation, and overwrite guard without making a remote call.

### Task 2: Migrate current S2 references to the cloud evidence root

**Files:**
- Modify: `server/data/midnight-season-2/README.md:75-100`
- Modify: `server/data/midnight-season-2/source-policy.json:111`
- Modify: `docs/plans/2026-08-13-s2-official-api-fact-snapshot-implementation.md:132-240`
- Modify: `docs/plans/README.md:19,34-35`
- Modify: `docs/roadmap.md:50,65`

**Interfaces:**
- Cloud base constant in documentation: `https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2`.
- Current S2 evidence links must resolve below this base; local relative links may remain only in Harness instructions that intentionally run in a checkout.

- [x] **Step 1: Replace direct current-S2 evidence links**

  Replace direct links for v8/v11 official captures, limited DB2 probes, journal DB2 capture, v73 candidate/seal/live-smoke, and UI closure evidence with the immutable cloud base while preserving labels, statuses, and historical/blocked wording.

- [x] **Step 2: Keep runtime and CI contracts explicit**

  Add a short note to the S2 data README and evidence runbook: runtime reads PostgreSQL/API and never opens the evidence URL; CI/Harness may still use repository-local task packets. Do not alter `project-state.json` evidence selectors or `scripts/project-harness.js` local output paths.

- [x] **Step 3: Add a reference audit**

  Run a tracked-file search and assert that production `server/`, `apps/`, and `packages/` runtime code has no `artifacts/releases` filesystem read. List remaining local references as Harness/doc build inputs rather than silently rewriting them.

### Task 3: Publish and verify the current S2 evidence release

**Files:**
- Create: the remote immutable release `2026-08-24-s2-equipment-library-evidence-v2` under `/var/www/wow-evidence/releases/`
- Verify: the remote `release-manifest.json` and every manifest-listed file over HTTPS

**Interfaces:**
- The local source set must be secret-free, bounded below 256 MiB, and match the publisher allowlist.
- HTTP verification must compare status, content length, SHA-256, and release id; a 200 alone is insufficient.

- [x] **Step 1: Scan the selected source set**

  Check for credential/header/token patterns, symlinks, missing files, and total size before upload. Do not include v69-v72 candidate snapshots, compact JSON, SimC matrices, community staging, or v73 `prepared-final-v1.json`.

- [x] **Step 2: Publish once**

  Run the publisher with the fixed release id. If the remote id already exists, stop and compare its manifest instead of overwriting it.

- [x] **Step 3: Verify every remote record**

  Fetch the manifest and each listed file via HTTPS, compare byte count and SHA-256, and record the resulting evidence in the working report. Verify the active S2 document URLs and the existing API health endpoint separately.

### Task 4: Remove local bulk outputs and prevent false local dependency claims

**Files:**
- Delete: only untracked entries under `artifacts/releases/` after Task 3 verification
- Modify: `.gitignore` only if a narrowly scoped rule for the identified bulk families is proven not to hide future formal release packets
- Verify: `git status`, `du`, `git ls-files`, tracked reference audit, and targeted tests

**Interfaces:**
- Preserve every Git-tracked file under `artifacts/releases/`.
- Preserve the remote release and all cloud links in the current S2 docs.
- After cleanup, `artifacts/releases` must contain the tracked evidence only plus no untracked 97GB families.

- [x] **Step 1: Generate the deletion set**

  Enumerate `git status --porcelain=v1 artifacts/releases`, classify every entry, and require that all untracked paths are either published in Task 3 or explicitly classified as obsolete intermediate output. Refuse any tracked path.

- [x] **Step 2: Delete only the approved untracked set**

  Use an explicit null-delimited deletion list rooted at `artifacts/releases/`; do not use broad repository cleanup. Report the before/after byte count.

- [x] **Step 3: Run final verification**

  Run `git diff --check`, the deployment/publisher tests, the S2 scope tests, the tracked reference audit, remote manifest hash verification, and `du -sh artifacts/releases`. Confirm main/origin parity is unchanged and no production source reads local artifacts.
