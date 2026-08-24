#!/usr/bin/env python3
"""Build a temporary S2 Gear snapshot that can compile observed profiles.

This bootstrap is intentionally not a public Catalog source.  Every row copied
from the community staging Gear snapshot is marked ``exact_instance`` and
retains its source status (including ``partial``).  A later final candidate must
be rebuilt from the official runtime snapshot plus freshly sealed templates.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping


def _text(value: Any) -> str:
    return str(value or "").strip()


def _item_id(row: Mapping[str, Any]) -> str:
    return _text(row.get("itemId") or row.get("id"))


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    target = path.expanduser().resolve()
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
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
        Path(temporary).replace(target)
        temporary = ""
    finally:
        if temporary:
            try:
                Path(temporary).unlink()
            except FileNotFoundError:
                pass


def _community_truth(row: Mapping[str, Any], *, membership: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(row))
    payload = result.get("payload") if isinstance(result.get("payload"), Mapping) else {}
    payload = copy.deepcopy(dict(payload))
    payload.update({
        "truthScope": "community_observed",
        "officialFactStatus": "UNVERIFIED",
        "membershipKind": membership,
        "editable": False,
    })
    result["payload"] = payload
    return result


def build_observed_compile_bootstrap(
    base_snapshot: Mapping[str, Any],
    community_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    base = copy.deepcopy(dict(base_snapshot))
    source = community_snapshot if isinstance(community_snapshot, Mapping) else {}
    base_items = {
        _item_id(row): dict(row)
        for row in base.get("items") or []
        if isinstance(row, Mapping) and _item_id(row)
    }
    base_sources = {
        (_text(row.get("sourceId")), _item_id(row), _text(row.get("sourceKey"))): dict(row)
        for row in base.get("sources") or []
        if isinstance(row, Mapping)
    }
    base_variants = {
        (_text(row.get("variantId")), _text(row.get("variantKey"))): dict(row)
        for row in base.get("variants") or []
        if isinstance(row, Mapping)
    }
    base_options = {
        (_text(row.get("optionId")), _text(row.get("optionKey"))): dict(row)
        for row in base.get("options") or []
        if isinstance(row, Mapping)
    }

    observed_items = [
        _community_truth(row, membership="observed_compile_support")
        for row in source.get("items") or []
        if isinstance(row, Mapping) and _item_id(row)
    ]
    observed_sources = [
        _community_truth(row, membership="observed_compile_support")
        for row in source.get("sources") or []
        if (
            isinstance(row, Mapping)
            and _item_id(row)
            and _text(row.get("sourceType")).lower() == "observed_profile"
        )
    ]
    observed_variants = []
    for raw in source.get("variants") or []:
        if (
            not isinstance(raw, Mapping)
            or not _item_id(raw)
            or _text(raw.get("sourceType")).lower() != "observed_profile"
        ):
            continue
        row = _community_truth(raw, membership="observed_compile_support")
        row["rowFamily"] = "exact_instance"
        observed_variants.append(row)
    observed_options = [
        _community_truth(row, membership="observed_compile_support")
        for row in source.get("options") or []
        if isinstance(row, Mapping)
    ]

    conflicts = []
    for row in observed_items:
        key = _item_id(row)
        if key not in base_items:
            base_items[key] = row
    for row in observed_sources:
        key = (_text(row.get("sourceId")), _item_id(row), _text(row.get("sourceKey")))
        existing = base_sources.get(key)
        if existing is None:
            base_sources[key] = row
        elif _canonical(existing) != _canonical(row):
            conflicts.append(f"source:{key[0]}:{key[1]}:{key[2]}")
    for row in observed_variants:
        key = (_text(row.get("variantId")), _text(row.get("variantKey")))
        existing = base_variants.get(key)
        if existing is None:
            base_variants[key] = row
        elif _canonical(existing) != _canonical(row):
            conflicts.append(f"variant:{key[0]}:{key[1]}")
    for row in observed_options:
        key = (_text(row.get("optionId")), _text(row.get("optionKey")))
        existing = base_options.get(key)
        if existing is None:
            base_options[key] = row
        elif _canonical(existing) != _canonical(row):
            conflicts.append(f"option:{key[0]}:{key[1]}")
    if conflicts:
        raise ValueError("observed bootstrap identity conflicts: " + ",".join(sorted(conflicts)[:20]))

    base["items"] = sorted(base_items.values(), key=lambda row: _item_id(row))
    base["sources"] = sorted(
        base_sources.values(),
        key=lambda row: (_text(row.get("sourceId")), _item_id(row), _text(row.get("sourceKey"))),
    )
    base["variants"] = sorted(
        base_variants.values(),
        key=lambda row: (_item_id(row), _text(row.get("variantKey")), _text(row.get("variantId"))),
    )
    base["options"] = sorted(
        base_options.values(),
        key=lambda row: (_text(row.get("optionId")), _text(row.get("optionKey"))),
    )
    base["observedCompileBootstrap"] = {
        "schemaRevision": "s2-observed-compile-bootstrap-v1",
        "truthScope": "community_observed",
        "catalogExpansion": False,
        "templateBinding": "deferred_until_fresh_sealed_community_snapshot",
        "observedItemCount": len(observed_items),
        "observedSourceCount": len(observed_sources),
        "observedVariantCount": len(observed_variants),
        "observedVerifiedVariantCount": sum(
            1 for row in observed_variants if _text(row.get("status")).lower() == "verified"
        ),
        "observedPartialVariantCount": sum(
            1 for row in observed_variants if _text(row.get("status")).lower() == "partial"
        ),
        "observedOptionCount": len(observed_options),
    }
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-snapshot", required=True, type=Path)
    parser.add_argument("--community-staging", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    base = _load_json(args.base_snapshot)
    bundle = _load_json(args.community_staging)
    if not isinstance(base, Mapping):
        raise ValueError("base snapshot must be a JSON object")
    if not isinstance(bundle, Mapping) or not isinstance(bundle.get("gear"), Mapping):
        raise ValueError("community staging must contain a gear snapshot")
    result = build_observed_compile_bootstrap(base, bundle["gear"])
    _atomic_json_write(args.output, result)
    print(json.dumps(result["observedCompileBootstrap"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error))
        raise SystemExit(2)
