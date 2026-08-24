#!/usr/bin/env python3
"""Capture the remote community Gear staging inputs for an S2 candidate.

The remote query is read-only.  The resulting private bundle is an input to
the candidate builder and must not be served as public payload; only the
sealed Exact registry and community release are public outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile


REMOTE_CODE = r'''
import json
import os

for raw in open("/etc/wow-backend.env", encoding="utf-8"):
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in chr(34) + chr(39):
        value = value[1:-1]
    os.environ[key.strip()] = value

from server.db import connect_postgres, database_config_from_env
from server.gear_release_store import GearReleaseStore

config = database_config_from_env()
store = GearReleaseStore(lambda: connect_postgres(config.database_url))
with connect_postgres(config.database_url) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT class_key, spec_key "
            "FROM cache.websim_community_gear_templates "
            "ORDER BY class_key, spec_key"
        )
        expected_specs = cur.fetchall()

bundle = {
    "schemaRevision": "s2-community-exact-staging-bundle-v1",
    "expectedSpecs": [list(row) for row in expected_specs],
    "gear": store.snapshot_staging_gear(),
    "templates": store.snapshot_staging_community_builder_templates(expected_specs),
}
print(json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="ubuntu@124.223.51.33")
    parser.add_argument("--remote-dir", default="/opt/wow-mini-program")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        args.host,
        f"cd {args.remote_dir} && sudo -n python3 -",
    ]
    completed = subprocess.run(
        command,
        input=REMOTE_CODE.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.decode("utf-8", errors="replace"))
    value = json.loads(completed.stdout.decode("utf-8"))
    if not isinstance(value, dict) or value.get("schemaRevision") != "s2-community-exact-staging-bundle-v1":
        raise SystemExit("remote staging bundle schema is invalid")

    target = args.output.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = handle.name
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
        Path(temporary).replace(target)
        temporary = ""
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
    print(json.dumps({
        "output": str(target),
        "expectedSpecCount": len(value.get("expectedSpecs") or []),
        "templateCount": len(value.get("templates") or []),
        "gearVariantCount": len((value.get("gear") or {}).get("variants") or []),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
