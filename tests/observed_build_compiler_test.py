import unittest
from unittest import mock

from server.observed_build_compiler import (
    compile_observed_build,
    compile_with_postgres,
)
from server.observed_build_projection import build_dependency_vector
from server.observed_build_registry import build_observed_snapshot


class ObservedBuildCompilerTest(unittest.TestCase):
    def snapshot(self):
        return build_observed_snapshot(
            slot={
                "classKey": "mage",
                "specKey": "frost",
                "heroKey": "frostfire",
                "scenarioKey": "mythic_plus",
            },
            source={
                "sourceKey": "raiderio",
                "sourceIdentity": "raiderio:cn|realm-a|player-a",
                "profileUrl": "https://raider.io/characters/cn/realm-a/player-a",
                "region": "cn",
                "realm": "realm-a",
                "character": "player-a",
            },
            ranking_evidence={"rank": 1, "score": 4200, "maxKeyLevel": 22},
            talent_observation={
                "rawImportCode": "C4DA",
                "loadoutSpecId": 64,
                "heroSubTreeId": 38,
                "heroKey": "frostfire",
                "source": "run_detail",
                "loadout": [
                    {"traitId": 91001, "rank": 1},
                    {"traitId": 91003, "rank": 1},
                ],
            },
            gear_observation={
                "itemLevel": 710,
                "raceKey": "human",
                "gearItems": [
                    {
                        "slot": "head",
                        "itemId": 230001,
                        "itemLevel": 710,
                        "bonus_id": "10355",
                    }
                ],
            },
            source_revision="raiderio:season-tww-3:observed-profile-v1",
        )

    def dependencies(self, **overrides):
        values = {
            "season_revision": "season-tww-3",
            "talent_catalog_revision": "talent-catalog-v7",
            "gear_release_id": "gear-release:sha256:" + "1" * 64,
            "gear_rule_revision": "gear-rule-matrix-v1",
            "resolver_contract_revision": "gear-resolver-contract-v1",
            "serializer_revision": "websim-profile-compat-v1",
            "simc_runtime_revision": "simc-runtime-abc",
            "selection_schema_revision": "selection-intent-v1",
            "projection_schema_revision": "observed-build-projection-v1",
        }
        values.update(overrides)
        return build_dependency_vector(**values)

    @staticmethod
    def verified_talent():
        return {
            "status": "verified",
            "heroKey": "frostfire",
            "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
            "websimExportCode": "websim:mage:frost:frostfire:encoded",
            "signature": "talent-signature-a",
        }

    @staticmethod
    def verified_gear():
        return {
            "status": "verified",
            "selectionIntent": {
                "schemaRevision": "selection-intent-v1",
                "slots": {"head": {"itemId": "230001", "variantKey": "variant-a"}},
            },
            "gearItems": [{"slot": "head", "itemId": "230001"}],
            "profileReadiness": {"status": "ready", "simcReady": True},
            "resolvedGearSignature": "sha256:" + "2" * 64,
        }

    def test_both_authorities_must_pass_for_one_importable_projection(self):
        projection = compile_observed_build(
            self.snapshot(),
            self.dependencies(),
            talent_compiler=lambda snapshot: self.verified_talent(),
            gear_compiler=lambda snapshot: self.verified_gear(),
        )

        self.assertEqual(projection["status"], "verified")
        self.assertTrue(projection["importable"])
        self.assertTrue(projection["profileReadiness"]["simcReady"])
        self.assertRegex(
            projection["profileReadiness"]["profileSignature"],
            r"^sha256:[0-9a-f]{64}$",
        )

    def test_gear_failure_blocks_talent_switch_in_the_same_projection(self):
        projection = compile_observed_build(
            self.snapshot(),
            self.dependencies(),
            talent_compiler=lambda snapshot: self.verified_talent(),
            gear_compiler=lambda snapshot: {
                "status": "blocked",
                "problems": [{"code": "gear_item_unmapped", "stage": "gear"}],
            },
        )

        self.assertEqual(projection["status"], "blocked")
        self.assertFalse(projection["importable"])
        self.assertEqual(projection["problems"][0]["code"], "gear_item_unmapped")

    def test_both_adapters_receive_the_same_immutable_snapshot(self):
        snapshot = self.snapshot()
        seen = []

        compile_observed_build(
            snapshot,
            self.dependencies(),
            talent_compiler=lambda value: (
                seen.append(("talent", value)) or self.verified_talent()
            ),
            gear_compiler=lambda value: (
                seen.append(("gear", value)) or self.verified_gear()
            ),
        )

        self.assertIs(seen[0][1], snapshot)
        self.assertIs(seen[1][1], snapshot)

    def test_adapter_exception_is_bounded_and_does_not_leak_payload(self):
        secret = "postgres://admin:secret@example.invalid/database"

        def fail(_snapshot):
            raise RuntimeError(secret)

        projection = compile_observed_build(
            self.snapshot(),
            self.dependencies(),
            talent_compiler=fail,
            gear_compiler=lambda snapshot: self.verified_gear(),
        )

        self.assertEqual(projection["status"], "blocked")
        self.assertEqual(
            projection["problems"][0],
            {
                "code": "talent_projection_failed",
                "stage": "talent_projection",
                "message": "Talent projection failed unexpectedly.",
            },
        )
        self.assertNotIn(secret, str(projection))

    def test_postgres_adapter_reuses_existing_authorities_without_simc(self):
        snapshot = self.snapshot()
        dependencies = self.dependencies()
        store = _FakeCompilerStore(dependencies)
        resolved = {
            "status": "verified",
            "dependencyVector": {
                **dependencies,
                "gearCatalogReleaseId": dependencies["gearReleaseId"],
                "gearCatalogRevision": dependencies["gearReleaseId"],
            },
            "resolvedGearSignature": "sha256:" + "3" * 64,
            "resolvedSlots": {
                "head": {
                    "itemId": "230001",
                    "variantKey": "variant-observed",
                    "simcOptions": {"ilevel": "710", "bonus_id": "10355"},
                }
            },
            "serializerInput": {
                "gearItems": [
                    {
                        "slot": "head",
                        "itemId": "230001",
                        "variantKey": "variant-observed",
                        "simcOptions": {"ilevel": "710", "bonus_id": "10355"},
                    }
                ]
            },
            "profileReadiness": {
                "status": "ready",
                "simcReady": True,
                "requiredSlots": ["head"],
                "readySlots": ["head"],
            },
            "problems": [],
        }
        validated_talent = {
            "status": "verified",
            "heroKey": "frostfire",
            "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
            "websimExportCode": "websim:mage:frost:frostfire:encoded",
            "rawImportCode": "C4DA",
            "signature": "talent-signature-a",
            "updatedAt": "2026-07-23T12:00:00+00:00",
            "expiresAt": "2026-07-30T12:00:00+00:00",
        }

        with (
            mock.patch(
                "server.observed_build_compiler.validate_community_talent_template",
                return_value=validated_talent,
            ) as talent_validator,
            mock.patch(
                "server.observed_build_compiler.gear_resolver.resolve",
                return_value=resolved,
            ) as resolver,
        ):
            projection = compile_with_postgres(
                store,
                snapshot,
                dependencies,
                "simc-runtime-abc",
            )

        self.assertTrue(projection["importable"])
        self.assertIs(talent_validator.call_args.args[0], store)
        talent_candidate = talent_validator.call_args.args[1]
        self.assertEqual(
            talent_candidate["payload"]["raiderio"]["sourceIdentity"],
            snapshot["source"]["sourceIdentity"],
        )
        self.assertEqual(
            store.backfill_calls[0]["enable_simc_stats"],
            False,
        )
        self.assertEqual(
            store.backfill_calls[0]["raiderio_payload"]["profiles"][0]["gear"],
            snapshot["gearObservation"]["gearItems"],
        )
        self.assertEqual(store.context_calls[0][0]["schemaRevision"], "selection-intent-v1")
        self.assertIs(resolver.call_args.args[1], store.authority_context)
        self.assertEqual(
            projection["gearProjection"]["resolvedGearSignature"],
            resolved["resolvedGearSignature"],
        )

    def test_postgres_adapter_blocks_dependency_or_runtime_drift_before_backfill(self):
        dependencies = self.dependencies()
        store = _FakeCompilerStore(dependencies)

        projection = compile_with_postgres(
            store,
            self.snapshot(),
            dependencies,
            "simc-runtime-other",
        )

        self.assertEqual(projection["status"], "blocked")
        self.assertEqual(
            projection["problems"][1]["code"],
            "gear_projection_failed",
        )
        self.assertEqual(store.backfill_calls, [])


class _FakeCompilerStore:
    def __init__(self, dependencies):
        self.dependencies = dependencies
        self.backfill_calls = []
        self.context_calls = []
        self.authority_context = {"sealed": True}

    def backfill_observed_gear_from_raiderio(self, raiderio_payload, **kwargs):
        self.backfill_calls.append(
            {"raiderio_payload": raiderio_payload, **kwargs}
        )
        return {"status": "verified"}

    def get_observed_build_gear_compile_context(self, gear_items):
        self.compile_context_gear_items = gear_items
        profile_url = "https://raider.io/characters/cn/realm-a/player-a"
        return {
            "manifest": {
                "seasonRevision": self.dependencies["seasonRevision"],
                "gearCatalogReleaseId": self.dependencies["gearReleaseId"],
            },
            "gearRelease": {
                "releaseId": self.dependencies["gearReleaseId"],
                "dependencyRevisions": {
                    "capabilityRevision": "gear-capability-matrix-v2",
                },
            },
            "gearSnapshot": {
                "items": [
                    {
                        "itemId": "230001",
                        "name": "Observed Helm",
                        "slot": "head",
                        "itemLevel": 710,
                        "sourceStatus": "verified",
                        "payload": {},
                    }
                ],
                "sources": [],
                "variants": [
                    {
                        "variantId": "variant-observed-id",
                        "itemId": "230001",
                        "variantKey": "variant-observed",
                        "slot": "head",
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 710,
                        "simcOptions": {
                            "ilevel": "710",
                            "bonus_id": "10355",
                        },
                        "status": "verified",
                        "blockers": [],
                        "payload": {"profileUrl": profile_url},
                    }
                ],
                "options": [],
            },
        }

    def get_gear_authority_context(self, selection_intent, runtime_authority):
        self.context_calls.append((selection_intent, runtime_authority))
        return self.authority_context


if __name__ == "__main__":
    unittest.main()
