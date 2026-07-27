import copy
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
        self.fetchmany_calls = []
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
                elif callable(rows):
                    self.current_rows = list(rows(tuple(params or ())))
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

    def fetchmany(self, size=None):
        self.fetchmany_calls.append(size)
        limit = int(size or 1)
        rows = self.current_rows[:limit]
        self.current_rows = self.current_rows[limit:]
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


class NamedCursorConnection(FakeConnection):
    """Connection double that records server-side cursor requests."""

    def __init__(self, rowsets=None, rowcounts=None):
        super().__init__(rowsets=rowsets, rowcounts=rowcounts)
        self.cursor_names = []

    def cursor(self, name=None):
        self.cursor_names.append(name)
        return self.cursor_instance


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

    def staging_rowsets(self, snapshot):
        return {
            "FROM cache.websim_items": [(
                row["itemId"], row["name"], row["slot"],
                row["itemLevel"], copy.deepcopy(row["payload"]),
                row["sourceStatus"], row["updatedAt"],
            ) for row in snapshot["items"]],
            "FROM cache.websim_gear_sources": [(
                row["sourceId"], row["itemId"], row["sourceType"],
                row["sourceKey"], row["sourceLabel"], row["instanceId"],
                row["encounterId"], row["difficultyKey"],
                row["seasonRevision"], copy.deepcopy(row["payload"]),
                row["updatedAt"],
            ) for row in snapshot["sources"]],
            "FROM cache.websim_gear_variants": [(
                row["variantId"], row["itemId"], row["variantKey"],
                row["slot"], row["label"], row["sourceType"],
                row["difficultyKey"], row["itemLevel"],
                copy.deepcopy(row["simcOptions"]), row["status"],
                copy.deepcopy(row["blockers"]),
                copy.deepcopy(row["payload"]), row["updatedAt"],
            ) for row in snapshot["variants"]],
            "FROM cache.websim_gear_mod_options": [(
                row["optionId"], row["variantId"], row["optionKey"],
                row["optionType"], row["name"],
                copy.deepcopy(row["applicableSlots"]),
                copy.deepcopy(row["simcOptions"]), row["status"],
                row["isVisible"], copy.deepcopy(row["payload"]),
                row["updatedAt"],
            ) for row in snapshot["options"]],
        }

    def canonical_staging_snapshot(self):
        snapshot = self.snapshot()
        snapshot["items"][0]["payload"]["_metadata"] = {
            "gameAsset": {
                "source": "blizzard",
                "status": "verified",
                "sourceIdentity": "battle-net:item:item-a",
                "sourceRevision": "battle-net-item-test-r1",
            }
        }
        snapshot["items"][0]["payload"]["equipmentUniqueness"] = {
            "isUnique": False
        }
        return snapshot

    def trusted_socket_evidence(self, revision="simc-r1"):
        return {
            "schemaRevision": "simc-socket-bonus-evidence-v1",
            "status": "verified",
            "sourceType": "simc_bonus_probe",
            "sourceIdentity": "simulationcraft:show_bonus_ids",
            "sourceRevision": revision,
            "sourceScope": "exact_variant",
            "minimums": {"9300": 1},
        }

    def trusted_gear_store(self, connection):
        from server.gear_release_store import GearReleaseStore

        store = GearReleaseStore(lambda: connection)
        store._configured_simc_probe_evidence = (
            self.trusted_socket_evidence
        )
        return store

    def complete_evidence_rowsets(
        self,
        artifact_rows,
        observation_rows,
        gap_rows,
    ):
        artifacts = {row[0]: row for row in artifact_rows}
        return {
            "gear_release_complete_evidence_universe": [
                tuple(observation) + tuple(
                    artifacts[observation[1]]
                )
                for observation in observation_rows
                if observation[1] in artifacts
            ],
            "gear_release_active_gap_universe": gap_rows,
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

    def canonical_seal_fixture(self):
        from server import (
            gear_fact_compiler,
            gear_fact_shadow,
            gear_release_tool,
            gear_release_store,
        )
        snapshot = self.canonical_staging_snapshot()
        raw_snapshot = copy.deepcopy(snapshot)
        socket_bonus_evidence = self.trusted_socket_evidence()
        normalized_bonus_minimums = {
            "9300": {
                "minimumTotal": 1,
                "sourceRevision": "simc-r1",
            }
        }
        compiled = gear_release_tool._compile_release_gear_evidence(
            raw_snapshot,
            season_revision="season-17",
            source_revision="canonical-store-test",
            captured_at="2026-07-11T05:00:00+00:00",
            socket_bonus_minimums=normalized_bonus_minimums,
            socket_bonus_evidence=socket_bonus_evidence,
        )
        facts = compiled["facts"]
        snapshot = copy.deepcopy(raw_snapshot)
        rows_by_subject = {
            f"item:{snapshot['items'][0]['itemId']}": (
                snapshot["items"][0]
            ),
            (
                f"item:{snapshot['variants'][0]['itemId']}"
                f"/variant:{snapshot['variants'][0]['variantKey']}"
            ): snapshot["variants"][0],
            f"option:{snapshot['options'][0]['optionId']}": (
                snapshot["options"][0]
            ),
            f"option:{snapshot['options'][0]['optionKey']}": (
                snapshot["options"][0]
            ),
        }
        for row in {
            id(row): row for row in rows_by_subject.values()
        }.values():
            payload = copy.deepcopy(row.get("payload") or {})
            payload["canonicalFacts"] = []
            row["payload"] = payload
        for fact in facts:
            projection = {
                key: copy.deepcopy(fact[key])
                for key in (
                    "schemaRevision",
                    "factKey",
                    "subjectKey",
                    "factType",
                    "value",
                    "status",
                    "factValueHash",
                    "provenanceHash",
                    "compilerRuleRevision",
                    "observationRefs",
                )
            }
            projection.update({
                "observationRefCount": len(
                    fact["observationRefs"]
                ),
                "referencesTruncated": False,
            })
            rows_by_subject[fact["subjectKey"]]["payload"][
                "canonicalFacts"
            ].append(projection)

        fact_digest_rows = sorted(
            [{
                "factKey": fact["factKey"],
                "status": fact["status"],
                "factValueHash": fact["factValueHash"],
                "provenanceHash": fact["provenanceHash"],
            } for fact in facts],
            key=lambda fact: (
                fact["factKey"],
                fact["factValueHash"],
                fact["provenanceHash"],
            ),
        )
        legacy_snapshot = gear_release_tool._legacy_shadow_snapshot(
            raw_snapshot,
            season_revision="season-17",
            capability_revision=self.dependencies()[
                "capabilityRevision"
            ],
            socket_bonus_evidence=socket_bonus_evidence,
        )
        summary = gear_release_store.gear_snapshot_summary(snapshot)
        release = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=summary,
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={
                "sourceRevision": "canonical-store-test",
                "stagingSnapshotHash": (
                    gear_release_store.gear_snapshot_summary(
                        raw_snapshot
                    )["snapshotHash"]
                ),
                "sourceEvidence": {
                    "socketBonusEvidence": socket_bonus_evidence,
                    "socketProbeDigest": (
                        gear_release_tool._socket_probe_digest(
                            socket_bonus_evidence
                        )
                    ),
                    "compilerPolicyDigest": gear_release_store._hash(
                        gear_fact_compiler.FACT_POLICIES
                    ),
                    "canonicalFactDigest": gear_release_store._hash(
                        fact_digest_rows
                    ),
                },
            },
        )
        fact_identity_digest = gear_release_store._hash(sorted(
            (
                fact["factKey"],
                fact["factValueHash"],
                fact["provenanceHash"],
            )
            for fact in facts
        ))
        gap_rows = []
        for gap in gear_fact_compiler.evidence_gaps_from_facts(
            facts
        ):
            identity = {
                "factKey": gap["factKey"],
                "problemCode": gap["problemCode"],
                "missingRequirement": gap["missingRequirement"],
            }
            gap_rows.append((
                "gear-gap:" + gear_release_store._hash(identity),
                gap["factKey"],
                gap["problemCode"],
                copy.deepcopy(gap["missingRequirement"]),
                "pending",
            ))
        gap_ids = sorted(row[0] for row in gap_rows)
        artifact_ids = sorted(
            artifact["artifactId"]
            for artifact in compiled["artifacts"]
        )
        observation_ids = sorted(
            observation["observationId"]
            for observation in compiled["observations"]
        )
        fact_identities = sorted(
            (
                fact["factKey"],
                fact["factValueHash"],
                fact["provenanceHash"],
            )
            for fact in facts
        )
        gate = {
            "status": "validated",
            **summary,
            "evidenceGapCount": len(gap_ids),
            "factShadow": gear_fact_shadow.compare_legacy_and_canonical(
                legacy_snapshot,
                facts,
                expected_fact_types_by_subject={
                    fact["subjectKey"]: [fact["factType"]]
                    for fact in facts
                },
            ),
            "evidenceCompilation": {
                "artifacts": {"count": len(artifact_ids), "identities": artifact_ids, "identityDigest": gear_release_store._hash(artifact_ids)},
                "observations": {"count": len(observation_ids), "identities": observation_ids, "identityDigest": gear_release_store._hash(observation_ids)},
                "facts": {"count": len(facts), "identities": fact_identities, "identityDigest": fact_identity_digest},
                "gaps": {"count": len(gap_ids), "identities": gap_ids, "identityDigest": gear_release_store._hash(gap_ids)},
            },
            "evidencePersistence": {
                "artifacts": {"persisted": len(artifact_ids), "identities": artifact_ids, "identityDigest": gear_release_store._hash(artifact_ids)},
                "observations": {"persisted": len(observation_ids), "identities": observation_ids, "identityDigest": gear_release_store._hash(observation_ids)},
                "facts": {"persisted": len(facts), "identities": fact_identities, "identityDigest": fact_identity_digest},
                "gaps": {
                    "requested": len(gap_ids),
                    "inserted": len(gap_ids),
                    "reused": 0,
                    "identities": gap_ids,
                    "identityDigest": gear_release_store._hash(gap_ids),
                },
            },
        }
        persisted_fact_rows = [(
            fact["factKey"],
            fact["schemaRevision"],
            fact["subjectKey"],
            fact["factType"],
            fact["value"],
            fact["status"],
            fact["observationRefs"],
            fact["factValueHash"],
            fact["provenanceHash"],
            fact["compilerRuleRevision"],
        ) for fact in facts]
        return (
            snapshot,
            release,
            gate,
            persisted_fact_rows,
            [(
                artifact["artifactId"],
                artifact["schemaRevision"],
                artifact["sourceType"],
                artifact["sourceIdentity"],
                artifact["sourceRevision"],
                artifact["seasonRevision"],
                artifact["capturedAt"],
                artifact["payloadHash"],
                artifact["payload"],
            ) for artifact in compiled["artifacts"]],
            [(
                observation["observationId"],
                observation["artifactId"],
                observation["schemaRevision"],
                observation["subjectKey"],
                observation["factType"],
                observation["observedValue"],
                observation["parserRevision"],
                observation["sourceScope"],
                observation["status"],
            ) for observation in compiled["observations"]],
            gap_rows,
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
        self.assertTrue(conn.committed)

    def test_snapshot_staging_gear_consumes_cursor_in_bounded_batches_without_payload_clone(self):
        from server.gear_release_store import GearReleaseStore

        variant_payload = {
            "nested": {"values": ["keep-the-driver-object"] * 16}
        }
        conn = FakeConnection(rowsets={
            "FROM cache.websim_items": [
                ("item-a", "Item A", "head", 289, {"x": 1}, "verified", "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_sources": [
                ("source-a", "item-a", "observed_profile", "profile:a", "Observed", "", "", "mythic", "season-17", {"status": "verified"}, "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_variants": [
                (f"variant-{index}", "item-a", f"variant-{index}", "head", "289", "observed_profile", "mythic", 289, {"ilevel": str(289 + index)}, "verified", [], variant_payload if index == 0 else {"index": index}, "2026-07-11T05:00:00+00:00")
                for index in range(5)
            ],
            "FROM cache.websim_gear_mod_options": [
                ("option-a-id", "variant-0", "gem-a", "gem", "Gem A", ["head"], {"gem_id": "1"}, "verified", True, {"itemStats": []}, "2026-07-11T05:00:00+00:00")
            ],
        })

        snapshot = GearReleaseStore(lambda: conn).snapshot_staging_gear()

        self.assertEqual(conn.cursor_instance.fetchall_calls, 0)
        self.assertGreaterEqual(len(conn.cursor_instance.fetchmany_calls), 8)
        self.assertIs(snapshot["variants"][0]["payload"], variant_payload)

    def test_snapshot_staging_gear_compacts_duplicate_observed_semantic_variants(self):
        from server.gear_release_store import GearReleaseStore

        conn = FakeConnection(rowsets={
            "FROM cache.websim_items": [
                ("item-a", "Item A", "head", 289, {}, "verified", "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_sources": [],
            "FROM cache.websim_gear_variants": [
                ("observed-old", "item-a", "observed-old", "head", "289", "observed_profile", "observed", 289, {"ilevel": "289"}, "verified", [], {"resolvedStats": {"intellect": 100}, "canonicalEvidence": {"sourceType": "season_rule", "sourceIdentity": "season-rule:item-a", "sourceRevision": "season-17", "sourceScope": "exact_variant", "status": "verified", "claims": ["socket_count"]}}, "2026-07-11T05:00:00+00:00"),
                ("observed-new", "item-a", "observed-new", "head", "289", "observed_profile", "observed", 289, {"ilevel": "289"}, "verified", [], {"resolvedStats": {"intellect": 100}, "canonicalEvidence": {"sourceType": "season_rule", "sourceIdentity": "season-rule:item-a", "sourceRevision": "season-17", "sourceScope": "exact_variant", "status": "verified", "claims": ["socket_count"]}}, "2026-07-12T05:00:00+00:00"),
                ("observed-new-evidence", "item-a", "observed-new-evidence", "head", "289", "observed_profile", "observed", 289, {"ilevel": "289"}, "verified", [], {"resolvedStats": {"intellect": 100}, "canonicalEvidence": {"sourceType": "season_rule", "sourceIdentity": "season-rule:item-a", "sourceRevision": "season-18", "sourceScope": "exact_variant", "status": "verified", "claims": ["socket_count"]}}, "2026-07-13T05:00:00+00:00"),
                ("raid-a", "item-a", "raid-a", "head", "289", "raid", "mythic", 289, {"ilevel": "289"}, "verified", [], {"resolvedStats": {"intellect": 100}}, "2026-07-11T05:00:00+00:00"),
            ],
            "FROM cache.websim_gear_mod_options": [],
        })

        snapshot = GearReleaseStore(lambda: conn).snapshot_staging_gear()

        self.assertEqual(
            [row["variantId"] for row in snapshot["variants"]],
            ["observed-new", "observed-new-evidence", "raid-a"],
        )

    def test_snapshot_staging_gear_keeps_an_option_owner_during_observed_compaction(self):
        from server.gear_release_tool import validate_gear_snapshot
        from server.gear_release_store import GearReleaseStore

        conn = FakeConnection(rowsets={
            "FROM cache.websim_items": [
                ("item-a", "Item A", "head", 289, {}, "verified", "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_sources": [
                ("source-a", "item-a", "observed_profile", "profile:a", "Observed", "", "", "observed", "season-17", {"status": "verified"}, "2026-07-11T05:00:00+00:00")
            ],
            "FROM cache.websim_gear_variants": [
                ("observed-old", "item-a", "observed-old", "head", "289", "observed_profile", "observed", 289, {"ilevel": "289"}, "verified", [], {"resolvedStats": {"intellect": 100}}, "2026-07-11T05:00:00+00:00"),
                ("observed-new", "item-a", "observed-new", "head", "289", "observed_profile", "observed", 289, {"ilevel": "289"}, "verified", [], {"resolvedStats": {"intellect": 100}}, "2026-07-12T05:00:00+00:00"),
            ],
            "FROM cache.websim_gear_mod_options": [
                ("option-a", "observed-old", "gem-a", "gem", "Gem A", ["head"], {"gem_id": "1"}, "verified", True, {}, "2026-07-11T05:00:00+00:00")
            ],
        })

        snapshot = GearReleaseStore(lambda: conn).snapshot_staging_gear()

        self.assertEqual(
            [row["variantId"] for row in snapshot["variants"]],
            ["observed-new", "observed-old"],
        )
        self.assertEqual(validate_gear_snapshot(snapshot), [])

    def test_snapshot_staging_gear_uses_a_server_side_cursor_when_supported(self):
        from server.gear_release_store import GearReleaseStore

        conn = NamedCursorConnection(rowsets={
            "FROM cache.websim_items": [],
            "FROM cache.websim_gear_sources": [],
            "FROM cache.websim_gear_variants": [],
            "FROM cache.websim_gear_mod_options": [],
        })

        GearReleaseStore(lambda: conn).snapshot_staging_gear()

        self.assertIn("gear_release_staging_snapshot", conn.cursor_names)

    def test_evidence_bundle_keeps_the_parent_transaction_connection_open(self):
        from server import gear_evidence_store
        from server.gear_release_store import GearReleaseStore

        class ContextClosingConnection(FakeConnection):
            def __init__(self):
                super().__init__()
                self.context_entries = 0

            def __enter__(self):
                if self.closed:
                    raise RuntimeError("borrowed connection was closed")
                self.context_entries += 1
                return self

            def __exit__(self, exc_type, exc, tb):
                self.close()
                return False

        class BorrowingEvidenceStore:
            def __init__(self, connection_factory):
                self.connection_factory = connection_factory

            def _persist(self, record):
                with self.connection_factory() as connection:
                    if connection.closed:
                        raise RuntimeError("borrowed connection was closed")
                    connection.cursor()
                return record

            persist_artifact = _persist
            persist_observation = _persist
            persist_fact = _persist

        conn = ContextClosingConnection()
        store = GearReleaseStore(lambda: conn)
        with patch.object(
            gear_evidence_store,
            "GearEvidenceStore",
            BorrowingEvidenceStore,
        ):
            result = store.persist_gear_evidence_bundle(
                artifacts=[{"artifactId": "artifact-a"}],
                observations=[{"observationId": "observation-a"}],
                facts=[{
                    "factKey": "fact-a",
                    "factValueHash": "value-a",
                    "provenanceHash": "provenance-a",
                }],
                gaps=[],
                now="2026-07-27T00:00:00+00:00",
            )

        self.assertEqual(result["facts"]["persisted"], 1)
        self.assertEqual(conn.context_entries, 0)
        self.assertTrue(conn.committed)
        self.assertTrue(conn.closed)

    def test_gear_snapshot_summary_sorts_serialized_rows_without_deep_copying_catalog(self):
        from server import gear_release_store

        snapshot = self.snapshot()
        expected = gear_release_store.gear_snapshot_summary(snapshot)

        with patch(
            "server.gear_release_store._canonical",
            side_effect=AssertionError("summary must not clone every catalog row"),
        ):
            actual = gear_release_store.gear_snapshot_summary(snapshot)

        self.assertEqual(actual, expected)

    def test_gear_snapshot_summary_uses_bounded_row_sorting(self):
        from server import gear_release_store

        snapshot = self.snapshot()
        expected = gear_release_store.gear_snapshot_summary(snapshot)

        with patch(
            "server.gear_release_store._canonical_rows",
            side_effect=AssertionError("summary must not retain every serialized row key"),
        ):
            actual = gear_release_store.gear_snapshot_summary(snapshot)

        self.assertEqual(actual, expected)

    def test_gear_snapshot_summary_preserves_the_v1_canonical_hash_bytes(self):
        from server import gear_release_store

        snapshot = self.snapshot()
        snapshot["items"].append(copy.deepcopy(snapshot["items"][0]))
        snapshot["items"][1]["itemId"] = "item-z"
        snapshot["sources"].append(copy.deepcopy(snapshot["sources"][0]))
        snapshot["sources"][1]["sourceId"] = "source-z"
        snapshot["variants"].append(copy.deepcopy(snapshot["variants"][0]))
        snapshot["variants"][1]["variantId"] = "variant-z-id"
        snapshot["variants"][1]["variantKey"] = "variant-z"
        snapshot["options"].append({
            "optionId": "option-z",
            "optionKey": "option-z",
            "optionType": "gem",
            "payload": {"effect": {"critical_strike": 1}},
        })
        expected_canonical = {
            key: gear_release_store._canonical_rows(snapshot[key])
            for key in ("items", "sources", "variants", "options")
        }

        summary = gear_release_store.gear_snapshot_summary(snapshot)

        self.assertEqual(
            summary["snapshotHash"],
            gear_release_store._hash(expected_canonical),
        )

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

    def test_unenhanced_candidate_resolve_exposes_all_released_allowed_options(self):
        from server import gear_resolver
        from server.gear_release_store import build_candidate_authority_context
        from server.websim_payload import (
            gear_resolver_runtime_authority,
            public_gear_capability_facts,
        )

        def fact(subject, fact_type, value):
            return {
                "schemaRevision": "gear-canonical-fact-v1",
                "factKey": f"gear-fact:test:{subject}:{fact_type}",
                "subjectKey": subject,
                "factType": fact_type,
                "value": copy.deepcopy(value),
                "status": "verified",
                "observationRefs": [],
                "observationRefCount": 0,
                "referencesTruncated": False,
                "compilerRuleRevision": f"test-{fact_type}-v1",
                "factValueHash": f"sha256:{fact_type}",
                "provenanceHash": f"sha256:{fact_type}-provenance",
            }

        snapshot = self.snapshot()
        item_subject = "item:item-a"
        variant_subject = "item:item-a/variant:variant-a"
        option_subject = "option:gem-a"
        snapshot["items"][0]["payload"]["canonicalFacts"] = [
            fact(item_subject, "item_identity", {
                "itemId": "item-a",
                "inventoryType": "head",
            }),
            fact(item_subject, "slot_compatibility", ["head"]),
            fact(item_subject, "socket_count", 1),
            fact(item_subject, "enchant_capability", False),
            fact(item_subject, "embellishment_capability", False),
            fact(item_subject, "allowed_enhancement_options", ["gem-a"]),
            fact(item_subject, "item_set_membership", False),
            fact(item_subject, "equipment_uniqueness", {"isUnique": False}),
        ]
        snapshot["variants"][0]["simcOptions"] = {
            "bonus_id": "raw-must-not-author",
            "ilevel": "999",
        }
        snapshot["variants"][0]["payload"]["canonicalFacts"] = [
            fact(variant_subject, "item_identity", {
                "itemId": "item-a",
                "variantKey": "variant-a",
            }),
            fact(variant_subject, "slot_compatibility", ["head"]),
            fact(variant_subject, "variant_track", {
                "itemId": "item-a",
                "variantKey": "variant-a",
                "track": "mythic",
                "itemLevel": 289,
            }),
            fact(variant_subject, "static_stats", {"intellect": 100}),
            fact(variant_subject, "socket_count", 1),
            fact(variant_subject, "enchant_capability", False),
            fact(variant_subject, "embellishment_capability", False),
            fact(
                variant_subject,
                "allowed_enhancement_options",
                ["gem-a"],
            ),
            fact(variant_subject, "item_set_membership", False),
            fact(variant_subject, "executable_item_options", {
                "itemId": "item-a",
                "variantKey": "variant-a",
                "options": {"bonus_id": "100/200", "ilevel": "289"},
            }),
        ]
        snapshot["options"][0]["payload"]["canonicalFacts"] = [
            fact(option_subject, "enhancement_option", {
                "optionId": "gem-a",
                "optionType": "gem",
                "effect": {"gem_id": "1"},
                "applicableScopes": ["head"],
                "statDeltas": {"haste": 10},
            })
        ]
        dependencies = self.dependencies()
        dependencies["capabilityRevision"] = (
            gear_socket_authority.CAPABILITY_REVISION
        )
        release = self.gear_release(snapshot, dependencies=dependencies)
        intent = {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": release["releaseId"],
            },
            "eligibilityContext": {
                "classKey": "mage",
                "specKey": "arcane",
                "level": 90,
            },
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
        runtime = gear_resolver_runtime_authority(
            "mage",
            "arcane",
            simc_runtime_revision="simc-r1",
        )
        runtime["dependencyRevisions"]["capabilityRevision"] = (
            gear_socket_authority.CAPABILITY_REVISION
        )

        context = build_candidate_authority_context(
            snapshot,
            intent,
            runtime,
            release,
        )
        resolved = gear_resolver.resolve(intent, context)
        browse = public_gear_capability_facts({
            "itemId": "item-a",
            "variantKey": "variant-a",
            "payload": snapshot["variants"][0]["payload"],
            "socketOptions": [{"id": "gem-a"}],
            "enchantOptions": [],
            "embellishmentOptions": [],
        })

        self.assertIn("gem-a", context["optionsById"])
        self.assertEqual(
            resolved["resolvedSlots"]["head"]["capabilityFacts"],
            browse,
        )
        self.assertEqual(
            resolved["resolvedSlots"]["head"]["capabilityFacts"]["socket"][
                "options"
            ],
            ["gem-a"],
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

        (
            snapshot,
            release,
            gate,
            fact_rows,
            artifact_rows,
            observation_rows,
            gap_rows,
        ) = self.canonical_seal_fixture()
        conn = FakeConnection(rowsets={
            **self.staging_rowsets(self.canonical_staging_snapshot()),
            **self.complete_evidence_rowsets(
                artifact_rows, observation_rows, gap_rows
            ),
            "FROM cache.websim_release_registry": [],
            "JOIN cache.websim_gear_canonical_facts": fact_rows,
            "FROM cache.websim_gear_evidence_artifacts": artifact_rows,
            "FROM cache.websim_gear_evidence_observations": observation_rows,
            "FROM ops.websim_gear_evidence_gaps": gap_rows,
        })
        store = self.trusted_gear_store(conn)

        result = store.seal_gear_release(
            release,
            snapshot,
            event={"mode": "legacy-import-r0"},
            gate_result=gate,
        )

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
        gap_query_index = next(
            index
            for index, statement in enumerate(
                conn.cursor_instance.statements
            )
            if "gear_release_active_gap_universe" in statement
        )
        queried_fact_keys = set(
            conn.cursor_instance.params[gap_query_index][0]
        )
        self.assertEqual(
            queried_fact_keys,
            {row[0] for row in fact_rows},
        )
        self.assertTrue(conn.committed)
        self.assertFalse(conn.rolled_back)

    def test_seal_gear_release_replays_complete_evidence_in_one_batch(self):
        from server import gear_fact_compiler

        (
            snapshot,
            release,
            gate,
            fact_rows,
            artifact_rows,
            observation_rows,
            gap_rows,
        ) = self.canonical_seal_fixture()
        conn = FakeConnection(rowsets={
            **self.staging_rowsets(self.canonical_staging_snapshot()),
            **self.complete_evidence_rowsets(
                artifact_rows, observation_rows, gap_rows
            ),
            "FROM cache.websim_release_registry": [],
            "JOIN cache.websim_gear_canonical_facts": fact_rows,
            "FROM cache.websim_gear_evidence_artifacts": artifact_rows,
            "FROM cache.websim_gear_evidence_observations": observation_rows,
            "FROM ops.websim_gear_evidence_gaps": gap_rows,
        })

        with patch(
            "server.gear_fact_compiler.compile_facts_by_subject",
            wraps=gear_fact_compiler.compile_facts_by_subject,
        ) as compile_batch:
            self.trusted_gear_store(conn).seal_gear_release(
                release,
                snapshot,
                gate_result=gate,
            )

        # One batch reconstructs the staging universe; a second batch verifies
        # every persisted fact. Per-fact replays would make full catalog seals
        # grow quadratically with the evidence universe.
        self.assertEqual(compile_batch.call_count, 2)

    def test_seal_gear_release_replays_compact_streaming_receipt_in_batches(self):
        from server import gear_release_tool

        raw_snapshot = self.canonical_staging_snapshot()
        raw_snapshot["items"][0]["payload"]["baseCapabilities"] = {
            "socketCount": 1,
            "canEnchant": True,
            "canEmbellish": False,
        }
        raw_snapshot["variants"][0]["payload"]["capabilityOverrides"] = {
            "socketCount": 1,
            "canEnchant": True,
            "canEmbellish": False,
        }
        raw_snapshot["variants"][0]["simcOptions"]["bonus_id"] = "9300"
        raw_snapshot["variants"][0]["payload"]["canonicalEvidence"] = {
            "sourceType": "season_rule",
            "sourceIdentity": "season-rule:variant-a",
            "sourceRevision": "season-17",
            "sourceScope": "exact_variant",
            "status": "verified",
            "claims": [
                "slot_compatibility",
                "socket_count",
                "enchant_capability",
                "embellishment_capability",
                "allowed_enhancement_options",
            ],
        }
        raw_snapshot["variants"][0]["payload"]["allowedEnhancementRules"] = [
            {
                "capabilityFactType": "socket_count",
                "optionIds": ["gem-a"],
                "slot": "head",
            }
        ]
        raw_snapshot["options"][0]["payload"] = {
            "evidenceSource": "simulationcraft",
            "optionEvidence": {
                "sourceType": "simc_item_probe",
                "sourceIdentity": "simc-option:gem-a",
                "sourceRevision": "simc-options-2026-07-11",
                "sourceScope": "option",
                "status": "verified",
            },
        }
        item_b = copy.deepcopy(raw_snapshot["items"][0])
        item_b.update({"itemId": "item-b", "name": "Item B"})
        item_b["payload"]["_metadata"]["gameAsset"].update({
            "sourceIdentity": "battle-net:item:item-b",
        })
        source_b = copy.deepcopy(raw_snapshot["sources"][0])
        source_b.update({
            "sourceId": "source-b",
            "itemId": "item-b",
            "sourceKey": "profile:b",
        })
        variant_b = copy.deepcopy(raw_snapshot["variants"][0])
        variant_b.update({
            "variantId": "variant-b-id",
            "itemId": "item-b",
            "variantKey": "variant-b",
        })
        raw_snapshot["items"].append(item_b)
        raw_snapshot["sources"].append(source_b)
        raw_snapshot["variants"].append(variant_b)
        # Force the preparation stream to have a different row order from the
        # compiler's Artifact-ID order.  Seal must replay the preparation
        # schedule, not substitute its own default batch boundary/order.
        item_evidence = gear_release_tool._compile_release_gear_evidence(
            raw_snapshot,
            season_revision="season-17",
            source_revision="canonical-store-test",
            captured_at="2026-07-27T06:00:00+00:00",
            socket_bonus_minimums={"9300": {"minimumTotal": 1, "sourceRevision": "simc-r1"}},
            socket_bonus_evidence=self.trusted_socket_evidence(),
            categories=("items",),
        )
        item_order = [
            row["payload"]["itemId"]
            for row in item_evidence["artifacts"]
            if row["sourceIdentity"].startswith("battle-net:item:")
        ]
        self.assertEqual(set(item_order), {"item-a", "item-b"})
        items_by_id = {row["itemId"]: row for row in raw_snapshot["items"]}
        raw_snapshot["items"] = [items_by_id[item_id] for item_id in reversed(item_order)]

        class BuilderStore:
            def __init__(self, snapshot):
                self.snapshot = snapshot
                self.bundles = []

            def snapshot_staging_gear(self):
                return copy.deepcopy(self.snapshot)

            def persist_gear_evidence_bundle(
                self,
                *,
                artifacts,
                observations,
                facts,
                gaps,
                now,
            ):
                self.bundles.append({
                    "artifacts": copy.deepcopy(artifacts),
                    "observations": copy.deepcopy(observations),
                    "facts": copy.deepcopy(facts),
                    "gaps": copy.deepcopy(gaps),
                })
                return {
                    "artifacts": {"persisted": len(artifacts)},
                    "observations": {"persisted": len(observations)},
                    "facts": {"persisted": len(facts)},
                    "gaps": {
                        "requested": len(gaps),
                        "inserted": len(gaps),
                        "reused": 0,
                    },
                }

        builder = BuilderStore(raw_snapshot)
        prepared = gear_release_tool.prepare_staging_gear_release(
            builder,
            season_revision="season-17",
            dependency_revisions=self.dependencies(),
            socket_bonus_minimums=self.trusted_socket_evidence(),
            source_revision="canonical-store-test",
            evidence_now="2026-07-27T06:00:00+00:00",
            evidence_batch_size=1,
        )
        self.assertEqual(prepared["gate"]["evidenceStream"]["batchSize"], 1)
        artifacts = {
            row["artifactId"]: row
            for bundle in builder.bundles
            for row in bundle["artifacts"]
        }
        observations = {
            row["observationId"]: row
            for bundle in builder.bundles
            for row in bundle["observations"]
        }
        facts = {
            (
                row["factKey"],
                row["factValueHash"],
                row["provenanceHash"],
            ): row
            for bundle in builder.bundles
            for row in bundle["facts"]
        }
        allowed_option_fact = next(
            row
            for row in facts.values()
            if row["subjectKey"] == "item:item-a/variant:variant-a"
            and row["factType"] == "allowed_enhancement_options"
        )
        self.assertEqual(allowed_option_fact["status"], "verified")
        self.assertEqual(allowed_option_fact["value"], ["gem-a"])
        gaps = {
            row["gapKey"]: row
            for bundle in builder.bundles
            for row in bundle["gaps"]
        }
        artifact_rows = {
            artifact_id: (
                row["artifactId"],
                row["schemaRevision"],
                row["sourceType"],
                row["sourceIdentity"],
                row["sourceRevision"],
                row["seasonRevision"],
                row["capturedAt"],
                row["payloadHash"],
                row["payload"],
            )
            for artifact_id, row in artifacts.items()
        }
        observation_rows = {
            observation_id: (
                row["observationId"],
                row["artifactId"],
                row["schemaRevision"],
                row["subjectKey"],
                row["factType"],
                row["observedValue"],
                row["parserRevision"],
                row["sourceScope"],
                row["status"],
            )
            for observation_id, row in observations.items()
        }

        def streamed_evidence_rows(params):
            observation_ids = set(params[0])
            return [
                observation_rows[observation_id] + artifact_rows[
                    observation_rows[observation_id][1]
                ]
                for observation_id in observation_ids
                if observation_id in observation_rows
            ]

        def streamed_gap_rows(params):
            return [
                (
                    gap["gapKey"],
                    gap["factKey"],
                    gap["problemCode"],
                    gap["missingRequirement"],
                    "pending",
                )
                for gap_key, gap in gaps.items()
                if gap_key in set(params[0])
            ]

        fact_rows = [
            (
                row["factKey"],
                row["schemaRevision"],
                row["subjectKey"],
                row["factType"],
                row["value"],
                row["status"],
                row["observationRefs"],
                row["factValueHash"],
                row["provenanceHash"],
                row["compilerRuleRevision"],
            )
            for row in facts.values()
        ]
        conn = FakeConnection(rowsets={
            **self.staging_rowsets(raw_snapshot),
            "FROM cache.websim_release_registry": [],
            "JOIN cache.websim_gear_canonical_facts": fact_rows,
            "gear_release_complete_evidence_stream_batch": streamed_evidence_rows,
            "gear_release_active_gap_stream_batch": streamed_gap_rows,
        })

        result = self.trusted_gear_store(conn).seal_gear_release(
            prepared["release"],
            prepared["snapshot"],
            gate_result=prepared["gate"],
        )

        self.assertEqual(result["status"], "inserted")
        self.assertTrue(conn.committed)

    def test_direct_gear_seal_rejects_each_missing_canonical_gate_binding(self):
        from server import gear_release_store
        from server.gear_release_store import (
            GearReleaseIntegrityError,
            GearReleaseStore,
        )

        (
            snapshot,
            release,
            gate,
            fact_rows,
            artifact_rows,
            observation_rows,
            gap_rows,
        ) = self.canonical_seal_fixture()

        def rebuilt(candidate_snapshot, candidate_source):
            return gear_release.build_release(
                release_kind="gear",
                season_revision="season-17",
                schema_revision="gear-release-v1",
                content=gear_release_store.gear_snapshot_summary(
                    candidate_snapshot
                ),
                dependency_revisions=self.dependencies(),
                release_status="validated",
                source=candidate_source,
            )

        cases = []
        cases.append(("missing gate", release, snapshot, {}))
        missing_receipt = copy.deepcopy(gate)
        missing_receipt.pop("evidencePersistence")
        cases.append(("missing receipt", release, snapshot, missing_receipt))
        missing_shadow = copy.deepcopy(gate)
        missing_shadow.pop("factShadow")
        cases.append(("missing shadow", release, snapshot, missing_shadow))
        blocked_shadow = copy.deepcopy(gate)
        blocked_shadow["factShadow"]["blockers"] = [{"code": "REGRESSION"}]
        cases.append(("blocked shadow", release, snapshot, blocked_shadow))
        fabricated_shadow = copy.deepcopy(gate)
        fabricated_shadow["factShadow"]["comparisons"][0][
            "legacyValue"
        ] = {"itemId": "different"}
        cases.append((
            "fabricated exact-parity shadow",
            release,
            snapshot,
            fabricated_shadow,
        ))
        fabricated_shadow_and_label = copy.deepcopy(gate)
        fabricated_shadow_and_label["factShadow"]["comparisons"][0].update({
            "legacyValue": {"itemId": "different"},
            "classification": "regression",
        })
        cases.append((
            "fabricated shadow input and label",
            release,
            snapshot,
            fabricated_shadow_and_label,
        ))

        for digest_field in (
            "compilerPolicyDigest",
            "canonicalFactDigest",
        ):
            source = copy.deepcopy(release["source"])
            source["sourceEvidence"].pop(digest_field)
            cases.append((
                f"missing {digest_field}",
                rebuilt(snapshot, source),
                snapshot,
                gate,
            ))
        forged_policy_source = copy.deepcopy(release["source"])
        forged_policy_source["sourceEvidence"][
            "compilerPolicyDigest"
        ] = gear_release_store._hash({"policy": "forged"})
        cases.append((
            "forged compiler policy digest",
            rebuilt(snapshot, forged_policy_source),
            snapshot,
            gate,
        ))

        empty_snapshot = copy.deepcopy(snapshot)
        empty_snapshot["items"][0]["payload"]["canonicalFacts"] = []
        cases.append((
            "empty canonical facts",
            rebuilt(empty_snapshot, release["source"]),
            empty_snapshot,
            gate,
        ))

        for label, candidate_release, candidate_snapshot, candidate_gate in cases:
            with self.subTest(label=label):
                conn = FakeConnection(rowsets={
                    **self.staging_rowsets(self.canonical_staging_snapshot()),
                    **self.complete_evidence_rowsets(
                        artifact_rows, observation_rows, gap_rows
                    ),
                    "FROM cache.websim_release_registry": [],
                    "JOIN cache.websim_gear_canonical_facts": fact_rows,
                    "FROM cache.websim_gear_evidence_artifacts": artifact_rows,
                    "FROM cache.websim_gear_evidence_observations": observation_rows,
                    "FROM ops.websim_gear_evidence_gaps": gap_rows,
                })
                with self.assertRaises(GearReleaseIntegrityError):
                    self.trusted_gear_store(conn).seal_gear_release(
                        candidate_release,
                        candidate_snapshot,
                        gate_result=candidate_gate,
                    )
                self.assertFalse(any(
                    "INSERT INTO cache.websim_release_registry" in statement
                    for statement in conn.cursor_instance.statements
                ))

        omitted_snapshot = copy.deepcopy(snapshot)
        omitted_snapshot["items"][0]["payload"][
            "canonicalFacts"
        ] = [
            fact
            for fact in omitted_snapshot["items"][0]["payload"][
                "canonicalFacts"
            ]
            if fact["factType"] != "socket_count"
        ]
        omitted_gate = copy.deepcopy(gate)
        omitted_summary = gear_release_store.gear_snapshot_summary(
            omitted_snapshot
        )
        omitted_gate.update(omitted_summary)
        omitted_release = rebuilt(
            omitted_snapshot,
            release["source"],
        )
        omitted_conn = FakeConnection(rowsets={
            **self.staging_rowsets(self.canonical_staging_snapshot()),
        })
        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "Fact universe is incomplete",
        ):
            self.trusted_gear_store(omitted_conn).seal_gear_release(
                omitted_release,
                omitted_snapshot,
                gate_result=omitted_gate,
            )

        for label, missing_marker, error_pattern in (
            (
                "artifact",
                "gear_release_complete_evidence_universe",
                "does not match staging compilation",
            ),
            (
                "observation",
                "gear_release_complete_evidence_universe",
                "does not match staging compilation",
            ),
            (
                "gap",
                "gear_release_active_gap_universe",
                "Gap semantics",
            ),
        ):
            with self.subTest(missing_persistence=label):
                rowsets = {
                    **self.staging_rowsets(self.canonical_staging_snapshot()),
                    **self.complete_evidence_rowsets(
                        artifact_rows, observation_rows, gap_rows
                    ),
                    "FROM cache.websim_release_registry": [],
                    "JOIN cache.websim_gear_canonical_facts": fact_rows,
                    "FROM cache.websim_gear_evidence_artifacts": artifact_rows,
                    "FROM cache.websim_gear_evidence_observations": observation_rows,
                    "FROM ops.websim_gear_evidence_gaps": gap_rows,
                }
                rowsets[missing_marker] = []
                missing_conn = FakeConnection(rowsets=rowsets)
                with self.assertRaisesRegex(
                    GearReleaseIntegrityError,
                    error_pattern,
                ):
                    self.trusted_gear_store(
                        missing_conn
                    ).seal_gear_release(
                        release,
                        snapshot,
                        gate_result=gate,
                    )

        unrelated_observation_rows = copy.deepcopy(observation_rows)
        unrelated = list(unrelated_observation_rows[0])
        unrelated[4] = "socket_count"
        unrelated[5] = 1
        unrelated_observation_rows[0] = tuple(unrelated)
        semantic_mismatch_conn = FakeConnection(rowsets={
            **self.staging_rowsets(self.canonical_staging_snapshot()),
            **self.complete_evidence_rowsets(
                artifact_rows,
                unrelated_observation_rows,
                gap_rows,
            ),
            "FROM cache.websim_release_registry": [],
            "JOIN cache.websim_gear_canonical_facts": fact_rows,
            "FROM cache.websim_gear_evidence_artifacts": artifact_rows,
            "FROM cache.websim_gear_evidence_observations": (
                unrelated_observation_rows
            ),
            "FROM ops.websim_gear_evidence_gaps": gap_rows,
        })
        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "not self-authenticating",
        ):
            self.trusted_gear_store(
                semantic_mismatch_conn
            ).seal_gear_release(
                release,
                snapshot,
                gate_result=gate,
            )

    def test_seal_rejects_socket_probe_envelope_without_runtime_anchor(self):
        from server import gear_release_store, gear_release_tool
        from server.gear_release_store import (
            GearReleaseIntegrityError,
            GearReleaseStore,
        )

        (
            snapshot,
            release,
            gate,
            fact_rows,
            artifact_rows,
            observation_rows,
            gap_rows,
        ) = self.canonical_seal_fixture()
        forged_evidence = self.trusted_socket_evidence("forged-runtime")
        forged_source = copy.deepcopy(release["source"])
        forged_source["sourceEvidence"]["socketBonusEvidence"] = (
            forged_evidence
        )
        forged_source["sourceEvidence"]["socketProbeDigest"] = (
            gear_release_tool._socket_probe_digest(forged_evidence)
        )
        forged_release = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_release_store.gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source=forged_source,
        )
        conn = FakeConnection(rowsets={
            **self.staging_rowsets(self.canonical_staging_snapshot()),
            **self.complete_evidence_rowsets(
                artifact_rows, observation_rows, gap_rows
            ),
            "FROM cache.websim_release_registry": [],
            "JOIN cache.websim_gear_canonical_facts": fact_rows,
            "FROM cache.websim_gear_evidence_artifacts": artifact_rows,
            "FROM cache.websim_gear_evidence_observations": observation_rows,
            "FROM ops.websim_gear_evidence_gaps": gap_rows,
        })
        store = self.trusted_gear_store(conn)
        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "trusted SimC socket probe",
        ):
            store.seal_gear_release(
                forged_release,
                snapshot,
                gate_result=gate,
            )

    def test_seal_rejects_artifact_payload_forged_under_expected_identity(self):
        from server import gear_release_store
        from server.gear_release_store import GearReleaseIntegrityError

        (
            snapshot,
            release,
            gate,
            fact_rows,
            artifact_rows,
            observation_rows,
            gap_rows,
        ) = self.canonical_seal_fixture()
        forged_artifact_rows = copy.deepcopy(artifact_rows)
        forged_artifact = list(forged_artifact_rows[0])
        forged_artifact[8] = {
            **forged_artifact[8],
            "forgedClaim": True,
        }
        forged_artifact[7] = gear_release_store._hash(
            forged_artifact[8]
        )
        forged_artifact_rows[0] = tuple(forged_artifact)
        conn = FakeConnection(rowsets={
            **self.staging_rowsets(self.canonical_staging_snapshot()),
            **self.complete_evidence_rowsets(
                forged_artifact_rows,
                observation_rows,
                gap_rows,
            ),
            "FROM cache.websim_release_registry": [],
            "JOIN cache.websim_gear_canonical_facts": fact_rows,
        })

        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "not self-authenticating",
        ):
            self.trusted_gear_store(conn).seal_gear_release(
                release,
                snapshot,
                gate_result=gate,
            )

    def test_seal_derives_supporting_evidence_beyond_receipt(self):
        from server import gear_release_store
        from server.gear_release_store import (
            GearReleaseIntegrityError,
        )

        (
            snapshot,
            release,
            gate,
            fact_rows,
            artifact_rows,
            observation_rows,
            gap_rows,
        ) = self.canonical_seal_fixture()
        for owner in ("artifacts", "observations"):
            with self.subTest(omitted_owner=owner):
                omitted_gate = copy.deepcopy(gate)
                omitted_gate["evidenceCompilation"][owner] = {
                    "count": 0,
                    "identities": [],
                    "identityDigest": gear_release_store._hash([]),
                }
                omitted_gate["evidencePersistence"][owner] = {
                    "persisted": 0,
                    "identities": [],
                    "identityDigest": gear_release_store._hash([]),
                }
                conn = FakeConnection(rowsets={
                    **self.staging_rowsets(
                        self.canonical_staging_snapshot()
                    ),
                    **self.complete_evidence_rowsets(
                        artifact_rows,
                        observation_rows,
                        gap_rows,
                    ),
                    "FROM cache.websim_release_registry": [],
                    "JOIN cache.websim_gear_canonical_facts": fact_rows,
                })
                with self.assertRaisesRegex(
                    GearReleaseIntegrityError,
                    "receipt omits complete Store evidence universe",
                ):
                    self.trusted_gear_store(
                        conn
                    ).seal_gear_release(
                        release,
                        snapshot,
                        gate_result=omitted_gate,
                    )

    def test_seal_rejects_gap_rows_without_exact_requirement_semantics(self):
        from server.gear_release_store import (
            GearReleaseIntegrityError,
            GearReleaseStore,
        )

        (
            snapshot,
            release,
            gate,
            fact_rows,
            artifact_rows,
            observation_rows,
            gap_rows,
        ) = self.canonical_seal_fixture()
        forged_gap_rows = copy.deepcopy(gap_rows)
        forged_gap = list(forged_gap_rows[0])
        forged_gap[2] = "source_unavailable"
        forged_gap[3] = {
            **forged_gap[3],
            "requiredInputKey": "forged",
        }
        forged_gap_rows[0] = tuple(forged_gap)
        conn = FakeConnection(rowsets={
            **self.staging_rowsets(self.canonical_staging_snapshot()),
            **self.complete_evidence_rowsets(
                artifact_rows,
                observation_rows,
                forged_gap_rows,
            ),
            "FROM cache.websim_release_registry": [],
            "JOIN cache.websim_gear_canonical_facts": fact_rows,
            "FROM cache.websim_gear_evidence_artifacts": artifact_rows,
            "FROM cache.websim_gear_evidence_observations": observation_rows,
            "FROM ops.websim_gear_evidence_gaps": gap_rows,
        })
        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "Gap semantics",
        ):
            self.trusted_gear_store(
                conn
            ).seal_gear_release(
                release,
                snapshot,
                gate_result=gate,
            )

    def test_seal_release_is_idempotent_only_for_exact_existing_descriptor(self):
        from server.gear_release_store import GearReleaseIntegrityError, GearReleaseStore

        (
            snapshot,
            release,
            gate,
            fact_rows,
            artifact_rows,
            observation_rows,
            gap_rows,
        ) = self.canonical_seal_fixture()
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
        conn = FakeConnection(rowsets={
            **self.staging_rowsets(self.canonical_staging_snapshot()),
            **self.complete_evidence_rowsets(
                artifact_rows, observation_rows, gap_rows
            ),
            "FROM cache.websim_release_registry": [existing_row],
            "JOIN cache.websim_gear_canonical_facts": fact_rows,
            "FROM cache.websim_gear_evidence_artifacts": artifact_rows,
            "FROM cache.websim_gear_evidence_observations": observation_rows,
            "FROM ops.websim_gear_evidence_gaps": gap_rows,
        })
        store = self.trusted_gear_store(conn)
        self.assertEqual(
            store.seal_gear_release(
                release,
                snapshot,
                gate_result=gate,
            ),
            {"status": "reused", "releaseId": release["releaseId"]},
        )
        self.assertFalse(any("INSERT INTO" in sql for sql in conn.cursor_instance.statements))

        mismatch = list(existing_row)
        mismatch[4] = "sha256:different"
        bad_conn = FakeConnection(rowsets={
            **self.staging_rowsets(self.canonical_staging_snapshot()),
            **self.complete_evidence_rowsets(
                artifact_rows, observation_rows, gap_rows
            ),
            "FROM cache.websim_release_registry": [tuple(mismatch)],
            "JOIN cache.websim_gear_canonical_facts": fact_rows,
            "FROM cache.websim_gear_evidence_artifacts": artifact_rows,
            "FROM cache.websim_gear_evidence_observations": observation_rows,
            "FROM ops.websim_gear_evidence_gaps": gap_rows,
        })
        with self.assertRaises(GearReleaseIntegrityError):
            self.trusted_gear_store(bad_conn).seal_gear_release(
                release,
                snapshot,
                gate_result=gate,
            )
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
