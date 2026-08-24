# Release Evidence Publishing

Current S2 evidence is published under the immutable public root
`https://api.chickenbro.cloud/wow-evidence/releases/<release-id>/`.

Publish one bounded release with:

```bash
WOW_EVIDENCE_RELEASE_ID=<release-id> server/publish_release_evidence.sh
```

Verify the remote manifest with:

```bash
curl -fsS https://api.chickenbro.cloud/wow-evidence/releases/<release-id>/release-manifest.json
```

Each release id is immutable. The publisher refuses overwrite, and rollback is
performed by changing the document pointer back to a previously published
release id rather than mutating an existing release directory.

The publisher only uploads the current bounded S2 evidence allowlist: the five
current S2 capture roots, the three tracked v73 evidence files, and
`artifacts/releases/2026-08-24-s2-equipment-library-ui-closure/evidence.json`.
It rejects missing paths, symlinks, path traversal, and total payloads above
256 MiB.

Harness local `artifacts/releases/...` paths remain CI and checkout inputs.
They are not production runtime dependencies, and the running backend continues
to read PostgreSQL/API state rather than opening release evidence files from the
cloud root.
