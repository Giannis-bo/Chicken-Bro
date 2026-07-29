import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from server import gear_release, gear_socket_authority


class FakeCursor:
    def __init__(self, rowsets=None, rowcounts=None):
        self.rowsets = rowsets or {}
        self.rowcounts = rowcounts or {}
        self.current_rows = []
        self.statements = []
        self.params = []
        self.executemany_calls = []
        self.fetchall_calls = 0
        self.fetchmany_calls = 0
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.statements.append(normalized)
        self.params.append(tuple(params or ()))
        self.current_rows = []
        self.rowcount = self.rowcounts.get("*", 1)
        for marker, count in self.rowcounts.items():
            if marker != "*" and marker in normalized:
                self.rowcount = count
                break
        for marker, rows in self.rowsets.items():
            if marker in normalized:
                if isinstance(rows, dict):
                    self.current_rows = list(rows.get(tuple(params or ()), rows.get("*", [])))
                else:
                    self.current_rows = list(rows)
                if marker not in self.rowcounts:
                    self.rowcount = len(self.current_rows)
                break

    def executemany(self, sql, params):
        normalized = " ".join(sql.split())
        values = [tuple(row) for row in params]
        self.statements.append(normalized)
        self.params.append(())
        self.executemany_calls.append((normalized, values))
        self.rowcount = len(values)

    def fetchone(self):
        return self.current_rows.pop(0) if self.current_rows else None

    def fetchall(self):
        self.fetchall_calls += 1
        rows = list(self.current_rows)
        self.current_rows = []
        return rows

    def fetchmany(self, size=1):
        self.fetchmany_calls += 1
        rows = self.current_rows[:size]
        self.current_rows = self.current_rows[size:]
        return rows


class FakeConnection:
    def __init__(self, rowsets=None, rowcounts=None):
        self.cursor_instance = FakeCursor(rowsets=rowsets, rowcounts=rowcounts)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class GearReleaseStoreTest(unittest.TestCase):
    def dependencies(self):
        return {
            "gearRuleRevision": "gear-rule-matrix-v1",
            "resolverContractRevision": "gear-resolver-contract-v1",
            "serializerRevision": "websim-profile-compat-v1",
            "simcRuntimeRevision": "simc-r1",
            "statPolicyRevision": "stat-snapshot-policy-v1",
            "selectionSchemaRevision": "selection-intent-v1",
            "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        }

    def snapshot(self):
        return {
            "items": [
                {
                    "itemId": "item-a",
                    "name": "Item A",
                    "slot": "head",
                    "itemLevel": 289,
                    "sourceStatus": "verified",
                    "payload": {"itemStats": [{"key": "intellect", "value": 100}]},
                    "updatedAt": "2026-07-11T05:00:00+00:00",
                }
            ],
            "sources": [
                {
                    "sourceId": "source-a",
                    "itemId": "item-a",
                    "sourceType": "observed_profile",
                    "sourceKey": "profile:a",
                    "sourceLabel": "Observed",
                    "instanceId": "",
                    "encounterId": "",
                    "difficultyKey": "mythic",
                    "seasonRevision": "season-17",
                    "payload": {"status": "verified"},
                    "updatedAt": "2026-07-11T05:00:00+00:00",
                }
            ],
            "variants": [
                {
                    "variantId": "variant-a-id",
                    "itemId": "item-a",
                    "variantKey": "variant-a",
                    "slot": "head",
                    "label": "289",
                    "sourceType": "observed_profile",
                    "difficultyKey": "mythic",
                    "itemLevel": 289,
                    "simcOptions": {"ilevel": "289"},
                    "status": "verified",
                    "blockers": [],
                    "payload": {"resolvedStats": {"intellect": 100}},
                    "updatedAt": "2026-07-11T05:00:00+00:00",
                }
            ],
            "options": [
                {
                    "optionId": "option-a-id",
                    "variantId": "variant-a-id",
                    "optionKey": "gem-a",
                    "optionType": "gem",
                    "name": "Gem A",
                    "applicableSlots": ["head"],
                    "simcOptions": {"gem_id": "1"},
                    "status": "verified",
                    "isVisible": True,
                    "payload": {"itemStats": [{"key": "haste", "value": 10}]},
                    "updatedAt": "2026-07-11T05:00:00+00:00",
                }
            ],
        }

    def gear_release(self, snapshot=None, dependencies=None):
        from server import gear_release_store

        snapshot = snapshot or self.snapshot()
        summary = gear_release_store.gear_snapshot_summary(snapshot)
        return gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=summary,
            dependency_revisions=dependencies or self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "legacy-import-r0"},
        )

    def community_release(self, gear_release_id, rows):
        from server import gear_release_store

        return gear_release.build_release(
            release_kind="community",
            season_revision="season-17",
            schema_revision="community-release-v1",
            content=gear_release_store.community_rows_summary(rows),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "legacy-import-r0"},
            validated_against_release_id=gear_release_id,
        )

    def release_row(self, release):
        return (
            release["releaseId"],
            release["releaseKind"],
            release["seasonRevision"],
            release["schemaRevision"],
            release["contentHash"],
            release["parentReleaseId"] or None,
            release["validatedAgainstReleaseId"] or None,
            release["releaseStatus"],
            release["dependencyRevisions"],
            {},
            release["source"],
            release["content"],
        )

    def test_gear_snapshot_summary_is_order_stable_and_content_sensitive(self):
        from server import gear_release_store

        snapshot = self.snapshot()
        reordered = {key: list(reversed(value)) for key, value in reversed(list(snapshot.items()))}
        first = gear_release_store.gear_snapshot_summary(snapshot)
        second = gear_release_store.gear_snapshot_summary(reordered)
        changed = copy.deepcopy(snapshot)
        changed["variants"][0]["itemLevel"] = 298

        self.assertEqual(first, second)
        self.assertRegex(first["snapshotHash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(first["counts"], {"items": 1, "sources": 1, "variants": 1, "options": 1})
        self.assertNotEqual(first, gear_release_store.gear_snapshot_summary(changed))

    def test_community_rows_summary_records_two_hero_winners_as_v2_content(self):
        from server import gear_release_store

        rows = [
            {
                "templateId": "community-gear:mage:arcane:sunfury:player-a",
                "classKey": "mage",
                "specKey": "arcane",
                "role": "winner",
                "electionRank": 1,
                "payload": {
                    "heroKey": "sunfury",
                    "talentWinnerId": "talent-sunfury-a",
                    "gearProjectionMode": "talent_winner",
                },
            },
            {
                "templateId": "community-gear:mage:arcane:spellslinger:player-b",
                "classKey": "mage",
                "specKey": "arcane",
                "role": "winner",
                "electionRank": 2,
                "payload": {
                    "heroKey": "spellslinger",
                    "talentWinnerId": "talent-spellslinger-a",
                    "gearProjectionMode": "gear_fallback",
                },
            },
        ]

        summary = gear_release_store.community_rows_summary(rows)

        self.assertEqual(summary["schemaRevision"], "community-release-content-v2")
        self.assertEqual(summary["winnerSpecs"], [{"classKey": "mage", "specKey": "arcane"}])
        self.assertEqual(
            summary["winnerHeroSlots"],
            [
                {"classKey": "mage", "specKey": "arcane", "heroKey": "spellslinger"},
                {"classKey": "mage", "specKey": "arcane", "heroKey": "sunfury"},
            ],
        )

    def test_seal_v2_community_release_rejects_duplicate_hero_projection_slots(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore, community_rows_summary

        rows = []
        for template_id, hero_key in (("hero-a", "sunfury"), ("hero-b", "spellslinger")):
            rows.append({
                "templateId": template_id,
                "classKey": "mage",
                "specKey": "arcane",
                "role": "winner",
                "electionRank": len(rows) + 1,
                "payload": {
                    "heroKey": hero_key,
                    "talentWinnerId": f"talent-{hero_key}",
                    "gearProjectionMode": "talent_winner",
                },
            })
        release = gear_release.build_release(
            release_kind="community",
            season_revision="season-17",
            schema_revision="community-release-v2",
            content=community_rows_summary(rows),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "hero-projection-test"},
            validated_against_release_id="gear-release:sha256:test",
        )
        store = GearReleaseStore(lambda: FakeConnection(rowsets={"FROM cache.websim_release_registry": []}))
        self.assertEqual(store.seal_community_release(release, rows)["status"], "inserted")

        duplicated = copy.deepcopy(rows)
        duplicated[1]["payload"]["heroKey"] = "sunfury"
        bad_release = gear_release.build_release(
            release_kind="community",
            season_revision="season-17",
            schema_revision="community-release-v2",
            content=community_rows_summary(duplicated),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "hero-projection-test"},
            validated_against_release_id="gear-release:sha256:test",
        )
        with self.assertRaisesRegex(GearReleaseIntegrityError, "distinct projected hero winners"):
            GearReleaseStore(lambda: FakeConnection()).seal_community_release(bad_release, duplicated)

    def test_snapshot_staging_gear_uses_one_repeatable_read_transaction(self):
        from server.gear_release_store import GearReleaseStore

        conn = FakeConnection(rowsets={
            "FROM cache.websim_items": [
                ("item-a", "Item A", "head", 289, {"x": 1}, "verified", "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_sources": [
                ("source-a", "item-a", "observed_profile", "profile:a", "Observed", "", "", "mythic", "season-17", {"status": "verified"}, "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_variants": [
                ("variant-a-id", "item-a", "variant-a", "head", "289", "observed_profile", "mythic", 289, {"ilevel": "289"}, "verified", [], {"resolvedStats": {"intellect": 100}}, "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_mod_options": [
                ("option-a-id", "variant-a-id", "gem-a", "gem", "Gem A", ["head"], {"gem_id": "1"}, "verified", True, {"itemStats": []}, "2026-07-11T05:00:00+00:00")
            ],
        })
        store = GearReleaseStore(lambda: conn)

        snapshot = store.snapshot_staging_gear()

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", sql)
        self.assertIn("FROM cache.websim_items", sql)
        self.assertIn("FROM cache.websim_gear_sources", sql)
        self.assertIn("FROM cache.websim_gear_variants", sql)
        self.assertIn("FROM cache.websim_gear_mod_options", sql)
        self.assertEqual(snapshot["items"][0]["itemId"], "item-a")
        self.assertEqual(snapshot["options"][0]["optionKey"], "gem-a")
        self.assertEqual(conn.cursor_instance.fetchall_calls, 0)
        self.assertGreaterEqual(conn.cursor_instance.fetchmany_calls, 5)
        self.assertTrue(conn.committed)

    def test_snapshot_staging_gear_projects_only_unambiguous_verified_blizzard_media(self):
        from server.gear_release_store import GearReleaseStore

        existing_icon = (
            "https://render.worldofwarcraft.com/icons/existing.jpg"
        )
        verified_icon = (
            "https://render.worldofwarcraft.com/icons/verified.jpg"
        )
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_items": [
                    (
                        "item-existing",
                        "Existing",
                        "head",
                        289,
                        {"iconUrl": existing_icon},
                        "verified",
                        "2026-07-11T05:00:00+00:00",
                    ),
                    (
                        "item-verified",
                        "Verified",
                        "main_hand",
                        295,
                        {},
                        "verified",
                        "2026-07-11T05:00:00+00:00",
                    ),
                    (
                        "item-conflict",
                        "Conflict",
                        "off_hand",
                        295,
                        {},
                        "verified",
                        "2026-07-11T05:00:00+00:00",
                    ),
                ],
                "FROM cache.websim_asset_registry asset": [
                    (
                        "item-verified",
                        "websim-item-metadata",
                        verified_icon,
                        "blizzard",
                        "verified",
                    ),
                    (
                        "item-verified",
                        "websim-item-loot",
                        verified_icon,
                        "blizzard",
                        "verified",
                    ),
                    (
                        "item-conflict",
                        "websim-item-metadata",
                        "https://render.worldofwarcraft.com/icons/first.jpg",
                        "blizzard",
                        "verified",
                    ),
                    (
                        "item-conflict",
                        "websim-item-loot",
                        "https://render.worldofwarcraft.com/icons/second.jpg",
                        "blizzard",
                        "verified",
                    ),
                ],
            }
        )

        snapshot = GearReleaseStore(
            lambda: conn
        ).snapshot_staging_gear()

        items = {
            row["itemId"]: row["payload"]
            for row in snapshot["items"]
        }
        self.assertEqual(
            items["item-existing"]["iconUrl"],
            existing_icon,
        )
        self.assertNotIn("gameAsset", items["item-existing"])
        self.assertEqual(
            items["item-verified"],
            {
                "iconUrl": verified_icon,
                "gameAsset": {
                    "status": "verified",
                    "source": "blizzard",
                    "iconUrl": verified_icon,
                },
            },
        )
        self.assertNotIn("iconUrl", items["item-conflict"])
        self.assertIn(
            "FROM cache.websim_asset_registry asset",
            "\n".join(conn.cursor_instance.statements),
        )

    def test_snapshot_gear_release_reads_one_exact_immutable_release(self):
        from server.gear_release_store import GearReleaseStore

        conn = FakeConnection(rowsets={
            "FROM cache.websim_gear_release_items": [
                ("item-a", "Item A", "head", 289, {"x": 1}, "verified", "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_release_sources": [
                ("source-a", "item-a", "observed_profile", "profile:a", "Observed", "", "", "mythic", "season-17", {"status": "verified"}, "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_release_variants": [
                ("variant-a-id", "item-a", "variant-a", "head", "289", "observed_profile", "mythic", 289, {"ilevel": "289"}, "verified", [], {"resolvedStats": {"intellect": 100}}, "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_release_mod_options": [
                ("option-a-id", "variant-a-id", "gem-a", "gem", "Gem A", ["head"], {"gem_id": "1"}, "verified", True, {"itemStats": []}, "2026-07-11T05:00:00+00:00")
            ],
        })

        snapshot = GearReleaseStore(lambda: conn).snapshot_gear_release(
            "gear-release:exact"
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", sql)
        self.assertNotIn("FROM cache.websim_items ", sql)
        self.assertEqual(snapshot["items"][0]["itemId"], "item-a")
        self.assertEqual(snapshot["variants"][0]["variantKey"], "variant-a")
        self.assertEqual(
            conn.cursor_instance.params[1:],
            [
                ("gear-release:exact",),
                ("gear-release:exact",),
                ("gear-release:exact",),
                ("gear-release:exact",),
            ],
        )

    def test_community_builder_projection_keeps_exact_rows_and_bounds_sources_payloads(self):
        from server.gear_release_store import (
            CandidateGearAuthorityIndex,
            GearReleaseIntegrityError,
            GearReleaseStore,
        )

        snapshot = self.snapshot()
        release = self.gear_release(snapshot)
        existing_row = (
            release["releaseId"],
            release["releaseKind"],
            release["seasonRevision"],
            release["schemaRevision"],
            release["contentHash"],
            release["parentReleaseId"] or None,
            release["validatedAgainstReleaseId"] or None,
            release["releaseStatus"],
            release["dependencyRevisions"],
            {},
            release["source"],
            release["content"],
        )
        conn = FakeConnection(rowsets={
            "FROM cache.websim_release_registry": [existing_row],
            "FROM cache.websim_gear_release_items": [
                ("item-a", "Item A", "head", 289, snapshot["items"][0]["payload"], "verified", "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_release_sources": [
                ("source-a", "item-a", "observed_profile", "profile:a", "Observed", "", "", "mythic", "season-17", {"status": "verified"}, "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_release_variants": [
                ("variant-a-id", "item-a", "variant-a", "head", "289", "observed_profile", "mythic", 289, {"ilevel": "289"}, "verified", [], snapshot["variants"][0]["payload"], "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_release_mod_options": [
                ("option-a-id", "variant-a-id", "gem-a", "gem", "Gem A", ["head"], {"gem_id": "1"}, "verified", True, snapshot["options"][0]["payload"], "2026-07-11T05:00:00+00:00")
            ],
        })

        projected = GearReleaseStore(
            lambda: conn
        ).snapshot_gear_release_for_community_builder(release["releaseId"])
        sql = "\n".join(conn.cursor_instance.statements)
        prepared = CandidateGearAuthorityIndex(projected, release)

        self.assertIn("SELECT DISTINCT ON (", sql)
        self.assertIn("candidate.item_id, candidate.source_type", sql)
        self.assertIn("jsonb_strip_nulls", sql)
        self.assertGreaterEqual(conn.cursor_instance.fetchmany_calls, 4)
        self.assertEqual(conn.cursor_instance.fetchall_calls, 0)
        self.assertEqual(
            projected["_releaseProjection"]["releaseId"],
            release["releaseId"],
        )
        self.assertIs(
            prepared.variants_by_item["item-a"][0],
            projected["variants"][0],
        )

        mismatched = copy.deepcopy(projected)
        mismatched["_releaseProjection"]["releaseId"] = "gear-release:other"
        with self.assertRaises(GearReleaseIntegrityError):
            CandidateGearAuthorityIndex(mismatched, release)

    def test_candidate_authority_context_uses_exact_sealed_snapshot_and_release_id(self):
        from server.gear_release_store import build_candidate_authority_context
        from server.websim_payload import gear_resolver_runtime_authority

        snapshot = self.snapshot()
        release = self.gear_release(snapshot)
        intent = {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": release["releaseId"],
            },
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90},
            "slots": {
                "head": {
                    "itemId": "item-a",
                    "variantKey": "variant-a",
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            },
        }
        runtime = gear_resolver_runtime_authority("mage", "arcane", simc_runtime_revision="simc-r1")
        runtime["dependencyRevisions"]["capabilityRevision"] = (
            gear_socket_authority.LEGACY_CAPABILITY_REVISION
        )

        context = build_candidate_authority_context(snapshot, intent, runtime, release)

        self.assertEqual(context["manifest"]["gearCatalogReleaseId"], release["releaseId"])
        self.assertEqual(context["manifest"]["gearCatalogRevision"], release["releaseId"])
        self.assertEqual(context["manifest"]["manifestType"], "candidate")
        self.assertFalse(context["manifest"]["formalActiveManifest"])

    def test_gear_snapshot_summary_streams_the_legacy_exact_hash_without_canonical_copies(self):
        from server import gear_release_store

        snapshot = self.snapshot()
        snapshot["variants"].append({
            **copy.deepcopy(snapshot["variants"][0]),
            "variantId": "variant-b-id",
            "variantKey": "variant-b",
            "payload": {
                "nested": {"z": 1, "a": [3, 2, 1]},
                "resolvedStats": {"haste": 90},
            },
        })
        snapshot["variants"].reverse()

        def canonical(value):
            return json.loads(json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ))

        def canonical_bytes(value):
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")

        legacy = {
            key: sorted(
                [
                    canonical(row)
                    for row in snapshot[key]
                    if isinstance(row, dict)
                ],
                key=canonical_bytes,
            )
            for key in ("items", "sources", "variants", "options")
        }
        expected_hash = "sha256:" + hashlib.sha256(
            canonical_bytes(legacy)
        ).hexdigest()

        with patch.object(
            gear_release_store,
            "_canonical_rows",
            side_effect=AssertionError("summary must not deep-copy the snapshot"),
        ):
            summary = gear_release_store.gear_snapshot_summary(snapshot)

        self.assertEqual(summary["snapshotHash"], expected_hash)
        self.assertEqual(summary["counts"]["variants"], 2)

    def test_candidate_authority_index_reuses_validated_snapshot_rows(self):
        from server.gear_release_store import CandidateGearAuthorityIndex

        snapshot = self.snapshot()
        release = self.gear_release(snapshot)
        prepared = CandidateGearAuthorityIndex(snapshot, release)

        self.assertIs(prepared.items["item-a"], snapshot["items"][0])
        self.assertIs(
            prepared.variants_by_item["item-a"][0],
            snapshot["variants"][0],
        )
        self.assertIs(
            prepared.options_by_key["gem-a"],
            snapshot["options"][0],
        )

    def test_prepared_candidate_authority_indexes_full_snapshot_only_once(self):
        from unittest.mock import patch

        from server import gear_release_store
        from server.gear_release_store import (
            CandidateGearAuthorityIndex,
            build_candidate_authority_context,
        )
        from server.websim_payload import gear_resolver_runtime_authority

        snapshot = self.snapshot()
        release = self.gear_release(snapshot)
        intent = {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": release["releaseId"],
            },
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90},
            "slots": {
                "head": {
                    "itemId": "item-a",
                    "variantKey": "variant-a",
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            },
        }
        runtime = gear_resolver_runtime_authority("mage", "arcane", simc_runtime_revision="simc-r1")
        runtime["dependencyRevisions"]["capabilityRevision"] = (
            gear_socket_authority.LEGACY_CAPABILITY_REVISION
        )

        with patch.object(
            gear_release_store,
            "gear_snapshot_summary",
            wraps=gear_release_store.gear_snapshot_summary,
        ) as summary:
            prepared = CandidateGearAuthorityIndex(snapshot, release)
            first = build_candidate_authority_context(
                snapshot,
                intent,
                runtime,
                release,
                prepared_index=prepared,
            )
            second = build_candidate_authority_context(
                snapshot,
                intent,
                runtime,
                release,
                prepared_index=prepared,
            )

        self.assertEqual(summary.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual(first["dependencyVector"]["gearCatalogReleaseId"], release["releaseId"])
        self.assertEqual(
            first["dependencyVector"]["capabilityRevision"],
            gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        )
        self.assertIn("item-a", first["itemsById"])
        self.assertIn("variant-a", first["variantsByKey"])
        self.assertEqual(first["missingFields"], [])

    def test_snapshot_staging_community_templates_keeps_all_observed_profiles_for_legal_fallback(self):
        from server.gear_release_store import GearReleaseStore

        conn = FakeConnection(rowsets={
            "FROM cache.websim_community_gear_templates": [
                (
                    "template-a", "mage", "arcane", "Observed A", "raiderio_observed_profile",
                    "Raider.IO", "https://raider.io/a", "synced", "complete", "gear:sig",
                    [{"sourceKey": "raiderio_observed_profile"}],
                    [{"slot": "head", "itemId": "item-a", "variantKey": "variant-a"}],
                    "head=item_a,id=item-a", 16, [], "observed", {"profileHash": "profile:a"},
                    "2026-07-11T05:00:00+00:00", "2026-07-25T05:00:00+00:00", "scan-a",
                )
            ]
        })
        rows = GearReleaseStore(lambda: conn).snapshot_staging_community_templates(
            [("mage", "arcane")]
        )
        sql = "\n".join(conn.cursor_instance.statements)

        self.assertIn("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", sql)
        self.assertIn("FROM cache.websim_community_gear_templates", sql)
        self.assertIn("unnest(%s::text[], %s::text[])", sql)
        self.assertIn("PARTITION BY template.class_key, template.spec_key", sql)
        self.assertNotIn("candidate_rank <= 10", sql)
        self.assertNotIn("LIMIT 400", sql)
        self.assertEqual(conn.cursor_instance.params[-1][0], ["mage"])
        self.assertEqual(conn.cursor_instance.params[-1][1], ["arcane"])
        self.assertGreaterEqual(conn.cursor_instance.fetchmany_calls, 1)
        self.assertEqual(conn.cursor_instance.fetchall_calls, 0)
        self.assertEqual(rows[0]["templateId"], "template-a")
        self.assertEqual(rows[0]["gearItems"][0]["variantKey"], "variant-a")
        self.assertEqual(rows[0]["payload"]["profileHash"], "profile:a")

    def test_snapshot_staging_talent_candidates_reads_persisted_election_order_without_cap(self):
        from server.gear_release_store import GearReleaseStore

        conn = FakeConnection(rowsets={
            "jsonb_array_elements": [
                (
                    "talent-fallback", "mage", "arcane", "sunfury", "mythic_plus",
                    "raiderio", "synced", "verified", "raiderio:us|area-52|fallback",
                    {"raiderio": {"sourceIdentity": "raiderio:us|area-52|fallback"}},
                    "2026-07-22T00:00:00+00:00", "2099-01-01T00:00:00+00:00", 11,
                )
            ]
        })

        rows = GearReleaseStore(lambda: conn).snapshot_staging_community_talent_candidates(
            [("mage", "arcane")]
        )
        sql = "\n".join(conn.cursor_instance.statements)

        self.assertIn("jsonb_array_elements", sql)
        self.assertIn("gearProjectionCandidates", sql)
        self.assertNotIn("talent_candidate_rank <= 10", sql)
        self.assertNotIn("LIMIT 800", sql)
        self.assertEqual(rows, [{
            "id": "talent-fallback",
            "classKey": "mage",
            "specKey": "arcane",
            "heroKey": "sunfury",
            "scenarioKey": "mythic_plus",
            "sourceKey": "raiderio",
            "sourceStatus": "synced",
            "status": "verified",
            "sourceIdentity": "raiderio:us|area-52|fallback",
            "payload": {"raiderio": {"sourceIdentity": "raiderio:us|area-52|fallback"}},
            "updatedAt": "2026-07-22T00:00:00+00:00",
            "expiresAt": "2099-01-01T00:00:00+00:00",
            "talentCandidateRank": 11,
        }])

    def test_release_refresh_reads_only_identity_hashes_for_additive_classification(self):
        from server.gear_release_store import GearReleaseStore

        conn = FakeConnection(rowsets={
            "FROM cache.websim_gear_release_items": [("item-a", "hash-item")],
            "FROM cache.websim_gear_release_sources": [("source-a", "hash-source")],
            "FROM cache.websim_gear_release_variants": [("variant-a", "hash-variant")],
            "FROM cache.websim_gear_release_mod_options": [("option-a", "hash-option")],
        })
        result = GearReleaseStore(lambda: conn).get_gear_release_row_hashes("gear-release:a")
        sql = "\n".join(conn.cursor_instance.statements)

        self.assertEqual(result, {
            "items": {"item-a": "hash-item"},
            "sources": {"source-a": "hash-source"},
            "variants": {"variant-a": "hash-variant"},
            "options": {"option-a": "hash-option"},
        })
        self.assertIn("SET TRANSACTION READ ONLY", sql)
        self.assertNotIn("payload_json", sql)
        self.assertNotIn("UPDATE ", sql)

    def test_release_refresh_events_are_append_only_and_latest_state_is_bounded(self):
        from server.gear_release_store import GearReleaseStore

        write_conn = FakeConnection()
        store = GearReleaseStore(lambda: write_conn)
        store.record_refresh_event(
            "gear_release_refresh_completed",
            {"status": "blocked", "blockerCodes": ["FULL_MATRIX_REQUIRED"]},
            release_id="community-release:a",
            manifest_revision="season-manifest:a",
        )
        write_sql = "\n".join(write_conn.cursor_instance.statements)
        self.assertIn("INSERT INTO cache.websim_release_events", write_sql)
        self.assertNotIn("UPDATE cache.websim_release_events", write_sql)

        read_conn = FakeConnection(rowsets={
            "FROM cache.websim_release_events": [(
                "gear_release_refresh_completed",
                {
                    "status": "blocked",
                    "blockerCodes": ["FULL_MATRIX_REQUIRED"],
                    "gearChange": {"addedCounts": {"items": 2}},
                    "sealStatus": {"gear": "inserted", "community": "inserted"},
                    "shadowStatus": "pass",
                    "shadowSpecCount": 40,
                    "shadowPerformance": {"specP95Ms": 123.4},
                    "raw": "not returned",
                },
                "2026-07-11T12:00:00+00:00",
                "community-release:a",
                "season-manifest:a",
            )]
        })
        latest = GearReleaseStore(lambda: read_conn).latest_refresh_state()
        self.assertEqual(latest["status"], "blocked")
        self.assertEqual(latest["eventType"], "gear_release_refresh_completed")
        self.assertEqual(latest["blockerCodes"], ["FULL_MATRIX_REQUIRED"])
        self.assertEqual(latest["gearChange"]["addedCounts"]["items"], 2)
        self.assertEqual(latest["sealStatus"]["gear"], "inserted")
        self.assertEqual(latest["shadowStatus"], "pass")
        self.assertEqual(latest["shadowSpecCount"], 40)
        self.assertEqual(latest["shadowPerformance"]["specP95Ms"], 123.4)
        self.assertNotIn("raw", latest)

    def test_seal_gear_release_inserts_registry_rows_and_append_only_event(self):
        from server.gear_release_store import GearReleaseStore

        snapshot = self.snapshot()
        release = self.gear_release(snapshot)
        conn = FakeConnection(rowsets={"FROM cache.websim_release_registry": []})
        store = GearReleaseStore(lambda: conn)

        result = store.seal_gear_release(release, snapshot, event={"mode": "legacy-import-r0"})

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(result, {"status": "inserted", "releaseId": release["releaseId"]})
        self.assertIn("INSERT INTO cache.websim_release_registry", sql)
        self.assertIn("INSERT INTO cache.websim_gear_release_items", sql)
        self.assertIn("INSERT INTO cache.websim_gear_release_sources", sql)
        self.assertIn("INSERT INTO cache.websim_gear_release_variants", sql)
        self.assertIn("INSERT INTO cache.websim_gear_release_mod_options", sql)
        self.assertIn("INSERT INTO cache.websim_release_events", sql)
        self.assertNotIn(" ON CONFLICT", sql)
        self.assertNotIn(" UPDATE cache.websim_release", sql)
        self.assertNotIn(" DELETE FROM cache.websim_release", sql)
        self.assertTrue(conn.committed)
        self.assertFalse(conn.rolled_back)

    def test_insert_gear_rows_bounds_each_executemany_batch(self):
        from server.gear_release_store import GearReleaseStore

        snapshot = {
            "items": [
                {
                    "itemId": f"item-{index:04d}",
                    "name": f"Item {index}",
                    "slot": "head",
                    "itemLevel": 289,
                    "sourceStatus": "verified",
                    "payload": {"itemStats": [{"key": "stamina", "value": index + 1}]},
                    "updatedAt": "2026-07-28T12:00:00+00:00",
                }
                for index in range(501)
            ],
            "sources": [],
            "variants": [],
            "options": [],
        }
        cursor = FakeCursor()

        GearReleaseStore._insert_gear_rows(cursor, "gear-release:test", snapshot)

        item_batches = [
            values
            for statement, values in cursor.executemany_calls
            if "INSERT INTO cache.websim_gear_release_items" in statement
        ]
        self.assertEqual([len(values) for values in item_batches], [250, 250, 1])
        self.assertTrue(all(len(values) <= 250 for values in item_batches))

    def test_seal_release_is_idempotent_only_for_exact_existing_descriptor(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        snapshot = self.snapshot()
        release = self.gear_release(snapshot)
        existing_row = (
            release["release_id"] if "release_id" in release else release["releaseId"],
            release["releaseKind"],
            release["seasonRevision"],
            release["schemaRevision"],
            release["contentHash"],
            release["parentReleaseId"] or None,
            release["validatedAgainstReleaseId"] or None,
            release["releaseStatus"],
            release["dependencyRevisions"],
            {},
            release["source"],
            release["content"],
        )
        conn = FakeConnection(rowsets={"FROM cache.websim_release_registry": [existing_row]})
        store = GearReleaseStore(lambda: conn)
        self.assertEqual(
            store.seal_gear_release(release, snapshot),
            {"status": "reused", "releaseId": release["releaseId"]},
        )
        self.assertFalse(any("INSERT INTO" in sql for sql in conn.cursor_instance.statements))

        mismatch = list(existing_row)
        mismatch[4] = "sha256:different"
        bad_conn = FakeConnection(rowsets={"FROM cache.websim_release_registry": [tuple(mismatch)]})
        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: bad_conn).seal_gear_release(release, snapshot)
        self.assertTrue(bad_conn.rolled_back)

    def test_seal_gear_release_rejects_snapshot_not_bound_by_descriptor(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        snapshot = self.snapshot()
        release = self.gear_release(snapshot)
        changed = copy.deepcopy(snapshot)
        changed["items"][0]["name"] = "Tampered"
        conn = FakeConnection()

        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: conn).seal_gear_release(release, changed)

        self.assertTrue(conn.rolled_back)
        self.assertFalse(any("INSERT INTO" in sql for sql in conn.cursor_instance.statements))

    def test_seal_release_rejects_forged_hash_addressed_descriptor(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        snapshot = self.snapshot()
        release = self.gear_release(snapshot)
        release["releaseId"] = "gear-release:sha256:forged"
        conn = FakeConnection()

        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: conn).seal_gear_release(release, snapshot)

        self.assertEqual(conn.cursor_instance.statements, [])

    def community_rows(self):
        return [
            {
                "templateId": "template-a",
                "classKey": "mage",
                "specKey": "arcane",
                "role": "winner",
                "electionRank": 1,
                "sourceKey": "raiderio_observed_profile",
                "sourceUrl": "https://raider.io/characters/cn/a",
                "sourceStatus": "synced",
                "sampleCount": 1,
                "profileHash": "profile:a",
                "gearHash": "gear:a",
                "selectionIntent": {"schemaRevision": "selection-intent-v1"},
                "resolvedGearSignature": "sha256:resolved",
                "semanticGearSignature": "sha256:semantic",
                "dependencyVector": {"gearCatalogReleaseId": "gear-release:a"},
                "evidence": {"status": "observed_verified"},
                "problems": [],
                "payload": {"name": "Observed A"},
                "updatedAt": "2026-07-11T05:00:00+00:00",
                "expiresAt": "2026-07-25T05:00:00+00:00",
            }
        ]

    def community_db_row(self, row):
        return (
            row["templateId"], row["classKey"], row["specKey"], row["role"],
            row["electionRank"], row["sourceKey"], row["sourceUrl"],
            row["sourceStatus"], row["sampleCount"], row["profileHash"],
            row["gearHash"], row["selectionIntent"], row["resolvedGearSignature"],
            row["semanticGearSignature"], row["dependencyVector"], row["evidence"],
            row["problems"], row["payload"], row["updatedAt"], row["expiresAt"],
        )

    def active_community_import_fixture(self):
        from server.gear_release_store import canonical_row_hash

        snapshot = self.snapshot()
        snapshot["items"][0]["payload"]["_metadata"] = {
            "iconUrl": "https://render.worldofwarcraft.com/icons/item-a.jpg",
            "gameAsset": {"source": "blizzard", "status": "verified"},
        }
        gear = self.gear_release(snapshot)
        rows = self.community_rows()
        rows[0]["selectionIntent"] = {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": gear["seasonRevision"],
                "gearCatalogRevision": gear["releaseId"],
            },
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90},
            "slots": {
                "head": {
                    "itemId": "item-a",
                    "variantKey": "variant-a",
                    "gemOptionIds": ["gem-a", "gem-a"],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            },
        }
        rows[0]["payload"]["importEvidence"] = {
            "schemaRevision": "community-template-import-evidence-v1",
            "sourceFingerprint": "sha256:" + "a" * 64,
            "slots": {
                "head": {
                    "itemId": "item-a",
                    "variantKey": "variant-a",
                    "observedItemLevel": 289,
                    "iconUrl": "https://render.worldofwarcraft.com/icons/item-a.jpg",
                },
            },
        }
        community = self.community_release(gear["releaseId"], rows)
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=community,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        binding = {
            "pointerMode": "active",
            "generation": 3,
            "formalActiveManifest": True,
            "manifest": manifest,
            "gearRelease": gear,
            "communityRelease": community,
        }
        rowsets = {
            "FROM cache.websim_community_release_templates": [
                self.community_db_row(rows[0]) + (canonical_row_hash(rows[0]),)
            ],
            "FROM cache.websim_gear_release_variants": [
                (
                    "item-a", "variant-a",
                    "variant-a-id", "item-a", "variant-a", "head", "289", "observed_profile",
                    "mythic", 289, {"ilevel": "289"}, "verified", [],
                    {"resolvedStats": {"intellect": 100}}, "2026-07-11T05:00:00+00:00",
                    canonical_row_hash(snapshot["variants"][0]),
                )
            ],
            "FROM cache.websim_gear_release_items": [
                (
                    "item-a", "Item A", "head", 289, "verified",
                    {
                        "itemStats": [{"key": "intellect", "value": 100}],
                        "_metadata": {
                            "iconUrl": "https://render.worldofwarcraft.com/icons/item-a.jpg",
                            "gameAsset": {"source": "blizzard", "status": "verified"},
                        },
                    },
                    "2026-07-11T05:00:00+00:00", canonical_row_hash(snapshot["items"][0]),
                )
            ],
            "FROM cache.websim_gear_release_sources": [
                (
                    "source-a", "item-a", "observed_profile", "profile:a", "Observed", "", "",
                    "mythic", "season-17", {"status": "verified"},
                    "2026-07-11T05:00:00+00:00", canonical_row_hash(snapshot["sources"][0]),
                )
            ],
            "FROM cache.websim_gear_release_mod_options": [
                (
                    "option-a-id", "variant-a-id", "gem-a", "gem", "Gem A", ["head"],
                    {"gem_id": "1"}, "verified", True,
                    {"itemStats": [{"key": "haste", "value": 10}]},
                    "2026-07-11T05:00:00+00:00", canonical_row_hash(snapshot["options"][0]),
                )
            ],
        }
        return binding, rows, snapshot, rowsets

    def test_active_community_import_reads_one_bound_observed_winner_and_selected_rows(self):
        from server.gear_release_store import GearReleaseStore

        binding, _rows, _snapshot, rowsets = self.active_community_import_fixture()
        conn = FakeConnection(rowsets=rowsets)

        result = GearReleaseStore(lambda: conn).load_active_community_template_import(
            binding, "mage", "arcane", "template-a"
        )

        self.assertEqual(result["winner"]["templateId"], "template-a")
        self.assertEqual(result["winner"]["sourceKey"], "raiderio_observed_profile")
        self.assertEqual(
            result["winner"]["payload"]["importEvidence"]["schemaRevision"],
            "community-template-import-evidence-v1",
        )
        self.assertEqual([row["variantId"] for row in result["variants"]], ["variant-a-id"])
        self.assertEqual([row["itemId"] for row in result["items"]], ["item-a"])
        self.assertEqual(
            result["items"][0]["payload"]["_metadata"]["iconUrl"],
            "https://render.worldofwarcraft.com/icons/item-a.jpg",
        )
        self.assertEqual([row["sourceId"] for row in result["sources"]], ["source-a"])
        self.assertEqual([row["optionKey"] for row in result["options"]], ["gem-a"])
        self.assertEqual(result["binding"]["manifest"]["manifestRevision"], binding["manifest"]["manifestRevision"])
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("template_id = %s", sql)
        self.assertIn("role = 'winner'", sql)
        self.assertIn("source_key = 'raiderio_observed_profile'", sql)
        self.assertIn("requested(item_id, variant_key)", sql)
        self.assertIn("item_id = ANY(%s::text[])", sql)
        self.assertIn("option_key = ANY(%s::text[])", sql)

    def test_candidate_preview_import_uses_the_same_sealed_release_reader(self):
        from server.gear_release_store import GearReleaseStore

        binding, _rows, _snapshot, rowsets = self.active_community_import_fixture()
        binding["formalActiveManifest"] = False
        binding["candidatePreview"] = True
        binding["pointerMode"] = "candidate_preview"

        result = GearReleaseStore(lambda: FakeConnection(rowsets=rowsets)).load_active_community_template_import(
            binding, "mage", "arcane", "template-a"
        )

        self.assertEqual(result["winner"]["templateId"], "template-a")
        self.assertTrue(result["binding"]["candidatePreview"])
        self.assertFalse(result["binding"]["formalActiveManifest"])

    def test_active_community_import_accepts_either_exact_v2_hero_projection_id(self):
        from server.gear_release_store import GearReleaseStore, canonical_row_hash, community_rows_summary

        binding, rows, _snapshot, rowsets = self.active_community_import_fixture()
        row = rows[0]
        template_id = "community-gear:mage:arcane:sunfury:player-a"
        row["templateId"] = template_id
        row["payload"].update({
            "id": template_id,
            "classKey": "mage",
            "specKey": "arcane",
            "heroKey": "sunfury",
            "talentWinnerId": "talent-sunfury-winner",
            "gearProjectionMode": "talent_winner",
            "sourceKey": "raiderio_observed_profile",
            "sourceStatus": "synced",
            "status": "complete",
            "sourceUrl": "https://raider.io/characters/cn/realm/PlayerA",
            "sampleCount": 1,
            "scanRunId": "scan-player-a",
            "readySlotCount": 16,
            "missingSlots": [],
            "gearItems": [{"slot": "head", "itemId": "item-a", "simcReady": True}],
            "payload": {
                "profileHash": "profile:player-a",
                "gearHash": "gear:player-a",
                "character": {"name": "PlayerA", "region": "cn", "realmSlug": "realm"},
            },
        })
        community = gear_release.build_release(
            release_kind="community",
            season_revision=binding["gearRelease"]["seasonRevision"],
            schema_revision="community-release-v2",
            content=community_rows_summary(rows),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "hero-projection-test"},
            validated_against_release_id=binding["gearRelease"]["releaseId"],
        )
        manifest = gear_release.build_manifest(
            season_revision=binding["gearRelease"]["seasonRevision"],
            gear_release=binding["gearRelease"],
            community_release=community,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        binding["communityRelease"] = community
        binding["manifest"] = manifest
        rowsets["FROM cache.websim_community_release_templates"] = [
            self.community_db_row(row) + (canonical_row_hash(row),)
        ]

        result = GearReleaseStore(lambda: FakeConnection(rowsets=rowsets)).load_active_community_template_import(
            binding, "mage", "arcane", template_id,
        )

        self.assertEqual(result["winner"]["templateId"], template_id)
        self.assertEqual(result["winner"]["payload"]["heroKey"], "sunfury")

    def test_active_community_import_rejects_template_id_not_owned_by_requested_spec(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        binding, _rows, _snapshot, rowsets = self.active_community_import_fixture()

        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: FakeConnection(rowsets=rowsets)).load_active_community_template_import(
                binding, "mage", "arcane", "not-template-a"
            )

    def test_active_community_import_rejects_non_observed_or_non_winner_row(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore, canonical_row_hash

        for field, value in (("role", "standby"), ("sourceKey", "season_recommendation")):
            with self.subTest(field=field):
                binding, rows, _snapshot, rowsets = self.active_community_import_fixture()
                rows[0][field] = value
                rowsets["FROM cache.websim_community_release_templates"] = [
                    self.community_db_row(rows[0]) + (canonical_row_hash(rows[0]),)
                ]
                with self.assertRaises(GearReleaseIntegrityError):
                    GearReleaseStore(lambda: FakeConnection(rowsets=rowsets)).load_active_community_template_import(
                        binding, "mage", "arcane", "template-a"
                    )

    def test_active_community_import_rejects_mixed_manifest_release_or_row_hash(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        binding, _rows, _snapshot, rowsets = self.active_community_import_fixture()
        mixed = copy.deepcopy(binding)
        mixed["manifest"]["communityTemplateReleaseId"] = "community-release:sha256:mixed"
        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: FakeConnection(rowsets=rowsets)).load_active_community_template_import(
                mixed, "mage", "arcane", "template-a"
            )

        tampered = copy.deepcopy(rowsets)
        bad_winner = list(tampered["FROM cache.websim_community_release_templates"][0])
        bad_winner[-1] = "sha256:tampered"
        tampered["FROM cache.websim_community_release_templates"] = [tuple(bad_winner)]
        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: FakeConnection(rowsets=tampered)).load_active_community_template_import(
                binding, "mage", "arcane", "template-a"
            )

    def test_active_community_import_never_queries_broad_slot_catalog(self):
        from server.gear_release_store import GearReleaseStore

        binding, _rows, _snapshot, rowsets = self.active_community_import_fixture()
        conn = FakeConnection(rowsets=rowsets)
        GearReleaseStore(lambda: conn).load_active_community_template_import(
            binding, "mage", "arcane", "template-a"
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertNotIn("gear_release_public_counts", sql)
        self.assertNotIn("FROM cache.websim_items", sql)
        self.assertNotIn("FROM cache.websim_community_gear_templates", sql)
        self.assertNotIn("WHERE release_id = %s ORDER BY option_id", sql)
        selected_query_params = conn.cursor_instance.params
        self.assertIn((binding["manifest"]["communityTemplateReleaseId"], "mage", "arcane", "template-a"), selected_query_params)
        self.assertIn((["item-a"], ["variant-a"], binding["gearRelease"]["releaseId"]), selected_query_params)
        self.assertIn((binding["gearRelease"]["releaseId"], ["item-a"]), selected_query_params)
        self.assertIn((binding["gearRelease"]["releaseId"], ["gem-a"]), selected_query_params)

    def test_active_community_import_rebinds_a_normalized_variant_alias_to_one_sealed_variant(self):
        from server.gear_release_store import GearReleaseStore, canonical_row_hash

        binding, _rows, snapshot, rowsets = self.active_community_import_fixture()
        aliased_snapshot = copy.deepcopy(snapshot)
        aliased_snapshot["variants"][0]["variantKey"] = "variant-a!"
        rowsets["FROM cache.websim_gear_release_variants"] = [
            (
                "item-a", "variant-a",
                "variant-a-id", "item-a", "variant-a!", "head", "289", "observed_profile",
                "mythic", 289, {"ilevel": "289"}, "verified", [],
                {"resolvedStats": {"intellect": 100}}, "2026-07-11T05:00:00+00:00",
                canonical_row_hash(aliased_snapshot["variants"][0]),
            )
        ]

        result = GearReleaseStore(lambda: FakeConnection(rowsets=rowsets)).load_active_community_template_import(
            binding, "mage", "arcane", "template-a"
        )

        self.assertEqual(result["variants"][0]["requestedVariantKey"], "variant-a")
        self.assertEqual(result["variants"][0]["variantKey"], "variant-a!")

    def test_active_community_import_reads_sealed_option_from_the_release_not_only_selected_variant(self):
        from server.gear_release_store import GearReleaseStore, canonical_row_hash

        binding, _rows, snapshot, rowsets = self.active_community_import_fixture()
        compatible_option = copy.deepcopy(snapshot["options"][0])
        compatible_option["variantId"] = "compatible-variant-id"
        rowsets["FROM cache.websim_gear_release_mod_options"] = [
            (
                "option-a-id", "compatible-variant-id", "gem-a", "gem", "Gem A", ["head"],
                {"gem_id": "1"}, "verified", True,
                {"itemStats": [{"key": "haste", "value": 10}]},
                "2026-07-11T05:00:00+00:00", canonical_row_hash(compatible_option),
            )
        ]

        result = GearReleaseStore(lambda: FakeConnection(rowsets=rowsets)).load_active_community_template_import(
            binding, "mage", "arcane", "template-a"
        )

        self.assertEqual(result["options"][0]["variantId"], "compatible-variant-id")

    def test_seal_community_release_inserts_elected_rows_without_pointer_write(self):
        from server.gear_release_store import GearReleaseStore

        gear = self.gear_release()
        rows = self.community_rows()
        release = self.community_release(gear["releaseId"], rows)
        conn = FakeConnection(rowsets={"FROM cache.websim_release_registry": []})
        store = GearReleaseStore(lambda: conn)

        result = store.seal_community_release(release, rows, event={"mode": "legacy-import-r0"})

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(result["status"], "inserted")
        self.assertIn("INSERT INTO cache.websim_community_release_templates", sql)
        self.assertIn("INSERT INTO cache.websim_release_events", sql)
        self.assertNotIn("websim_active_manifest_pointer", sql)
        community_call = next(
            values
            for statement, values in conn.cursor_instance.executemany_calls
            if "INSERT INTO cache.websim_community_release_templates" in statement
        )
        self.assertEqual(len(community_call[0]), 22)
        self.assertEqual(community_call[0][19], "2026-07-11T05:00:00+00:00")
        self.assertEqual(community_call[0][20], "2026-07-25T05:00:00+00:00")

    def test_seal_manifest_is_inactive_and_pointer_cas_is_generation_guarded(self):
        from server.gear_release_store import GearReleaseStore, StaleManifestPointerError

        gear = self.gear_release()
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        conn = FakeConnection(rowsets={"FROM cache.websim_season_manifests": []})
        store = GearReleaseStore(lambda: conn)
        result = store.seal_manifest(manifest)
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(result["status"], "inserted")
        self.assertIn("INSERT INTO cache.websim_season_manifests", sql)
        self.assertNotIn("websim_active_manifest_pointer", sql)

        command = gear_release.build_pointer_command(
            "promote",
            manifest["manifestRevision"],
            7,
            "season-manifest:sha256:old",
        )
        cas_conn = FakeConnection(rowcounts={"UPDATE cache.websim_active_manifest_pointer": 1})
        cas = GearReleaseStore(lambda: cas_conn).compare_and_swap_pointer(command, updated_by="candidate-test")
        cas_sql = "\n".join(cas_conn.cursor_instance.statements)
        self.assertEqual(cas["generation"], 8)
        self.assertIn("WHERE environment = 'retail' AND generation = %s", cas_sql)

        stale_conn = FakeConnection(rowcounts={"UPDATE cache.websim_active_manifest_pointer": 0})
        with self.assertRaises(StaleManifestPointerError):
            GearReleaseStore(lambda: stale_conn).compare_and_swap_pointer(command, updated_by="candidate-test")
        self.assertTrue(stale_conn.rolled_back)

    def test_seal_manifest_rejects_tampered_hash_addressed_identity(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        gear = self.gear_release()
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        manifest["talentCatalogRevision"] = "tampered"

        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: FakeConnection()).seal_manifest(manifest)

    def test_manifest_seal_and_pointer_promote_share_one_atomic_transaction(self):
        from server.gear_release_store import GearReleaseStore

        gear = self.gear_release()
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        command = gear_release.build_pointer_command(
            "promote",
            manifest["manifestRevision"],
            0,
        )
        connection_calls = []
        conn = FakeConnection(
            rowsets={"FROM cache.websim_season_manifests": []},
            rowcounts={"INSERT INTO cache.websim_active_manifest_pointer": 1},
        )

        result = GearReleaseStore(lambda: connection_calls.append(conn) or conn).seal_manifest_and_compare_and_swap_pointer(
            manifest,
            command,
            updated_by="candidate-test",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(len(connection_calls), 1)
        self.assertTrue(conn.committed)
        self.assertEqual(result["manifest"]["status"], "inserted")
        self.assertEqual(result["pointer"]["generation"], 1)
        self.assertIn("INSERT INTO cache.websim_season_manifests", sql)
        self.assertIn("INSERT INTO cache.websim_active_manifest_pointer", sql)
        self.assertLess(
            sql.index("INSERT INTO cache.websim_season_manifests"),
            sql.index("INSERT INTO cache.websim_active_manifest_pointer"),
        )

    def test_atomic_manifest_promote_rolls_back_manifest_when_pointer_generation_is_stale(self):
        from server.gear_release_store import GearReleaseStore, StaleManifestPointerError

        gear = self.gear_release()
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        command = gear_release.build_pointer_command("promote", manifest["manifestRevision"], 7)
        conn = FakeConnection(
            rowsets={"FROM cache.websim_season_manifests": []},
            rowcounts={"UPDATE cache.websim_active_manifest_pointer": 0},
        )

        with self.assertRaises(StaleManifestPointerError):
            GearReleaseStore(lambda: conn).seal_manifest_and_compare_and_swap_pointer(
                manifest,
                command,
                updated_by="candidate-test",
            )

        self.assertTrue(conn.rolled_back)
        self.assertFalse(conn.committed)
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("INSERT INTO cache.websim_season_manifests", sql)
        self.assertIn("UPDATE cache.websim_active_manifest_pointer", sql)

    def test_atomic_manifest_promote_rejects_mismatched_or_non_promote_command_before_sql(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        gear = self.gear_release()
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        invalid_commands = (
            gear_release.build_pointer_command("promote", "season-manifest:sha256:other", 0),
            gear_release.build_pointer_command("rollback", manifest["manifestRevision"], 1),
            gear_release.build_pointer_command("rollback", "", 1, target_mode="transitional"),
        )
        for command in invalid_commands:
            with self.subTest(command=command):
                conn = FakeConnection()
                with self.assertRaises((GearReleaseIntegrityError, ValueError)):
                    GearReleaseStore(lambda: conn).seal_manifest_and_compare_and_swap_pointer(
                        manifest,
                        command,
                        updated_by="candidate-test",
                    )
                self.assertEqual(conn.cursor_instance.statements, [])

    def test_pointer_cas_rejects_untrusted_command_shapes_before_sql(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        valid = gear_release.build_pointer_command(
            "promote",
            "season-manifest:sha256:new",
            0,
            "season-manifest:sha256:old",
        )
        invalid_commands = (
            {**valid, "schemaRevision": "unknown"},
            {**valid, "environment": "staging"},
            {**valid, "targetMode": "unknown"},
            {**valid, "manifestRevision": ""},
            {**valid, "expectedGeneration": True},
            {**valid, "expectedGeneration": "0"},
            {**valid, "expectedGeneration": -1},
        )
        for command in invalid_commands:
            with self.subTest(command=command):
                conn = FakeConnection()
                with self.assertRaises((GearReleaseIntegrityError, ValueError)):
                    GearReleaseStore(lambda: conn).compare_and_swap_pointer(
                        command,
                        updated_by="candidate-test",
                    )
                self.assertEqual(conn.cursor_instance.statements, [])

    def test_pointer_cas_keeps_one_row_and_advances_generation_through_transitional_rollback(self):
        from server.gear_release_store import GearReleaseStore

        promote = gear_release.build_pointer_command(
            "promote",
            "season-manifest:sha256:new",
            0,
        )
        first_conn = FakeConnection(rowcounts={"INSERT INTO cache.websim_active_manifest_pointer": 1})
        first = GearReleaseStore(lambda: first_conn).compare_and_swap_pointer(promote, updated_by="candidate-test")
        self.assertEqual(first, {
            "status": "updated",
            "pointerMode": "active",
            "manifestRevision": "season-manifest:sha256:new",
            "generation": 1,
        })
        first_sql = "\n".join(first_conn.cursor_instance.statements)
        self.assertIn("pointer_mode", first_sql)
        self.assertIn("ON CONFLICT (environment) DO NOTHING", first_sql)

        rollback = gear_release.build_pointer_command(
            "rollback",
            "",
            1,
            target_mode="transitional",
        )
        rollback_conn = FakeConnection(rowcounts={"UPDATE cache.websim_active_manifest_pointer": 1})
        rolled_back = GearReleaseStore(lambda: rollback_conn).compare_and_swap_pointer(
            rollback,
            updated_by="candidate-test",
        )
        self.assertEqual(rolled_back, {
            "status": "updated",
            "pointerMode": "transitional",
            "manifestRevision": "",
            "generation": 2,
        })
        rollback_sql = "\n".join(rollback_conn.cursor_instance.statements)
        self.assertIn("SET pointer_mode = %s", rollback_sql)
        self.assertNotIn("DELETE FROM cache.websim_active_manifest_pointer", rollback_sql)

        repromote = gear_release.build_pointer_command(
            "promote",
            "season-manifest:sha256:newer",
            2,
        )
        repromote_conn = FakeConnection(rowcounts={"UPDATE cache.websim_active_manifest_pointer": 1})
        repromoted = GearReleaseStore(lambda: repromote_conn).compare_and_swap_pointer(
            repromote,
            updated_by="candidate-test",
        )
        self.assertEqual(repromoted["generation"], 3)
        self.assertEqual(repromoted["pointerMode"], "active")

    def test_active_pointer_read_exposes_pointer_mode(self):
        from server.gear_release_store import GearReleaseStore

        conn = FakeConnection(rowsets={
            "FROM cache.websim_active_manifest_pointer": [
                ("retail", "transitional", None, 2, None, "2026-07-11T09:00:00+00:00", "candidate-test")
            ]
        })

        pointer = GearReleaseStore(lambda: conn).get_active_pointer()

        self.assertEqual(pointer["pointerMode"], "transitional")
        self.assertEqual(pointer["manifestRevision"], "")
        self.assertEqual(pointer["generation"], 2)

    def test_active_pointer_read_returns_empty_without_legacy_fallback(self):
        from server.gear_release_store import GearReleaseStore

        conn = FakeConnection(rowsets={"FROM cache.websim_active_manifest_pointer": []})
        pointer = GearReleaseStore(lambda: conn).get_active_pointer()
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(pointer, {})
        self.assertIn("FROM cache.websim_active_manifest_pointer", sql)
        self.assertNotIn("websim_season_state", sql)
        self.assertNotIn("websim_sync_state", sql)

    def test_active_manifest_binding_reads_and_validates_one_exact_release_combination(self):
        from server.gear_release_store import GearReleaseStore

        gear = self.gear_release()
        community_rows = self.community_rows()
        community = self.community_release(gear["releaseId"], community_rows)
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=community,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        conn = FakeConnection(rowsets={
            "FROM cache.websim_active_manifest_pointer pointer": [(
                "retail",
                "active",
                manifest["manifestRevision"],
                3,
                None,
                "2026-07-11T09:00:00+00:00",
                "candidate-test",
                manifest,
            )],
            "FROM cache.websim_release_registry": {
                (gear["releaseId"],): [self.release_row(gear)],
                (community["releaseId"],): [self.release_row(community)],
            },
        })

        binding = GearReleaseStore(lambda: conn).load_active_manifest_binding()

        self.assertEqual(binding["pointerMode"], "active")
        self.assertEqual(binding["generation"], 3)
        self.assertTrue(binding["formalActiveManifest"])
        self.assertEqual(binding["manifest"], manifest)
        self.assertEqual(binding["gearRelease"]["releaseId"], gear["releaseId"])
        self.assertEqual(binding["communityRelease"]["releaseId"], community["releaseId"])
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", sql)
        self.assertEqual(sql.count("FROM cache.websim_active_manifest_pointer pointer"), 1)

    def test_active_manifest_v2_binding_loads_catalog_and_exact_in_same_snapshot(self):
        from server.gear_release_store import GearReleaseStore

        gear = self.gear_release()
        community_rows = self.community_rows()
        community = self.community_release(gear["releaseId"], community_rows)
        catalog_revision = "gear-catalog:sha256:" + ("a" * 64)
        exact_registry_revision = "gear-exact-registry:sha256:" + ("b" * 64)
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=community,
            talent_catalog_revision="talent-r1",
            dependency_revisions={
                **self.dependencies(),
                "gearCatalogRevision": catalog_revision,
                "gearExactRegistryRevision": exact_registry_revision,
            },
            catalog_revision=catalog_revision,
            exact_registry_revision=exact_registry_revision,
        )
        catalog = {
            "status": "verified",
            "catalogRevision": catalog_revision,
            "seasonRevision": "season-17",
            "dependencyVector": {
                "gearRuleRevision": self.dependencies()["gearRuleRevision"],
            },
            "provenance": {"sourceGearReleaseId": gear["releaseId"]},
        }
        exact_registry = {
            "status": "partial",
            "registryRevision": exact_registry_revision,
            "catalogRevision": catalog_revision,
            "seasonRevision": "season-17",
            "gearRuleRevision": self.dependencies()["gearRuleRevision"],
        }
        conn = FakeConnection(rowsets={
            "FROM cache.websim_active_manifest_pointer pointer": [(
                "retail",
                "active",
                manifest["manifestRevision"],
                33,
                "season-manifest:sha256:old",
                "2026-07-29T09:00:00+00:00",
                "phase4-test",
                manifest,
            )],
            "FROM cache.websim_release_registry": {
                (gear["releaseId"],): [self.release_row(gear)],
                (community["releaseId"],): [self.release_row(community)],
            },
        })

        with patch(
            "server.gear_release_store.GearCatalogRevisionStore._load_with_cursor",
            return_value=catalog,
        ) as catalog_loader, patch(
            "server.gear_release_store.GearExactItemRegistryStore._load_header_with_cursor",
            return_value=exact_registry,
        ) as exact_loader:
            binding = GearReleaseStore(
                lambda: conn
            ).load_active_manifest_binding()

        self.assertEqual(binding["gearCatalog"], catalog)
        self.assertEqual(binding["gearExactRegistry"], exact_registry)
        catalog_loader.assert_called_once_with(
            conn.cursor_instance,
            catalog_revision,
        )
        exact_loader.assert_called_once_with(
            conn.cursor_instance,
            exact_registry_revision,
        )
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(
            sql.count(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
            ),
            1,
        )

    def test_candidate_manifest_v2_binding_reads_without_the_retail_pointer(self):
        from server.gear_release_store import GearReleaseStore

        gear = self.gear_release()
        community_rows = self.community_rows()
        community = self.community_release(
            gear["releaseId"],
            community_rows,
        )
        catalog_revision = "gear-catalog:sha256:" + ("a" * 64)
        exact_registry_revision = (
            "gear-exact-registry:sha256:" + ("b" * 64)
        )
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=community,
            talent_catalog_revision="talent-r1",
            dependency_revisions={
                **self.dependencies(),
                "gearCatalogRevision": catalog_revision,
                "gearExactRegistryRevision": exact_registry_revision,
            },
            catalog_revision=catalog_revision,
            exact_registry_revision=exact_registry_revision,
        )
        catalog = {
            "status": "verified",
            "catalogRevision": catalog_revision,
            "seasonRevision": "season-17",
            "dependencyVector": {
                "gearRuleRevision": (
                    self.dependencies()["gearRuleRevision"]
                ),
            },
            "provenance": {
                "sourceGearReleaseId": gear["releaseId"],
            },
        }
        exact_registry = {
            "status": "verified",
            "registryRevision": exact_registry_revision,
            "catalogRevision": catalog_revision,
            "seasonRevision": "season-17",
            "gearRuleRevision": self.dependencies()["gearRuleRevision"],
        }
        conn = FakeConnection(rowsets={
            "FROM cache.websim_season_manifests": [(
                manifest,
            )],
            "FROM cache.websim_release_registry": {
                (gear["releaseId"],): [self.release_row(gear)],
                (community["releaseId"],): [
                    self.release_row(community)
                ],
            },
        })

        with patch(
            "server.gear_release_store.GearCatalogRevisionStore._load_with_cursor",
            return_value=catalog,
        ), patch(
            "server.gear_release_store.GearExactItemRegistryStore._load_header_with_cursor",
            return_value=exact_registry,
        ):
            binding = GearReleaseStore(
                lambda: conn
            ).load_candidate_manifest_binding(
                manifest["manifestRevision"]
            )

        self.assertTrue(binding["candidatePreview"])
        self.assertFalse(binding["formalActiveManifest"])
        self.assertEqual(binding["manifest"], manifest)
        self.assertEqual(binding["gearCatalog"], catalog)
        self.assertEqual(binding["gearExactRegistry"], exact_registry)
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertNotIn(
            "FROM cache.websim_active_manifest_pointer",
            sql,
        )

    def test_active_manifest_binding_models_zero_row_and_transitional_without_staging_queries(self):
        from server.gear_release_store import GearReleaseStore

        cases = (
            ([], "pre_cutover", 0),
            ([
                ("retail", "transitional", None, 2, None, "2026-07-11T09:00:00+00:00", "candidate-test", None)
            ], "transitional", 2),
        )
        for rows, expected_mode, expected_generation in cases:
            with self.subTest(expected_mode=expected_mode):
                conn = FakeConnection(rowsets={"FROM cache.websim_active_manifest_pointer pointer": rows})
                binding = GearReleaseStore(lambda: conn).load_active_manifest_binding()
                self.assertEqual(binding["pointerMode"], expected_mode)
                self.assertEqual(binding["generation"], expected_generation)
                self.assertFalse(binding["formalActiveManifest"])
                self.assertNotIn(
                    "FROM cache.websim_release_registry",
                    "\n".join(conn.cursor_instance.statements),
                )

    def test_active_manifest_binding_fails_closed_for_missing_or_invalid_active_release(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        gear = self.gear_release()
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        conn = FakeConnection(rowsets={
            "FROM cache.websim_active_manifest_pointer pointer": [(
                "retail", "active", manifest["manifestRevision"], 1, None,
                "2026-07-11T09:00:00+00:00", "candidate-test", manifest,
            )],
            "FROM cache.websim_release_registry": [],
        })

        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: conn).load_active_manifest_binding()

        self.assertTrue(conn.rolled_back)

    def test_active_public_gear_data_reads_only_bound_immutable_release_rows(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore, canonical_row_hash

        snapshot = copy.deepcopy(self.snapshot())
        snapshot["items"][0]["itemLevel"] = None
        gear = self.gear_release(snapshot)
        community_rows = self.community_rows()
        community_rows[0]["selectionIntent"] = {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": gear["seasonRevision"],
                "gearCatalogRevision": gear["releaseId"],
            },
            "eligibilityContext": {
                "classKey": "mage",
                "specKey": "arcane",
                "level": 90,
            },
            "slots": {
                "head": {
                    "gemOptionIds": ["gem-a", "gem-a"],
                    "enchantOptionId": "enchant-a",
                    "embellishmentOptionId": "embellishment-a",
                },
                "neck": {
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                },
            },
        }
        community_rows[0]["payload"]["enhancementBySlot"] = {
            "head": {"gemOptionIds": ["stale-payload-gem"]},
        }
        community = self.community_release(gear["releaseId"], community_rows)
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=community,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        binding = {
            "pointerMode": "active",
            "generation": 3,
            "formalActiveManifest": True,
            "manifest": manifest,
            "gearRelease": gear,
            "communityRelease": community,
        }
        conn = FakeConnection(rowsets={
            "gear_release_public_counts": [(1, 1, 1, 1)],
            "FROM cache.websim_community_release_templates": [
                self.community_db_row(community_rows[0]) + (canonical_row_hash(community_rows[0]),)
            ],
            "FROM cache.websim_gear_release_items": [
                ("item-a", "Item A", "head", None, "verified", {"itemStats": [{"key": "intellect", "value": 100}]}, "2026-07-11T05:00:00+00:00", canonical_row_hash(snapshot["items"][0]))
            ],
            "FROM cache.websim_gear_release_sources": [
                ("source-a", "item-a", "observed_profile", "profile:a", "Observed", "", "", "mythic", "season-17", {"status": "verified"}, "2026-07-11T05:00:00+00:00", canonical_row_hash(snapshot["sources"][0]))
            ],
            "FROM cache.websim_gear_release_variants": [
                ("variant-a-id", "item-a", "variant-a", "head", "289", "observed_profile", "mythic", 289, {"ilevel": "289"}, "verified", [], {"resolvedStats": {"intellect": 100}}, "2026-07-11T05:00:00+00:00", canonical_row_hash(snapshot["variants"][0]))
            ],
            "FROM cache.websim_gear_release_mod_options": [
                ("option-a-id", "variant-a-id", "gem-a", "gem", "Gem A", ["head"], {"gem_id": "1"}, "verified", True, {"itemStats": [{"key": "haste", "value": 10}]}, "2026-07-11T05:00:00+00:00", canonical_row_hash(snapshot["options"][0]))
            ],
        })

        data = GearReleaseStore(lambda: conn).load_active_public_gear(
            binding,
            "mage",
            "arcane",
            include_catalog=True,
            catalog_slot="head",
        )

        self.assertEqual(data["communityTemplates"], [{
            "id": "template-a",
            "name": "Observed A",
            "canApplyGear": True,
            "enhancementBySlot": {
                "head": {
                    "gemOptionIds": ["gem-a", "gem-a"],
                    "enchantOptionId": "enchant-a",
                    "embellishmentOptionId": "embellishment-a",
                },
            },
        }])
        self.assertNotIn("selectionIntent", data["communityTemplates"][0])
        self.assertEqual(data["gearSnapshot"], snapshot)
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("release_id = %s", sql)
        self.assertIn("gear_release_public_counts", sql)
        self.assertIn("slot = %s", sql)
        self.assertIn("row_hash", sql)
        self.assertNotIn("source_updated_at::text", sql)
        self.assertNotIn("FROM cache.websim_items", sql)
        self.assertNotIn("FROM cache.websim_community_gear_templates", sql)

        tampered_rowsets = copy.deepcopy(conn.cursor_instance.rowsets)
        tampered_item = list(tampered_rowsets["FROM cache.websim_gear_release_items"][0])
        tampered_item[-1] = "sha256:tampered"
        tampered_rowsets["FROM cache.websim_gear_release_items"] = [tuple(tampered_item)]
        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: FakeConnection(rowsets=tampered_rowsets)).load_active_public_gear(
                binding,
                "mage",
                "arcane",
                include_catalog=True,
                catalog_slot="head",
            )

        tampered_community_rowsets = copy.deepcopy(conn.cursor_instance.rowsets)
        tampered_community = list(
            tampered_community_rowsets["FROM cache.websim_community_release_templates"][0]
        )
        tampered_intent = copy.deepcopy(tampered_community[11])
        tampered_intent["slots"]["head"]["gemOptionIds"] = ["forged-gem"]
        tampered_community[11] = tampered_intent
        tampered_community_rowsets["FROM cache.websim_community_release_templates"] = [
            tuple(tampered_community)
        ]
        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(
                lambda: FakeConnection(rowsets=tampered_community_rowsets)
            ).load_active_public_gear(
                binding,
                "mage",
                "arcane",
                include_catalog=True,
                catalog_slot="head",
            )

    def test_active_public_gear_reads_exactly_two_verified_hero_projection_rows(self):
        from server.gear_release_store import GearReleaseStore, canonical_row_hash, community_rows_summary

        snapshot = self.snapshot()
        gear = self.gear_release(snapshot)
        rows = []
        for rank, (hero_key, mode) in enumerate(
            (("sunfury", "talent_winner"), ("spellslinger", "gear_fallback")),
            start=1,
        ):
            template_id = f"community-gear:mage:arcane:{hero_key}:player-{rank}"
            row = copy.deepcopy(self.community_rows()[0])
            row.update({"templateId": template_id, "electionRank": rank})
            row["payload"] = {
                "id": template_id,
                "name": f"{hero_key} player",
                "classKey": "mage",
                "specKey": "arcane",
                "heroKey": hero_key,
                "talentWinnerId": f"talent-{hero_key}-winner",
                "gearProjectionMode": mode,
                "sourceKey": "raiderio_observed_profile",
                "sourceStatus": "synced",
                "status": "complete",
                "sourceUrl": f"https://raider.io/characters/cn/realm/player-{rank}",
                "sampleCount": 1,
                "scanRunId": f"scan-{rank}",
                "readySlotCount": 16,
                "missingSlots": [],
                "gearItems": [{"slot": "head", "itemId": "item-a", "simcReady": True}],
                "payload": {
                    "profileHash": f"profile:{rank}",
                    "gearHash": f"gear:{rank}",
                    "character": {"name": f"Player{rank}", "region": "cn", "realmSlug": "realm"},
                },
            }
            rows.append(row)
        community = gear_release.build_release(
            release_kind="community",
            season_revision="season-17",
            schema_revision="community-release-v2",
            content=community_rows_summary(rows),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "hero-projection-test"},
            validated_against_release_id=gear["releaseId"],
        )
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=community,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        binding = {
            "pointerMode": "active", "generation": 3, "formalActiveManifest": True,
            "manifest": manifest, "gearRelease": gear, "communityRelease": community,
        }
        conn = FakeConnection(rowsets={
            "gear_release_public_counts": [(1, 1, 1, 1)],
            "FROM cache.websim_community_release_templates": [
                self.community_db_row(row) + (canonical_row_hash(row),)
                for row in rows
            ],
        })

        data = GearReleaseStore(lambda: conn).load_active_public_gear(
            binding, "mage", "arcane", include_catalog=False,
        )

        self.assertEqual(
            [(template["heroKey"], template["gearProjectionMode"]) for template in data["communityTemplates"]],
            [("sunfury", "talent_winner"), ("spellslinger", "gear_fallback")],
        )

    def test_active_observed_compile_context_reads_only_actual_player_dependencies(self):
        from server import gear_release_store
        from server.gear_release_store import GearReleaseStore, canonical_row_hash

        snapshot = self.snapshot()
        gear = self.gear_release(snapshot)
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        binding = {
            "pointerMode": "candidate",
            "generation": 4,
            "formalActiveManifest": False,
            "candidatePreview": True,
            "manifest": manifest,
            "gearRelease": gear,
            "communityRelease": None,
        }
        conn = FakeConnection(rowsets={
            "gear_release_observed_compile_counts": [(1, 1, 1, 1)],
            "gear_release_observed_compile_items": [
                (
                    "item-a",
                    "Item A",
                    "head",
                    289,
                    "verified",
                    {"itemStats": [{"key": "intellect", "value": 100}]},
                    "2026-07-11T05:00:00+00:00",
                    canonical_row_hash(snapshot["items"][0]),
                ),
            ],
            "gear_release_observed_compile_variants": [
                (
                    "variant-a-id",
                    "item-a",
                    "variant-a",
                    "head",
                    "289",
                    "observed_profile",
                    "mythic",
                    289,
                    {"ilevel": "289"},
                    "verified",
                    [],
                    {"resolvedStats": {"intellect": 100}},
                    "2026-07-11T05:00:00+00:00",
                    canonical_row_hash(snapshot["variants"][0]),
                ),
            ],
            "gear_release_observed_compile_options": [
                (
                    "option-a-id",
                    "variant-a-id",
                    "gem-a",
                    "gem",
                    "Gem A",
                    ["head"],
                    {"gem_id": "1"},
                    "verified",
                    True,
                    {"itemStats": [{"key": "haste", "value": 10}]},
                    "2026-07-11T05:00:00+00:00",
                    canonical_row_hash(snapshot["options"][0]),
                ),
            ],
        })

        data = GearReleaseStore(lambda: conn).load_active_observed_compile_context(
            binding,
            [
                {
                    "itemId": "item-a",
                    "slot": "head",
                    "gems": [{"itemId": 1}],
                },
            ],
        )

        self.assertEqual(data["gearRelease"]["releaseId"], gear["releaseId"])
        self.assertEqual(data["gearSnapshot"]["items"], snapshot["items"])
        self.assertEqual(data["gearSnapshot"]["variants"], snapshot["variants"])
        self.assertEqual(data["gearSnapshot"]["options"], snapshot["options"])
        self.assertEqual(data["gearSnapshot"]["sources"], [])
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("gear_release_observed_compile_counts", sql)
        self.assertIn("item_id = ANY(%s::text[])", sql)
        self.assertIn("simc_options_json->>'gem_id' = ANY(%s::text[])", sql)
        self.assertNotIn("FROM cache.websim_community_release_templates", sql)
        self.assertNotIn("SELECT source_id, item_id", sql)
        self.assertEqual(
            conn.cursor_instance.params[-1],
            (gear["releaseId"], ["1"], [], []),
        )

        tampered = copy.deepcopy(conn.cursor_instance.rowsets)
        unrelated_option = list(tampered["gear_release_observed_compile_options"][0])
        unrelated_option[-1] = "sha256:tampered"
        tampered["gear_release_observed_compile_options"] = [tuple(unrelated_option)]
        with self.assertRaisesRegex(
            gear_release_store.GearReleaseIntegrityError,
            "option row integrity",
        ):
            GearReleaseStore(
                lambda: FakeConnection(rowsets=tampered)
            ).load_active_observed_compile_context(
                binding,
                [{"itemId": "item-a", "slot": "head", "gem_id": "1"}],
            )

    def test_active_resolver_context_is_manifest_bound_and_rejects_runtime_drift(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        gear = self.gear_release()
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        binding = {
            "pointerMode": "active",
            "generation": 3,
            "formalActiveManifest": True,
            "manifest": manifest,
            "gearRelease": gear,
            "communityRelease": None,
        }
        runtime = {
            "dependencyRevisions": {
                **self.dependencies(),
                "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
            },
            "supportedCapabilityRevisions": list(
                gear_socket_authority.SUPPORTED_CAPABILITY_REVISIONS
            ),
        }

        context = GearReleaseStore(lambda: FakeConnection()).active_resolver_context(binding, runtime)

        self.assertTrue(context["formalActiveManifest"])
        self.assertEqual(context["manifestRevision"], manifest["manifestRevision"])
        self.assertEqual(context["pointerGeneration"], 3)
        self.assertEqual(context["authoredAgainst"], {
            "seasonRevision": "season-17",
            "gearCatalogRevision": gear["releaseId"],
        })

        drifted = copy.deepcopy(runtime)
        drifted["dependencyRevisions"]["simcRuntimeRevision"] = "simc-other"
        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: FakeConnection()).active_resolver_context(binding, drifted)

    def test_active_reader_accepts_supported_v1_manifest_during_v2_rollout(self):
        from server.gear_release_store import GearReleaseStore

        gear = self.gear_release()
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        binding = {
            "pointerMode": "active",
            "generation": 3,
            "formalActiveManifest": True,
            "manifest": manifest,
            "gearRelease": gear,
            "communityRelease": None,
        }
        runtime_dependencies = {
            **self.dependencies(),
            "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
        }
        runtime = {
            "dependencyRevisions": runtime_dependencies,
            "supportedCapabilityRevisions": list(
                gear_socket_authority.SUPPORTED_CAPABILITY_REVISIONS
            ),
        }

        context = GearReleaseStore(lambda: FakeConnection()).active_resolver_context(
            binding,
            runtime,
        )

        self.assertEqual(
            context["dependencyRevisions"]["capabilityRevision"],
            gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        )

    def test_active_reader_rejects_unsupported_capability_revision(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        future_dependencies = {
            **self.dependencies(),
            "capabilityRevision": "gear-capability-matrix-v3",
        }
        gear = self.gear_release(dependencies=future_dependencies)
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=future_dependencies,
        )
        binding = {
            "pointerMode": "active",
            "generation": 4,
            "formalActiveManifest": True,
            "manifest": manifest,
            "gearRelease": gear,
            "communityRelease": None,
        }
        runtime = {
            "dependencyRevisions": {
                **self.dependencies(),
                "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
            },
            "supportedCapabilityRevisions": list(
                gear_socket_authority.SUPPORTED_CAPABILITY_REVISIONS
            ),
        }

        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: FakeConnection()).active_resolver_context(
                binding,
                runtime,
            )

        missing_binding = copy.deepcopy(binding)
        missing_binding["manifest"]["dependencyRevisions"].pop(
            "capabilityRevision"
        )
        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: FakeConnection()).active_resolver_context(
                missing_binding,
                runtime,
            )

    def test_active_authority_reads_current_release_for_stale_intent_so_resolver_can_report_409(self):
        from server.gear_release_store import GearReleaseStore

        gear = self.gear_release()
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions=self.dependencies(),
        )
        binding = {
            "pointerMode": "active",
            "generation": 3,
            "formalActiveManifest": True,
            "manifest": manifest,
            "gearRelease": gear,
            "communityRelease": None,
        }
        runtime = {
            "dependencyRevisions": {
                **self.dependencies(),
                "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
            },
            "supportedCapabilityRevisions": list(
                gear_socket_authority.SUPPORTED_CAPABILITY_REVISIONS
            ),
        }
        stale_intent = {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-16",
                "gearCatalogRevision": "gear-release:stale",
            },
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90},
            "slots": {},
        }
        original_intent = copy.deepcopy(stale_intent)
        loaded_intents = []
        store = GearReleaseStore(lambda: FakeConnection())

        def load_current_release(intent, runtime_authority, release_id):
            loaded_intents.append(copy.deepcopy(intent))
            self.assertEqual(intent["authoredAgainst"], {
                "seasonRevision": "season-17",
                "gearCatalogRevision": gear["releaseId"],
            })
            self.assertIs(runtime_authority, runtime)
            self.assertEqual(release_id, gear["releaseId"])
            return {"missingFields": [], "itemsById": {}, "variantsByKey": {}, "optionsById": {}}

        store.load_candidate_authority_context = load_current_release

        context = store.load_active_authority_context(stale_intent, runtime, binding)

        self.assertEqual(stale_intent, original_intent)
        self.assertEqual(len(loaded_intents), 1)
        self.assertTrue(context["manifest"]["formalActiveManifest"])
        self.assertEqual(context["manifest"]["gearCatalogRevision"], gear["releaseId"])
        self.assertEqual(context["dependencyVector"]["gearCatalogRevision"], gear["releaseId"])

    def test_manifest_v2_authority_maps_browse_identity_to_bound_source_variant(self):
        from server.gear_release_store import (
            GearReleaseIntegrityError,
            GearReleaseStore,
        )

        gear = self.gear_release()
        catalog_revision = "gear-catalog:sha256:" + ("a" * 64)
        exact_registry_revision = "gear-exact-registry:sha256:" + ("b" * 64)
        browse_key = "browse-variant:sha256:" + ("c" * 64)
        manifest = gear_release.build_manifest(
            season_revision="season-17",
            gear_release=gear,
            community_release=None,
            talent_catalog_revision="talent-r1",
            dependency_revisions={
                **self.dependencies(),
                "gearCatalogRevision": catalog_revision,
                "gearExactRegistryRevision": exact_registry_revision,
            },
            catalog_revision=catalog_revision,
            exact_registry_revision=exact_registry_revision,
        )
        binding = {
            "pointerMode": "active",
            "generation": 33,
            "formalActiveManifest": True,
            "manifest": manifest,
            "gearRelease": gear,
            "communityRelease": None,
            "gearCatalog": {
                "catalogRevision": catalog_revision,
                "browseVariants": [
                    {
                        "browseVariantKey": browse_key,
                        "itemId": "item-a",
                        "sourceVariantKeys": [
                            "observed-template-a",
                            "variant-a",
                        ],
                        "canonicalSourceVariantKey": "variant-a",
                        "itemLevel": 276,
                        "bonusIds": ["13334"],
                        "staticFacts": {"intellect": 100},
                    }
                ],
            },
            "gearExactRegistry": {
                "registryRevision": exact_registry_revision,
            },
        }
        runtime = {
            "dependencyRevisions": {
                **self.dependencies(),
                "capabilityRevision": (
                    gear_socket_authority.CAPABILITY_REVISION
                ),
            },
            "supportedCapabilityRevisions": list(
                gear_socket_authority.SUPPORTED_CAPABILITY_REVISIONS
            ),
        }
        intent = {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": catalog_revision,
            },
            "eligibilityContext": {
                "classKey": "mage",
                "specKey": "arcane",
                "level": 90,
            },
            "slots": {
                "head": {
                    "itemId": "item-a",
                    "variantKey": browse_key,
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            },
        }
        store = GearReleaseStore(lambda: FakeConnection())

        def load_source_authority(translated, _runtime, release_id):
            self.assertEqual(release_id, gear["releaseId"])
            self.assertEqual(
                translated["authoredAgainst"]["gearCatalogRevision"],
                gear["releaseId"],
            )
            self.assertEqual(
                translated["slots"]["head"]["variantKey"],
                "variant-a",
            )
            return {
                "missingFields": [],
                "itemsById": {
                    "item-a": {
                        "itemId": "item-a",
                        "variantKeys": ["variant-a"],
                    }
                },
                "variantsByKey": {
                    "variant-a": {
                        "itemId": "item-a",
                        "variantKey": "variant-a",
                        "serializerInput": {"id": "item-a"},
                    }
                },
                "optionsById": {},
            }

        store.load_candidate_authority_context = load_source_authority

        context = store.load_active_authority_context(
            intent,
            runtime,
            binding,
            source_variant_overrides={
                "head": "observed-template-a",
            },
        )

        self.assertEqual(
            context["manifest"]["gearCatalogRevision"],
            catalog_revision,
        )
        self.assertIn(browse_key, context["variantsByKey"])
        self.assertEqual(
            context["variantsByKey"][browse_key]["sourceVariantKey"],
            "variant-a",
        )
        self.assertEqual(
            context["variantsByKey"][browse_key]["resolvedStats"],
            {"intellect": 100},
        )
        self.assertEqual(
            context["variantsByKey"][browse_key]["simcOptions"],
            {"bonus_id": "13334", "ilevel": "276"},
        )
        self.assertEqual(
            context["itemsById"]["item-a"]["variantKeys"],
            [browse_key],
        )
        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "outside its Manifest Catalog shape",
        ):
            store.load_active_authority_context(
                intent,
                runtime,
                binding,
                source_variant_overrides={
                    "head": "invented-source",
                },
            )

    def test_manifest_catalog_snapshot_projects_canonical_browse_membership(self):
        from server.gear_release_store import _manifest_catalog_snapshot

        browse_key = "browse-variant:sha256:" + ("c" * 64)
        catalog = {
            "status": "verified",
            "catalogRevision": (
                "gear-catalog:sha256:" + ("a" * 64)
            ),
            "itemDefinitions": [
                {
                    "itemId": "item-a",
                    "name": "Item A",
                    "slot": "head",
                    "itemLevel": 289,
                    "sourceStatus": "verified",
                    "media": {"iconUrl": "/runtime-media/item-a.webp"},
                    "equipment": {
                        "armorType": "Plate",
                        "inventoryType": "head",
                    },
                    "restrictions": {"requiredClassIds": ["8"]},
                    "sources": [
                        {
                            "sourceIdentity": "catalog-source:sha256:test",
                            "sourceType": "raid",
                            "sourceKey": "raid-a",
                            "difficultyKey": "mythic",
                            "seasonRevision": "season-17",
                            "status": "verified",
                        },
                        {
                            "sourceIdentity": "catalog-source:sha256:fallback",
                            "sourceType": "dungeon",
                            "sourceKey": "opaque-dungeon-key",
                            "difficultyKey": "heroic",
                            "seasonRevision": "season-17",
                            "status": "verified",
                        },
                    ],
                }
            ],
            "browseVariants": [
                {
                    "browseVariantKey": browse_key,
                    "itemId": "item-a",
                    "progressionKind": "upgrade_track",
                    "progressionState": {
                        "kind": "upgrade_track",
                        "trackKey": "hero",
                        "rank": 6,
                        "rankMax": 6,
                    },
                    "itemLevel": 289,
                    "bonusIds": ["1", "2"],
                    "staticFacts": {"intellect": 100},
                    "sourceType": "raid",
                    "sourceVariantKeys": ["variant-a"],
                    "evidenceStatus": "verified",
                }
            ],
        }
        legacy_snapshot = {
            "items": [{"itemId": "legacy-must-not-leak"}],
            "sources": [
                {"sourceId": "legacy-must-not-leak"},
                {
                    "sourceId": "display-source-a",
                    "itemId": "item-a",
                    "sourceType": "raid",
                    "sourceKey": "raid-a",
                    "difficultyKey": "mythic",
                    "seasonRevision": "season-17",
                    "sourceLabel": "首领 A - 团队副本 A",
                },
            ],
            "variants": [{"variantId": "legacy-must-not-leak"}],
            "options": [{"optionId": "option-a"}],
        }

        snapshot = _manifest_catalog_snapshot(
            catalog,
            legacy_snapshot,
            catalog_slot="head",
        )

        self.assertEqual(
            [row["itemId"] for row in snapshot["items"]],
            ["item-a"],
        )
        self.assertEqual(
            [row["variantKey"] for row in snapshot["variants"]],
            [browse_key],
        )
        self.assertEqual(
            snapshot["variants"][0]["payload"]["sourceVariantKeys"],
            ["variant-a"],
        )
        self.assertEqual(
            snapshot["variants"][0]["payload"]["itemStats"],
            [{"key": "intellect", "label": "智力", "value": 100}],
        )
        self.assertEqual(
            snapshot["variants"][0]["payload"]["statDisplayStatus"],
            "verified_variant",
        )
        self.assertEqual(
            snapshot["variants"][0]["payload"]["catalogEvidenceStatus"],
            "verified",
        )
        self.assertEqual(
            snapshot["variants"][0]["payload"]["progressionState"],
            {
                "kind": "upgrade_track",
                "trackKey": "hero",
                "rank": 6,
                "rankMax": 6,
            },
        )
        self.assertEqual(
            snapshot["items"][0]["payload"]["armorType"],
            "Plate",
        )
        self.assertEqual(
            snapshot["sources"][0]["sourceLabel"],
            "首领 A - 团队副本 A",
        )
        self.assertNotEqual(snapshot["sources"][0]["sourceLabel"], "raid-a")
        self.assertEqual(
            snapshot["sources"][1]["sourceLabel"],
            "地下城 · 英雄",
        )
        self.assertNotEqual(
            snapshot["sources"][1]["sourceLabel"],
            "opaque-dungeon-key",
        )
        self.assertEqual(snapshot["options"], [{"optionId": "option-a"}])
        self.assertNotIn("legacy-must-not-leak", str(snapshot))

    def test_manifest_catalog_snapshot_expands_equivalent_and_offhand_source_slots(self):
        from server.gear_release_store import _manifest_catalog_snapshot

        catalog = {
            "status": "verified",
            "catalogRevision": (
                "gear-catalog:sha256:" + ("a" * 64)
            ),
            "itemDefinitions": [],
            "browseVariants": [],
        }
        for index, (item_id, slot) in enumerate(
            (
                ("ring-a", "finger1"),
                ("trinket-a", "trinket1"),
                ("dagger-a", "main_hand"),
            )
        ):
            catalog["itemDefinitions"].append(
                {
                    "itemId": item_id,
                    "name": item_id,
                    "slot": slot,
                    "itemLevel": 289,
                    "sourceStatus": "verified",
                    "equipment": {
                        "weaponType": (
                            "Dagger" if slot == "main_hand" else ""
                        ),
                    },
                    "sources": [
                        {
                            "sourceIdentity": (
                                f"catalog-source:sha256:{index}"
                            ),
                            "sourceType": "raid",
                            "sourceKey": f"raid-{index}",
                            "difficultyKey": "mythic",
                            "seasonRevision": "season-17",
                            "status": "verified",
                        }
                    ],
                }
            )
            catalog["browseVariants"].append(
                {
                    "browseVariantKey": (
                        f"browse-variant:sha256:{index:064x}"
                    ),
                    "itemId": item_id,
                    "progressionState": {
                        "kind": "upgrade_track",
                        "trackKey": "myth",
                        "rank": 6,
                        "rankMax": 6,
                    },
                    "itemLevel": 289,
                    "bonusIds": [str(index + 1)],
                    "staticFacts": {"stamina": 100 + index},
                    "sourceType": "raid",
                    "sourceVariantKeys": [f"variant-{index}"],
                    "evidenceStatus": "verified",
                }
            )

        finger2 = _manifest_catalog_snapshot(
            catalog,
            {},
            catalog_slot="finger2",
        )
        trinket2 = _manifest_catalog_snapshot(
            catalog,
            {},
            catalog_slot="trinket2",
        )
        off_hand = _manifest_catalog_snapshot(
            catalog,
            {},
            catalog_slot="off_hand",
        )

        self.assertEqual(
            [row["itemId"] for row in finger2["items"]],
            ["ring-a"],
        )
        self.assertEqual(
            [row["itemId"] for row in trinket2["items"]],
            ["trinket-a"],
        )
        self.assertEqual(
            [row["itemId"] for row in off_hand["items"]],
            ["dagger-a"],
        )

    def test_manifest_v2_public_gear_projects_only_the_bound_catalog(self):
        from server.gear_release_store import GearReleaseStore

        catalog_revision = "gear-catalog:sha256:" + ("a" * 64)
        exact_revision = "gear-exact-registry:sha256:" + ("b" * 64)
        browse_key = "browse-variant:sha256:" + ("c" * 64)
        binding = {
            "formalActiveManifest": True,
            "manifest": {
                "schemaRevision": "active-season-manifest-v2",
                "gearCatalogReleaseId": "gear-release-a",
                "gearCatalogRevision": catalog_revision,
                "gearExactRegistryRevision": exact_revision,
                "communityTemplateReleaseId": "community-release-a",
            },
            "gearCatalog": {
                "status": "verified",
                "catalogRevision": catalog_revision,
                "itemDefinitions": [{
                    "itemId": "item-a",
                    "name": "Item A",
                    "slot": "head",
                    "itemLevel": 289,
                    "sourceStatus": "verified",
                    "sources": [{
                        "sourceIdentity": "catalog-source:sha256:test",
                        "sourceType": "raid",
                        "sourceKey": "raid-a",
                        "difficultyKey": "mythic",
                        "seasonRevision": "season-17",
                        "status": "verified",
                    }],
                }],
                "browseVariants": [{
                    "browseVariantKey": browse_key,
                    "itemId": "item-a",
                    "progressionState": {
                        "trackKey": "hero",
                        "rank": 6,
                        "rankMax": 6,
                    },
                    "itemLevel": 289,
                    "bonusIds": ["1"],
                    "staticFacts": {"intellect": 100},
                    "sourceVariantKeys": ["variant-a"],
                    "evidenceStatus": "verified",
                }],
            },
            "gearExactRegistry": {
                "registryRevision": exact_revision,
                "status": "verified",
            },
        }
        store = GearReleaseStore(lambda: self.fail("unit test must not open PostgreSQL"))
        calls = []

        def load_material(
            exact_binding,
            class_key,
            spec_key,
            *,
            include_catalog,
            catalog_slot="",
            catalog_options_only=False,
        ):
            calls.append(
                (
                    exact_binding,
                    class_key,
                    spec_key,
                    include_catalog,
                    catalog_slot,
                    catalog_options_only,
                )
            )
            return {
                "gearRelease": {
                    "releaseId": "gear-release-a",
                    "releaseStatus": "validated",
                },
                "communityRelease": {"releaseId": "community-release-a"},
                "communityTemplates": [{"id": "template-a"}],
                "gearSnapshot": {
                    "items": [{"itemId": "legacy-must-not-leak"}],
                    "sources": [{"sourceId": "legacy-must-not-leak"}],
                    "variants": [{"variantId": "legacy-must-not-leak"}],
                    "options": [{"optionId": "option-a"}],
                },
            }

        store._load_public_release_material = load_material
        result = store.load_active_manifest_public_gear(
            binding,
            "mage",
            "arcane",
            include_catalog=True,
            catalog_slot="head",
        )

        self.assertEqual(
            calls,
            [(binding, "mage", "arcane", True, "head", True)],
        )
        self.assertEqual(
            [row["variantKey"] for row in result["gearSnapshot"]["variants"]],
            [browse_key],
        )
        self.assertNotIn("legacy-must-not-leak", str(result["gearSnapshot"]))
        self.assertIs(result["gearCatalog"], binding["gearCatalog"])
        self.assertIs(
            result["gearExactRegistry"],
            binding["gearExactRegistry"],
        )

    def test_manifest_v2_public_gear_does_not_materialize_legacy_catalog_rows(self):
        from server.gear_release_store import (
            GearReleaseStore,
            canonical_row_hash,
        )

        snapshot = self.snapshot()
        gear = self.gear_release(snapshot)
        catalog_revision = "gear-catalog:sha256:" + ("a" * 64)
        exact_revision = "gear-exact-registry:sha256:" + ("b" * 64)
        browse_key = "browse-variant:sha256:" + ("c" * 64)
        binding = {
            "formalActiveManifest": True,
            "manifest": {
                "schemaRevision": "active-season-manifest-v2",
                "gearCatalogReleaseId": gear["releaseId"],
                "gearCatalogRevision": catalog_revision,
                "gearExactRegistryRevision": exact_revision,
                "communityTemplateReleaseId": "",
            },
            "gearRelease": gear,
            "communityRelease": None,
            "gearCatalog": {
                "status": "verified",
                "catalogRevision": catalog_revision,
                "itemDefinitions": [
                    {
                        "itemId": "item-a",
                        "name": "Item A",
                        "slot": "head",
                        "itemLevel": 289,
                        "sourceStatus": "verified",
                        "sources": [
                            {
                                "sourceIdentity": "catalog-source:sha256:test",
                                "sourceType": "raid",
                                "sourceKey": "raid-a",
                                "difficultyKey": "mythic",
                                "seasonRevision": "season-17",
                                "status": "verified",
                            }
                        ],
                    }
                ],
                "browseVariants": [
                    {
                        "browseVariantKey": browse_key,
                        "itemId": "item-a",
                        "progressionState": {
                            "trackKey": "hero",
                            "rank": 6,
                            "rankMax": 6,
                        },
                        "itemLevel": 289,
                        "bonusIds": ["1"],
                        "staticFacts": {"intellect": 100},
                        "sourceVariantKeys": ["variant-a"],
                        "evidenceStatus": "verified",
                    }
                ],
            },
            "gearExactRegistry": {
                "registryRevision": exact_revision,
                "status": "verified",
            },
        }
        conn = FakeConnection(
            rowsets={
                "gear_release_public_counts": [(1, 1, 1, 1)],
                "FROM cache.websim_gear_release_mod_options": [
                    (
                        "option-a-id",
                        "variant-a-id",
                        "gem-a",
                        "gem",
                        "Gem A",
                        ["head"],
                        {"gem_id": "1"},
                        "verified",
                        True,
                        {"itemStats": [{"key": "haste", "value": 10}]},
                        "2026-07-11T05:00:00+00:00",
                        canonical_row_hash(snapshot["options"][0]),
                    )
                ],
            }
        )

        result = GearReleaseStore(
            lambda: conn
        ).load_active_manifest_public_gear(
            binding,
            "mage",
            "arcane",
            include_catalog=True,
        )

        sql = "\n".join(conn.cursor_instance.statements)
        catalog_row_sql = "\n".join(
            statement
            for statement in conn.cursor_instance.statements
            if "gear_release_public_counts" not in statement
        )
        self.assertIn("gear_release_public_counts", sql)
        self.assertIn("FROM cache.websim_gear_release_mod_options", sql)
        self.assertNotIn(
            "FROM cache.websim_gear_release_items",
            catalog_row_sql,
        )
        self.assertNotIn(
            "FROM cache.websim_gear_release_sources",
            catalog_row_sql,
        )
        self.assertNotIn(
            "FROM cache.websim_gear_release_variants",
            catalog_row_sql,
        )
        self.assertEqual(
            [row["variantKey"] for row in result["gearSnapshot"]["variants"]],
            [browse_key],
        )
        self.assertEqual(result["gearSnapshot"]["options"], snapshot["options"])

    def test_candidate_authority_reads_one_exact_release_without_staging_fallback(self):
        from server.gear_release_store import GearReleaseStore
        from server.websim_payload import gear_resolver_runtime_authority

        snapshot = self.snapshot()
        release = self.gear_release(snapshot)
        intent = {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": release["releaseId"],
            },
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90},
            "slots": {
                "head": {
                    "itemId": "item-a",
                    "variantKey": "variant-a",
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            },
        }
        runtime = gear_resolver_runtime_authority("mage", "arcane", simc_runtime_revision="simc-r1")
        runtime["dependencyRevisions"]["capabilityRevision"] = (
            gear_socket_authority.LEGACY_CAPABILITY_REVISION
        )
        item_record = {
            "id": "item-a",
            "name": "Item A",
            "slot": "head",
            "itemLevel": 289,
            "sourceStatus": "verified",
            "itemSetIds": [],
            "payload": {"itemStats": [{"key": "intellect", "value": 100}]},
            "updatedAt": "2026-07-11T05:00:00+00:00",
        }
        variant_record = {
            "id": "variant-a-id",
            "itemId": "item-a",
            "slot": "head",
            "variantKey": "variant-a",
            "label": "289",
            "sourceType": "observed_profile",
            "difficultyKey": "mythic",
            "itemLevel": 289,
            "simcOptions": {"ilevel": "289"},
            "status": "verified",
            "blockers": [],
            "payload": {"resolvedStats": {"intellect": 100}},
            "updatedAt": "2026-07-11T05:00:00+00:00",
        }
        source_records = [{
            "id": "source-a",
            "sourceType": "observed_profile",
            "sourceKey": "profile:a",
            "sourceLabel": "Observed",
            "difficultyKey": "mythic",
            "seasonRevision": "season-17",
            "status": "unknown",
            "sourceStatus": "unknown",
            "payload": {
                "variantKey": "variant-a",
                "slot": "head",
                "itemId": "item-a",
                "ilevel": "289",
                "bonus_id": "100/200",
                "statSource": "simulationcraft",
                "itemStats": [{"key": "intellect", "value": 100}],
            },
            "updatedAt": "2026-07-11T05:00:00+00:00",
        }]
        conn = FakeConnection(rowsets={
            "FROM cache.websim_release_registry": [self.release_row(release)],
            "gear_release_authority_items_variants": [
                ("item-a", "variant-a", item_record, None, source_records)
            ],
            "gear_release_authority_options": [],
        })

        context = GearReleaseStore(lambda: conn).load_candidate_authority_context(
            intent,
            runtime,
            release["releaseId"],
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", sql)
        self.assertIn("cache.websim_gear_release_items", sql)
        self.assertIn("cache.websim_gear_release_variants", sql)
        self.assertIn("cache.websim_gear_release_sources", sql)
        self.assertIn("cache.websim_gear_release_mod_options", sql)
        self.assertIn("regexp_replace(variant.variant_key", " ".join(sql.split()))
        self.assertNotIn("FROM cache.websim_items", sql)
        self.assertNotIn("FROM cache.websim_gear_variants", sql)
        self.assertEqual(context["manifest"]["gearCatalogReleaseId"], release["releaseId"])
        self.assertEqual(context["manifest"]["manifestType"], "candidate_shadow")
        self.assertFalse(context["manifest"]["formalActiveManifest"])
        self.assertEqual(context["missingFields"], [])
        self.assertEqual(context["variantsByKey"]["variant-a"]["simcOptions"], {
            "bonus_id": "100/200",
            "ilevel": "289",
        })

    def test_candidate_authority_prefers_exact_variant_over_divergent_normalized_alias(self):
        from server.gear_release_store import (
            GearReleaseStore,
            build_candidate_authority_context,
        )
        from server.websim_payload import gear_resolver_runtime_authority

        requested_key = "observed_profile-head-289-bonus_id:123ilevel:289"
        alias_key = 'observed_profile-head-289-{"bonus_id": "123", "ilevel": "289"}'
        snapshot = self.snapshot()
        snapshot["variants"][0].update({
            "variantKey": requested_key,
            "simcOptions": {"bonus_id": "123", "ilevel": "289"},
        })
        alias = copy.deepcopy(snapshot["variants"][0])
        alias.update({
            "variantId": "variant-alias-divergent",
            "variantKey": alias_key,
            "simcOptions": {"bonus_id": "divergent", "ilevel": "289"},
        })
        snapshot["variants"].append(alias)
        release = self.gear_release(snapshot)
        intent = {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": release["seasonRevision"],
                "gearCatalogRevision": release["releaseId"],
            },
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90},
            "slots": {
                "head": {
                    "itemId": "item-a",
                    "variantKey": requested_key,
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            },
        }
        runtime = gear_resolver_runtime_authority(
            "mage",
            "arcane",
            simc_runtime_revision="simc-r1",
        )
        runtime["dependencyRevisions"]["capabilityRevision"] = (
            gear_socket_authority.LEGACY_CAPABILITY_REVISION
        )

        memory_context = build_candidate_authority_context(
            snapshot,
            intent,
            runtime,
            release,
        )
        self.assertEqual(memory_context["missingFields"], [])
        self.assertEqual(
            memory_context["variantsByKey"][requested_key]["simcOptions"]["bonus_id"],
            "123",
        )

        item = snapshot["items"][0]
        item_record = {
            "id": item["itemId"],
            "name": item["name"],
            "slot": item["slot"],
            "itemLevel": item["itemLevel"],
            "sourceStatus": item["sourceStatus"],
            "itemSetIds": [],
            "payload": item["payload"],
            "updatedAt": item["updatedAt"],
        }

        def variant_record(row):
            return {
                "id": row["variantId"],
                "itemId": row["itemId"],
                "slot": row["slot"],
                "variantKey": row["variantKey"],
                "label": row["label"],
                "sourceType": row["sourceType"],
                "difficultyKey": row["difficultyKey"],
                "itemLevel": row["itemLevel"],
                "simcOptions": row["simcOptions"],
                "status": row["status"],
                "blockers": row["blockers"],
                "payload": row["payload"],
                "updatedAt": row["updatedAt"],
            }

        source = snapshot["sources"][0]
        source_records = [{
            "id": source["sourceId"],
            "sourceType": source["sourceType"],
            "sourceKey": source["sourceKey"],
            "sourceLabel": source["sourceLabel"],
            "instanceId": source["instanceId"],
            "encounterId": source["encounterId"],
            "difficultyKey": source["difficultyKey"],
            "seasonRevision": source["seasonRevision"],
            "status": "verified",
            "sourceStatus": "verified",
            "payload": source["payload"],
            "updatedAt": source["updatedAt"],
        }]
        conn = FakeConnection(rowsets={
            "FROM cache.websim_release_registry": [self.release_row(release)],
            "gear_release_authority_items_variants": [
                (
                    "item-a",
                    requested_key,
                    item_record,
                    variant_record(snapshot["variants"][0]),
                    source_records,
                ),
                (
                    "item-a",
                    requested_key,
                    item_record,
                    variant_record(alias),
                    source_records,
                ),
            ],
            "gear_release_authority_options": [],
        })

        database_context = GearReleaseStore(
            lambda: conn
        ).load_candidate_authority_context(intent, runtime, release["releaseId"])

        self.assertEqual(database_context["missingFields"], [])
        self.assertEqual(
            database_context["variantsByKey"][requested_key]["simcOptions"]["bonus_id"],
            "123",
        )

    def test_candidate_community_release_rejects_missing_or_mixed_binding(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        gear = self.gear_release()
        rows = self.community_rows()
        community = self.community_release(gear["releaseId"], rows)

        missing = FakeConnection(rowsets={"FROM cache.websim_release_registry": []})
        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: missing).load_community_release(
                gear["releaseId"],
                community["releaseId"],
            )
        self.assertNotIn("websim_community_release_templates", "\n".join(missing.cursor_instance.statements))

        other_gear = self.gear_release({
            **self.snapshot(),
            "items": [{**self.snapshot()["items"][0], "name": "Other"}],
        })
        mixed = FakeConnection(rowsets={
            "FROM cache.websim_release_registry": {
                (other_gear["releaseId"],): [self.release_row(other_gear)],
                (community["releaseId"],): [self.release_row(community)],
            }
        })
        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: mixed).load_community_release(
                other_gear["releaseId"],
                community["releaseId"],
            )
        self.assertNotIn("websim_community_release_templates", "\n".join(mixed.cursor_instance.statements))

    def test_candidate_community_release_checks_complete_content_hash(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        gear = self.gear_release()
        rows = self.community_rows()
        community = self.community_release(gear["releaseId"], rows)
        registry = {
            (gear["releaseId"],): [self.release_row(gear)],
            (community["releaseId"],): [self.release_row(community)],
        }
        conn = FakeConnection(rowsets={
            "FROM cache.websim_release_registry": registry,
            "FROM cache.websim_community_release_templates": [self.community_db_row(rows[0])],
        })

        result = GearReleaseStore(lambda: conn).load_community_release(
            gear["releaseId"], community["releaseId"]
        )

        self.assertEqual(result["communityRelease"]["releaseId"], community["releaseId"])
        self.assertEqual([row["templateId"] for row in result["winners"]], ["template-a"])
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("WHERE release_id = %s", sql)
        self.assertNotIn("FROM cache.websim_community_gear_templates", sql)

        tampered = list(self.community_db_row(rows[0]))
        tampered[13] = "sha256:tampered"
        bad = FakeConnection(rowsets={
            "FROM cache.websim_release_registry": registry,
            "FROM cache.websim_community_release_templates": [tuple(tampered)],
        })
        with self.assertRaises(GearReleaseIntegrityError):
            GearReleaseStore(lambda: bad).load_community_release(
                gear["releaseId"], community["releaseId"]
            )


if __name__ == "__main__":
    unittest.main()
