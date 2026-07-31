#!/usr/bin/env python3
"""Build deterministic manifests from already-captured official evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.season_pve_official_evidence import (  # noqa: E402
    EVIDENCE_SCHEMA_REVISION,
    OfficialEvidenceError,
    authority_identity,
    build_crafted_allowlist_diff,
    build_official_item_opposition,
    build_official_membership_snapshot,
    build_universe_discovery_input,
    client_build_from_namespace,
    client_build_from_simc_version,
    index_simc_generated_item_data,
    official_response_namespaces,
    sha256_file,
    verify_current_client_public_tact_key_reextract_audit,
    verify_current_client_source_relations_audit,
    verify_current_client_tact_key_coverage_audit,
    verify_current_client_tact_key_upstream_source_audit,
    verify_official_item_range_snapshot,
    write_json,
)
from server.season_pve_official_capture import (  # noqa: E402
    index_official_item_search,
)
from server.crafted_gear_backfill import (  # noqa: E402
    CURRENT_PVE_CRAFTED_METADATA_ITEMS,
    EXCLUDED_CRAFTED_METADATA_ITEMS,
    UNSUPPORTED_CRAFTED_METADATA_ITEMS,
)


class _HeadMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.canonical_url = ""

    def handle_starttag(self, tag, attrs):
        values = {str(key).lower(): str(value or "") for key, value in attrs}
        lowered = tag.lower()
        if lowered == "title":
            self.in_title = True
        elif lowered == "meta":
            key = values.get("property") or values.get("name")
            content = values.get("content")
            if key and content:
                self.meta[key.lower()] = content.strip()
        elif lowered == "link" and values.get("rel", "").lower() == "canonical":
            self.canonical_url = values.get("href", "").strip()

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return re.sub(r"\s+", " ", "".join(self.title_parts)).strip()


def _page_metadata(path: Path, developer_authority_ref: str) -> dict:
    body = path.read_text(encoding="utf-8")
    parser = _HeadMetadataParser()
    parser.feed(body)
    published_match = re.search(
        r'"datePublished"\s*:\s*"([^"]+)"',
        body,
    )
    canonical_url = (
        developer_authority_ref
        if path.name == "developer-game-data-apis.html"
        else parser.canonical_url
        or parser.meta.get("og:url", "")
    )
    if not canonical_url:
        raise OfficialEvidenceError(
            f"{path.name} does not expose a canonical official URL"
        )
    return {
        "relativePath": f"raw/authority-pages/{path.name}",
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "authorityRef": canonical_url,
        "authorityIdentity": authority_identity(canonical_url),
        "title": parser.meta.get("og:title") or parser.title,
        "publishedAt": published_match.group(1) if published_match else "",
    }


def _verify_game_data_capture(root: Path, manifest: dict) -> dict:
    requests = manifest.get("requests")
    if not isinstance(requests, list):
        raise OfficialEvidenceError("Game Data manifest requires requests")
    seen = set()
    verified_bytes = 0
    response_namespaces = set()
    for request in requests:
        relative_path = str(request.get("relativePath") or "")
        if not relative_path or relative_path in seen:
            raise OfficialEvidenceError(
                "Game Data manifest paths must be non-empty and unique"
            )
        seen.add(relative_path)
        path = root / relative_path
        if not path.is_file():
            raise OfficialEvidenceError(
                f"Game Data response missing: {relative_path}"
            )
        actual_sha = sha256_file(path)
        if actual_sha != request.get("sha256"):
            raise OfficialEvidenceError(
                f"Game Data response checksum mismatch: {relative_path}"
            )
        actual_bytes = path.stat().st_size
        if actual_bytes != request.get("bytes"):
            raise OfficialEvidenceError(
                f"Game Data response byte mismatch: {relative_path}"
            )
        verified_bytes += actual_bytes
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise OfficialEvidenceError(
                f"Game Data response is not valid JSON: {relative_path}"
            ) from error
        response_namespaces.update(
            official_response_namespaces(payload)
        )
    if len(requests) != manifest.get("requestCount"):
        raise OfficialEvidenceError("Game Data request count mismatch")
    return {
        "verifiedRequestCount": len(requests),
        "verifiedRequestBytes": verified_bytes,
        "uniqueRelativePathCount": len(seen),
        "responseNamespaces": sorted(response_namespaces),
        "staticClientBuilds": sorted(
            {
                client_build_from_namespace(namespace)
                for namespace in response_namespaces
                if client_build_from_namespace(namespace)
            },
            key=int,
        ),
    }


def build(args) -> dict:
    snapshot_root = Path(args.snapshot_root).expanduser().resolve()
    policy = json.loads(
        Path(args.policy).expanduser().resolve().read_text(encoding="utf-8")
    )
    capture_root = snapshot_root / args.capture_revision_dir
    capture = json.loads(
        (capture_root / "official-game-data-capture.json").read_text(
            encoding="utf-8"
        )
    )
    capture_manifest = json.loads(
        (capture_root / "capture-manifest.json").read_text(encoding="utf-8")
    )
    game_data_verification = _verify_game_data_capture(
        capture_root,
        capture_manifest,
    )
    for recipe in capture.get("professionCapture", {}).get("recipes") or []:
        recipe_id = str(recipe.get("recipeId") or "").strip()
        recipe_payload = json.loads(
            (
                capture_root
                / "raw"
                / "game-data"
                / "professions"
                / "recipes"
                / f"{recipe_id}.json"
            ).read_text(encoding="utf-8")
        )
        recipe["modifiedCraftingSlotNames"] = [
            str(
                (
                    raw_slot.get("slot_type")
                    if isinstance(raw_slot, dict)
                    else {}
                ).get("name")
                or ""
            ).strip()
            for raw_slot in recipe_payload.get("modified_crafting_slots") or []
            if str(
                (
                    raw_slot.get("slot_type")
                    if isinstance(raw_slot, dict)
                    else {}
                ).get("name")
                or ""
            ).strip()
        ]

    policy_authority_refs = sorted(
        {
            str(reference).strip()
            for source in policy.get("sources") or []
            for reference in source.get("authorityRefs") or []
            if str(reference).strip()
        }
    )
    developer_refs = [
        reference
        for reference in policy_authority_refs
        if "developer.battle.net/documentation/world-of-warcraft/game-data-apis"
        in reference
    ]
    if len(developer_refs) != 1:
        raise OfficialEvidenceError(
            "source policy requires one Game Data API authority reference"
        )
    authority_dir = snapshot_root / "raw" / "authority-pages"
    pages = [
        _page_metadata(path, developer_refs[0])
        for path in sorted(authority_dir.glob("*.html"))
    ]
    page_by_identity = {
        page["authorityIdentity"]: page
        for page in pages
    }
    if len(page_by_identity) != len(pages):
        raise OfficialEvidenceError(
            "captured authority pages contain duplicate canonical identities"
        )
    coverage = []
    for reference in policy_authority_refs:
        identity = authority_identity(reference)
        page = page_by_identity.get(identity)
        coverage.append(
            {
                "authorityRef": reference,
                "authorityIdentity": identity,
                "captured": page is not None,
                "relativePath": page["relativePath"] if page else "",
                "sha256": page["sha256"] if page else "",
            }
        )
    unmatched = [
        row["authorityRef"] for row in coverage if not row["captured"]
    ]
    policy_identities = {
        row["authorityIdentity"] for row in coverage
    }
    authority_manifest = {
        "schemaVersion": 1,
        "schemaRevision": EVIDENCE_SCHEMA_REVISION,
        "status": "blocked" if unmatched else "captured",
        "capturedAt": args.authority_captured_at,
        "pageCount": len(pages),
        "policyAuthorityRefCount": len(policy_authority_refs),
        "coveredPolicyAuthorityRefCount": len(coverage) - len(unmatched),
        "unmatchedPolicyAuthorityRefs": unmatched,
        "additionalOfficialPageCount": sum(
            page["authorityIdentity"] not in policy_identities
            for page in pages
        ),
        "pages": pages,
        "policyAuthorityCoverage": coverage,
    }
    authority_manifest_path = snapshot_root / "authority-page-manifest.json"
    write_json(authority_manifest_path, authority_manifest)

    simc_root = snapshot_root / "raw" / "simc-client-data"
    simc_item_data_path = simc_root / "item_data.inc"
    simc_commit_path = simc_root / "simc.commit"
    simc_commit = simc_commit_path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", simc_commit):
        raise OfficialEvidenceError(
            "SimulationCraft commit snapshot must be one Git SHA"
        )
    simc_item_index = index_simc_generated_item_data(
        simc_item_data_path.read_text(encoding="utf-8")
    )
    simc_manifest = {
        "schemaVersion": 1,
        "schemaRevision": EVIDENCE_SCHEMA_REVISION,
        "status": "captured",
        "capturedAt": args.simc_captured_at,
        "version": args.simc_version,
        "clientBuild": client_build_from_simc_version(args.simc_version),
        "commit": simc_commit,
        "itemData": {
            "relativePath": "raw/simc-client-data/item_data.inc",
            "sha256": sha256_file(simc_item_data_path),
            "bytes": simc_item_data_path.stat().st_size,
            "distinctNameCount": len(simc_item_index),
            "itemCount": sum(len(rows) for rows in simc_item_index.values()),
        },
        "commitEvidence": {
            "relativePath": "raw/simc-client-data/simc.commit",
            "sha256": sha256_file(simc_commit_path),
            "bytes": simc_commit_path.stat().st_size,
        },
    }
    simc_manifest_path = snapshot_root / "simc-client-data-manifest.json"
    write_json(simc_manifest_path, simc_manifest)

    client_crafted_membership = None
    client_crafted_evidence_ref = ""
    if args.client_crafted_membership:
        client_crafted_path = (
            snapshot_root / args.client_crafted_membership
        ).resolve()
        if not client_crafted_path.is_relative_to(snapshot_root):
            raise OfficialEvidenceError(
                "current-client crafted evidence must stay in snapshot root"
            )
        client_crafted_membership = json.loads(
            client_crafted_path.read_text(encoding="utf-8")
        )
        client_crafted_evidence_ref = (
            client_crafted_path.relative_to(snapshot_root).as_posix()
        )
    client_journal_membership = None
    client_journal_evidence_ref = ""
    if args.client_journal_membership:
        client_journal_path = (
            snapshot_root / args.client_journal_membership
        ).resolve()
        if not client_journal_path.is_relative_to(snapshot_root):
            raise OfficialEvidenceError(
                "current-client Journal evidence must stay in snapshot root"
            )
        client_journal_membership = json.loads(
            client_journal_path.read_text(encoding="utf-8")
        )
        client_journal_evidence_ref = (
            client_journal_path.relative_to(snapshot_root).as_posix()
        )
    membership = build_official_membership_snapshot(
        policy,
        capture,
        captured_at=capture.get("capturedAt") or "",
        authority_manifest_ref="authority-page-manifest.json",
        capture_ref=(
            f"{args.capture_revision_dir}/official-game-data-capture.json"
        ),
        capture_directory=args.capture_revision_dir,
        simc_item_index=simc_item_index,
        simc_evidence_ref="simc-client-data-manifest.json",
        client_crafted_membership=client_crafted_membership,
        client_crafted_evidence_ref=client_crafted_evidence_ref,
        client_journal_membership=client_journal_membership,
        client_journal_evidence_ref=client_journal_evidence_ref,
    )
    membership["gameDataCaptureVerification"] = game_data_verification
    simc_client_build = simc_manifest["clientBuild"]
    game_data_client_builds = game_data_verification[
        "staticClientBuilds"
    ]
    client_build_parity = (
        "matched"
        if simc_client_build
        and game_data_client_builds == [simc_client_build]
        else "mismatched"
        if simc_client_build and game_data_client_builds
        else "unresolved"
    )
    membership["clientBuildEvidence"] = {
        "status": client_build_parity,
        "gameDataStaticClientBuilds": game_data_client_builds,
        "simcClientBuild": simc_client_build,
        "reasonCode": (
            ""
            if client_build_parity == "matched"
            else "OFFICIAL_EVIDENCE_CLIENT_BUILD_MISMATCH"
            if client_build_parity == "mismatched"
            else "OFFICIAL_EVIDENCE_CLIENT_BUILD_UNRESOLVED"
        ),
    }
    membership["summary"]["clientBuildStatus"] = client_build_parity
    membership_path = (
        snapshot_root / "official-source-membership-snapshot.json"
    )
    write_json(membership_path, membership)
    universe_discovery = build_universe_discovery_input(
        membership,
        evidence_ref="official-source-membership-snapshot.json",
    )
    universe_discovery_path = (
        snapshot_root / "universe-discovery-input.json"
    )
    write_json(universe_discovery_path, universe_discovery)
    item_range_verification = None
    if args.item_range_dir:
        item_range_root = snapshot_root / args.item_range_dir
        (
            item_range_verification,
            official_item_index,
        ) = verify_official_item_range_snapshot(item_range_root)
        item_opposition = build_official_item_opposition(
            official_item_index,
            membership,
            required_level=None,
            search_scope="all_equippable_items",
            client_item_ids={
                row["itemId"]
                for rows in simc_item_index.values()
                for row in rows
            },
        )
        item_opposition["officialItemSearchEvidenceRef"] = (
            f"{args.item_range_dir}/capture-manifest.json"
        )
        item_opposition["officialItemRangeVerification"] = (
            item_range_verification
        )
        item_opposition["clientItemDataEvidenceRef"] = (
            "simc-client-data-manifest.json"
        )
    else:
        official_item_search = json.loads(
            (
                capture_root
                / "raw"
                / "game-data"
                / "items"
                / "required-level-90-equippable.json"
            ).read_text(encoding="utf-8")
        )
        item_opposition = build_official_item_opposition(
            index_official_item_search(official_item_search),
            membership,
        )
        item_opposition["officialItemSearchEvidenceRef"] = (
            f"{args.capture_revision_dir}/raw/game-data/items/"
            "required-level-90-equippable.json"
        )
    item_opposition["sourceMembershipSnapshotRef"] = (
        "official-source-membership-snapshot.json"
    )
    item_opposition_path = (
        snapshot_root / "official-item-opposition.json"
    )
    write_json(item_opposition_path, item_opposition)
    client_source_relations_verification = None
    client_source_relations_verification_path = None
    if (
        args.client_tact_key_coverage_audit
        and not args.client_source_relations_audit
    ):
        raise OfficialEvidenceError(
            "current-client TACT-key audit requires "
            "the source relation audit"
        )
    if (
        args.client_public_tact_key_reextract_audit
        and (
            not args.client_source_relations_audit
            or not args.client_tact_key_coverage_audit
        )
    ):
        raise OfficialEvidenceError(
            "public TACT-key re-extraction audit requires both "
            "the source relation and static TACT-key audits"
        )
    if (
        args.client_tact_key_upstream_source_audit
        and not args.client_public_tact_key_reextract_audit
    ):
        raise OfficialEvidenceError(
            "TACT-key upstream source audit requires the public "
            "TACT-key re-extraction audit"
        )
    if args.client_source_relations_audit:
        client_source_relations_path = (
            snapshot_root / args.client_source_relations_audit
        ).resolve()
        if not client_source_relations_path.is_relative_to(snapshot_root):
            raise OfficialEvidenceError(
                "current-client source relation audit must stay in snapshot root"
            )
        client_source_relations = json.loads(
            client_source_relations_path.read_text(encoding="utf-8")
        )
        client_source_relations_verification = (
            verify_current_client_source_relations_audit(
                client_source_relations,
                expected_gap_count=membership["summary"]["gapCount"],
            )
        )
        if (
            client_source_relations_verification["build"].rsplit(".", 1)[-1]
            != simc_client_build
        ):
            raise OfficialEvidenceError(
                "current-client source relation audit build does not match "
                "the captured client-data build"
            )
        audit_inputs = client_source_relations.get("inputs")
        expected_input_hashes = {
            "official-source-membership-snapshot.json": sha256_file(
                membership_path
            ),
            "official-item-opposition.json": sha256_file(
                item_opposition_path
            ),
        }
        if (
            not isinstance(audit_inputs, dict)
            or any(
                not isinstance(audit_inputs.get(name), dict)
                or audit_inputs[name].get("sha256") != expected_sha
                for name, expected_sha in expected_input_hashes.items()
            )
        ):
            raise OfficialEvidenceError(
                "current-client source relation audit inputs do not match "
                "the rebuilt official snapshot"
            )
        client_source_relations_verification_path = (
            snapshot_root
            / "current-client-source-relations-verification.json"
        )
        tact_key_coverage_evidence = None
        public_tact_key_reextract_evidence = None
        tact_key_upstream_source_evidence = None
        if args.client_tact_key_coverage_audit:
            tact_key_coverage_path = (
                snapshot_root / args.client_tact_key_coverage_audit
            ).resolve()
            if not tact_key_coverage_path.is_relative_to(snapshot_root):
                raise OfficialEvidenceError(
                    "current-client TACT-key audit must stay in snapshot root"
                )
            tact_key_coverage = json.loads(
                tact_key_coverage_path.read_text(encoding="utf-8")
            )
            tact_key_coverage_verification = (
                verify_current_client_tact_key_coverage_audit(
                    tact_key_coverage,
                    expected_encrypted_record_count=(
                        client_source_relations_verification[
                            "encryptedRecordCount"
                        ]
                    ),
                )
            )
            tact_inputs = tact_key_coverage.get("inputs")
            relation_input = (
                tact_inputs.get(
                    "current-client-source-relations-audit.json"
                )
                if isinstance(tact_inputs, dict)
                else None
            )
            if (
                tact_key_coverage_verification["build"]
                != client_source_relations_verification["build"]
                or not isinstance(relation_input, dict)
                or relation_input.get("sha256")
                != sha256_file(client_source_relations_path)
            ):
                raise OfficialEvidenceError(
                    "current-client TACT-key audit does not bind "
                    "the source relation audit"
                )
            tact_key_coverage_evidence = {
                "relativePath": (
                    tact_key_coverage_path.relative_to(
                        snapshot_root
                    ).as_posix()
                ),
                "sha256": sha256_file(tact_key_coverage_path),
                "bytes": tact_key_coverage_path.stat().st_size,
                "verification": tact_key_coverage_verification,
            }
        if args.client_public_tact_key_reextract_audit:
            public_reextract_path = (
                snapshot_root
                / args.client_public_tact_key_reextract_audit
            ).resolve()
            if not public_reextract_path.is_relative_to(snapshot_root):
                raise OfficialEvidenceError(
                    "public TACT-key re-extraction audit must stay "
                    "in snapshot root"
                )
            public_reextract = json.loads(
                public_reextract_path.read_text(encoding="utf-8")
            )
            public_reextract_verification = (
                verify_current_client_public_tact_key_reextract_audit(
                    public_reextract,
                    expected_encrypted_record_count=(
                        client_source_relations_verification[
                            "encryptedRecordCount"
                        ]
                    ),
                )
            )
            public_inputs = public_reextract.get("inputs")
            required_public_input_hashes = {
                "current-client-tact-key-coverage.json": sha256_file(
                    tact_key_coverage_path
                ),
                "current-client-source-relations-audit.json": (
                    sha256_file(client_source_relations_path)
                ),
            }
            if (
                public_reextract_verification["build"]
                != client_source_relations_verification["build"]
                or public_reextract_verification[
                    "recoveredEncryptedRecordCount"
                ]
                != client_source_relations_verification[
                    "recoveredEncryptedRecordCount"
                ]
                or public_reextract_verification[
                    "unavailableEncryptedRecordCount"
                ]
                != client_source_relations_verification[
                    "unparsedEncryptedRecordCount"
                ]
                or not isinstance(public_inputs, dict)
                or any(
                    not isinstance(public_inputs.get(name), dict)
                    or public_inputs[name].get("sha256")
                    != expected_sha
                    for name, expected_sha
                    in required_public_input_hashes.items()
                )
            ):
                raise OfficialEvidenceError(
                    "public TACT-key re-extraction audit does not bind "
                    "the source relation and static key audits"
                )
            public_tact_key_reextract_evidence = {
                "relativePath": (
                    public_reextract_path.relative_to(
                        snapshot_root
                    ).as_posix()
                ),
                "sha256": sha256_file(public_reextract_path),
                "bytes": public_reextract_path.stat().st_size,
                "verification": public_reextract_verification,
            }
        if args.client_tact_key_upstream_source_audit:
            upstream_source_path = (
                snapshot_root
                / args.client_tact_key_upstream_source_audit
            ).resolve()
            if not upstream_source_path.is_relative_to(snapshot_root):
                raise OfficialEvidenceError(
                    "TACT-key upstream source audit must stay "
                    "in snapshot root"
                )
            upstream_source = json.loads(
                upstream_source_path.read_text(encoding="utf-8")
            )
            upstream_source_verification = (
                verify_current_client_tact_key_upstream_source_audit(
                    upstream_source,
                    expected_encrypted_record_count=(
                        client_source_relations_verification[
                            "encryptedRecordCount"
                        ]
                    ),
                )
            )
            upstream_inputs = upstream_source.get("inputs")
            public_coverage_input = (
                public_inputs.get(
                    "public-tact-key-a3449fd-coverage-audit.json"
                )
                if isinstance(public_inputs, dict)
                else None
            )
            if (
                upstream_source_verification["build"]
                != client_source_relations_verification["build"]
                or upstream_source_verification[
                    "sourceUnionAvailableTargetKeyCount"
                ]
                != public_reextract_verification[
                    "publicRecordTactKeyCount"
                ]
                or upstream_source_verification[
                    "sourceUnionMissingTargetKeyCount"
                ]
                != public_reextract_verification[
                    "missingRecordTactKeyCount"
                ]
                or upstream_source_verification[
                    "sourceUnionCoveredTargetRecordCount"
                ]
                != public_reextract_verification[
                    "recoveredEncryptedRecordCount"
                ]
                or upstream_source_verification[
                    "sourceUnionMissingTargetRecordCount"
                ]
                != public_reextract_verification[
                    "unavailableEncryptedRecordCount"
                ]
                or not isinstance(upstream_inputs, dict)
                or not isinstance(public_coverage_input, dict)
                or not isinstance(
                    upstream_inputs.get("currentPublicTactKeys"),
                    dict,
                )
                or upstream_inputs["currentPublicTactKeys"].get(
                    "sha256"
                )
                != public_coverage_input.get("sha256")
            ):
                raise OfficialEvidenceError(
                    "TACT-key upstream source audit does not bind "
                    "the public re-extraction evidence"
                )
            tact_key_upstream_source_evidence = {
                "relativePath": (
                    upstream_source_path.relative_to(
                        snapshot_root
                    ).as_posix()
                ),
                "sha256": sha256_file(upstream_source_path),
                "bytes": upstream_source_path.stat().st_size,
                "verification": upstream_source_verification,
            }
        write_json(
            client_source_relations_verification_path,
            {
                "schemaVersion": 1,
                "status": "blocked",
                "auditEvidence": {
                    "relativePath": (
                        client_source_relations_path.relative_to(
                            snapshot_root
                        ).as_posix()
                    ),
                    "sha256": sha256_file(
                        client_source_relations_path
                    ),
                    "bytes": client_source_relations_path.stat().st_size,
                },
                "inputBindings": expected_input_hashes,
                "verification": client_source_relations_verification,
                "staticTactKeyCoverage": tact_key_coverage_evidence,
                "publicTactKeyReextract": (
                    public_tact_key_reextract_evidence
                ),
                "tactKeyUpstreamSources": (
                    tact_key_upstream_source_evidence
                ),
                "promotionDecision": {
                    "promotedMemberCount": 0,
                    "catalogMutation": False,
                },
            },
        )
    crafted_source = next(
        (
            source
            for source in membership["sources"]
            if source["sourceKey"] == "crafted:midnight-season-1"
        ),
        None,
    )
    crafted_diff = build_crafted_allowlist_diff(
        crafted_source,
        CURRENT_PVE_CRAFTED_METADATA_ITEMS,
        project_unsupported=UNSUPPORTED_CRAFTED_METADATA_ITEMS,
        project_excluded=EXCLUDED_CRAFTED_METADATA_ITEMS,
    )
    crafted_diff["sourceMembershipSnapshotRef"] = (
        "official-source-membership-snapshot.json"
    )
    crafted_diff["projectAllowlistOwner"] = (
        "server/data/"
        "midnight-season-1-crafted-pve-membership.json"
    )
    crafted_diff_path = snapshot_root / "crafted-membership-diff.json"
    write_json(crafted_diff_path, crafted_diff)
    result = {
        "schemaRevision": EVIDENCE_SCHEMA_REVISION,
        "status": "blocked",
        "authorityManifest": {
            "status": authority_manifest["status"],
            "pageCount": authority_manifest["pageCount"],
            "policyAuthorityRefCount": (
                authority_manifest["policyAuthorityRefCount"]
            ),
            "coveredPolicyAuthorityRefCount": (
                authority_manifest["coveredPolicyAuthorityRefCount"]
            ),
        },
        "gameDataCaptureVerification": game_data_verification,
        "officialItemRangeVerification": item_range_verification,
        "clientBuildEvidence": membership["clientBuildEvidence"],
        "clientSourceRelationsVerification": (
            client_source_relations_verification
        ),
        "membershipSummary": membership["summary"],
        "itemOppositionSummary": item_opposition["summary"],
        "craftedDiffSummary": crafted_diff["summary"],
        "outputs": [
            authority_manifest_path.relative_to(snapshot_root).as_posix(),
            simc_manifest_path.relative_to(snapshot_root).as_posix(),
            membership_path.relative_to(snapshot_root).as_posix(),
            universe_discovery_path.relative_to(snapshot_root).as_posix(),
            item_opposition_path.relative_to(snapshot_root).as_posix(),
            crafted_diff_path.relative_to(snapshot_root).as_posix(),
            *(
                [
                    client_source_relations_verification_path.relative_to(
                        snapshot_root
                    ).as_posix()
                ]
                if client_source_relations_verification_path
                else []
            ),
        ],
    }
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--authority-captured-at", required=True)
    parser.add_argument(
        "--capture-revision-dir",
        default="official-game-data-v2",
    )
    parser.add_argument("--item-range-dir")
    parser.add_argument("--simc-captured-at", required=True)
    parser.add_argument("--simc-version", required=True)
    parser.add_argument("--client-crafted-membership")
    parser.add_argument("--client-journal-membership")
    parser.add_argument("--client-source-relations-audit")
    parser.add_argument("--client-tact-key-coverage-audit")
    parser.add_argument("--client-public-tact-key-reextract-audit")
    parser.add_argument("--client-tact-key-upstream-source-audit")
    return parser.parse_args(argv)


def main(argv=None):
    result = build(parse_args(argv))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 2 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OfficialEvidenceError, OSError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {
                    "schemaRevision": EVIDENCE_SCHEMA_REVISION,
                    "status": "blocked",
                    "reasonCode": "OFFICIAL_EVIDENCE_BUILD_FAILED",
                    "error": str(error)[:500],
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)
