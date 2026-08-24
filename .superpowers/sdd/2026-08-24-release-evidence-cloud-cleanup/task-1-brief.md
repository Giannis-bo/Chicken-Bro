### Task 1: Add immutable cloud evidence hosting and bounded publisher

**Files:**
- Modify: `server/deploy_lighthouse.sh:491-500,660-690`
- Create: `server/publish_release_evidence.sh`
- Create: `docs/release-evidence-publishing.md`
- Modify: `tests/deploy_lighthouse.test.js`

**Interfaces:**
- Publisher entrypoint: `WOW_EVIDENCE_RELEASE_ID=<id> server/publish_release_evidence.sh`.
- Publisher target: `https://api.chickenbro.cloud/wow-evidence/releases/<id>/`.
- Publisher source allowlist includes the six current S2 capture roots, the three tracked v73 evidence files, and `2026-08-24-s2-equipment-library-ui-closure/evidence.json`; it rejects missing paths, symlinks, path traversal, release-id overwrite, and a total payload over 256 MiB.
- Remote release contains `release-manifest.json` with `schemaVersion`, `releaseId`, `immutableRoot`, `fileCount`, `totalBytes`, and sorted `{path, sha256, bytes}` records.

- [ ] **Step 1: Add the Nginx location and directory creation**

  Add `/var/www/wow-evidence/releases` creation beside the existing assets/media roots and add a read-only immutable Nginx location for `/wow-evidence/releases/` with `try_files`, `Cache-Control: public, max-age=31536000, immutable`, CORS, and `nosniff` headers. Keep `--exclude 'artifacts'` unchanged in the tar deployment source.

- [ ] **Step 2: Implement the bounded publisher**

  Validate `^[a-z0-9][a-z0-9._-]{7,63}$` release ids and an absolute remote root. Copy only the explicit allowlist into a temporary staging directory, reject symlinks, compute SHA-256/byte counts, write sorted `release-manifest.json`, stream a tar archive over the existing `wow-lighthouse` SSH alias, and atomically create the remote release directory only when it does not already exist.

- [ ] **Step 3: Document the boundary and rollback**

  Document the public root, exact publish command, manifest verification command, immutable-release rule, rollback by changing the document pointer to a previous release id, and the statement that Harness local paths are CI inputs rather than production runtime dependencies.

- [ ] **Step 4: Add static contract tests**

  Extend deployment tests to assert the evidence directory, Nginx route, immutable headers, and `artifacts` exclusion. Test the publisher's allowlist, release-id validation, and overwrite guard without making a remote call.
