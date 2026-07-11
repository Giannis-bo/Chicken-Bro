import copy
import unittest

from server import gear_release


class FakeCursor:
    def __init__(self, rowsets=None, rowcounts=None):
        self.rowsets = rowsets or {}
        self.rowcounts = rowcounts or {}
        self.current_rows = []
        self.statements = []
        self.params = []
        self.executemany_calls = []
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
        rows = list(self.current_rows)
        self.current_rows = []
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
            "capabilityRevision": "gear-capability-v1",
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

    def gear_release(self, snapshot=None):
        from server import gear_release_store

        snapshot = snapshot or self.snapshot()
        summary = gear_release_store.gear_snapshot_summary(snapshot)
        return gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=summary,
            dependency_revisions=self.dependencies(),
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
        self.assertTrue(conn.committed)

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
        runtime["dependencyRevisions"]["capabilityRevision"] = "gear-capability-v1"

        context = build_candidate_authority_context(snapshot, intent, runtime, release)

        self.assertEqual(context["manifest"]["gearCatalogReleaseId"], release["releaseId"])
        self.assertEqual(context["manifest"]["gearCatalogRevision"], release["releaseId"])
        self.assertEqual(context["manifest"]["manifestType"], "candidate")
        self.assertFalse(context["manifest"]["formalActiveManifest"])

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
        runtime["dependencyRevisions"]["capabilityRevision"] = "gear-capability-v1"

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
        self.assertEqual(first["dependencyVector"]["capabilityRevision"], "gear-capability-v1")
        self.assertIn("item-a", first["itemsById"])
        self.assertIn("variant-a", first["variantsByKey"])
        self.assertEqual(first["missingFields"], [])

    def test_snapshot_staging_community_templates_is_read_only_and_bounded(self):
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
        self.assertIn("candidate_rank <= 10", sql)
        self.assertIn("LIMIT 400", sql)
        self.assertEqual(conn.cursor_instance.params[-1][0], ["mage"])
        self.assertEqual(conn.cursor_instance.params[-1][1], ["arcane"])
        self.assertEqual(rows[0]["templateId"], "template-a")
        self.assertEqual(rows[0]["gearItems"][0]["variantKey"], "variant-a")
        self.assertEqual(rows[0]["payload"]["profileHash"], "profile:a")

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

    def test_active_pointer_read_returns_empty_without_legacy_fallback(self):
        from server.gear_release_store import GearReleaseStore

        conn = FakeConnection(rowsets={"FROM cache.websim_active_manifest_pointer": []})
        pointer = GearReleaseStore(lambda: conn).get_active_pointer()
        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(pointer, {})
        self.assertIn("FROM cache.websim_active_manifest_pointer", sql)
        self.assertNotIn("websim_season_state", sql)
        self.assertNotIn("websim_sync_state", sql)

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
        runtime["dependencyRevisions"]["capabilityRevision"] = "gear-capability-v1"
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
            "status": "verified",
            "sourceStatus": "unknown",
            "payload": {"status": "verified"},
            "updatedAt": "2026-07-11T05:00:00+00:00",
        }]
        conn = FakeConnection(rowsets={
            "FROM cache.websim_release_registry": [self.release_row(release)],
            "gear_release_authority_items_variants": [
                ("item-a", "variant-a", item_record, variant_record, source_records)
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
        self.assertNotIn("FROM cache.websim_items", sql)
        self.assertNotIn("FROM cache.websim_gear_variants", sql)
        self.assertEqual(context["manifest"]["gearCatalogReleaseId"], release["releaseId"])
        self.assertEqual(context["manifest"]["manifestType"], "candidate_shadow")
        self.assertFalse(context["manifest"]["formalActiveManifest"])
        self.assertEqual(context["missingFields"], [])

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
