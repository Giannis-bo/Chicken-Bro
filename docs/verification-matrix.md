# Project Harness Verification Matrix

This matrix defines the local and CI verification profiles for the Project Harness Engineering Normalization milestone. All profiles resolve a single release packet from either `--release` or `docs/project-state.json.activeReleaseArtifact`.

| Profile | Purpose | Commands are owned by |
| --- | --- | --- |
| `harness` | Docs, schemas, owner maps and Harness tooling | `scripts/verify-project.js` |
| `backend` | Python backend, data and read-model contracts | `scripts/verify-project.js` |
| `frontend` | Mini-program JavaScript contract and syntax | `scripts/verify-project.js` |
| `full` | Milestone and PR closure baseline | `scripts/verify-project.js` |

## Local Usage

```bash
node scripts/verify-project.js --profile harness --release artifacts/releases/2026-07-10-executable-project-harness
node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-10-executable-project-harness
```

Use `--dry-run --json` to inspect the exact command list without executing it.

## CI Contract

`.github/workflows/project-harness.yml` resolves the active release from `docs/project-state.json` and invokes:

```bash
node scripts/verify-project.js --profile harness --release "$ACTIVE_RELEASE" --base origin/main
node scripts/verify-project.js --profile full --release "$ACTIVE_RELEASE" --base origin/main
```

The workflow does not deploy, SSH, install repository dependencies, run migrations, trigger sync jobs, or write production data. Failing tests, invalid JSON, owner-map conflicts, Harness packet failures, syntax failures, or whitespace errors must return nonzero.
