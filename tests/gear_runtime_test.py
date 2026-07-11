import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from server import gear_runtime


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gear-resolver-complete-authority-v1.json"


class FakeStore:
    def __init__(self, context=None, error=None):
        self.context = context
        self.error = error
        self.calls = []

    def get_gear_authority_context(self, intent, runtime_authority):
        self.calls.append(
            {
                "intent": copy.deepcopy(intent),
                "runtimeAuthority": copy.deepcopy(runtime_authority),
            }
        )
        if self.error is not None:
            raise self.error
        return copy.deepcopy(self.context)


class FakeCandidateStore(FakeStore):
    def get_gear_authority_context(self, intent, runtime_authority):
        raise AssertionError("candidate shadow must not use transitional authority")

    def get_candidate_gear_authority_context(self, intent, runtime_authority, gear_release_id):
        self.calls.append(
            {
                "intent": copy.deepcopy(intent),
                "runtimeAuthority": copy.deepcopy(runtime_authority),
                "gearReleaseId": gear_release_id,
            }
        )
        if self.error is not None:
            raise self.error
        return copy.deepcopy(self.context)


class GearRuntimeTest(unittest.TestCase):
    def fixture(self):
        return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def resolve(self, fixture=None, *, store=None, request_id="request-test"):
        fixture = fixture or self.fixture()
        store = store or FakeStore(fixture["authorityContext"])
        status, envelope = gear_runtime.resolve_selection_intent(
            fixture["intent"],
            store=store,
            simc_runtime_revision="simc-v1",
            request_id=request_id,
        )
        return store, status, envelope

    def test_runtime_imports_from_server_directory_for_direct_backend_startup(self):
        server_dir = Path(__file__).resolve().parents[1] / "server"

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import gear_runtime; print(gear_runtime.resolve_selection_intent.__name__)",
            ],
            cwd=server_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "resolve_selection_intent")

    def test_malformed_intent_returns_400_without_store_call(self):
        store = FakeStore(error=AssertionError("invalid Intent must not query authority"))

        status, envelope = gear_runtime.resolve_selection_intent(
            {"schemaRevision": "selection-intent-v1", "stats": {"strength": 999999}},
            store=store,
            simc_runtime_revision="simc-v1",
            request_id="request-invalid",
        )

        self.assertEqual(status, 400)
        self.assertEqual(envelope["contractRevision"], "gear-result-envelope-v1")
        self.assertEqual(envelope["requestId"], "request-invalid")
        self.assertEqual(envelope["status"], "blocked")
        self.assertEqual(envelope["releaseContext"], {})
        self.assertTrue(any(problem["kind"] == "INVALID_INTENT" for problem in envelope["problems"]))
        self.assertEqual(store.calls, [])
        self.assertNotIn("999999", json.dumps(envelope))

    def test_legal_intent_resolves_once_into_200_envelope(self):
        fixture = self.fixture()
        fixture["authorityContext"]["manifest"].update(
            {
                "manifestRevision": "season-manifest:r17",
                "pointerGeneration": 9,
                "communityTemplateReleaseId": "community-release:r17",
                "talentCatalogRevision": "talent-catalog:r17",
                "formalActiveManifest": True,
            }
        )

        store, status, envelope = self.resolve(fixture, request_id="request-legal")

        self.assertEqual(status, 200)
        self.assertEqual(envelope["status"], "resolved")
        self.assertEqual(envelope["requestId"], "request-legal")
        self.assertEqual(envelope["data"]["status"], "verified")
        self.assertTrue(envelope["data"]["profileReadiness"]["simcReady"])
        self.assertEqual(envelope["problems"], [])
        self.assertEqual(len(store.calls), 1)
        self.assertEqual(store.calls[0]["intent"], fixture["intent"])
        self.assertEqual(
            store.calls[0]["runtimeAuthority"]["dependencyRevisions"]["simcRuntimeRevision"],
            "simc-v1",
        )
        self.assertEqual(
            envelope["releaseContext"]["gearCatalogRevision"],
            fixture["authorityContext"]["manifest"]["gearCatalogRevision"],
        )
        self.assertEqual(envelope["releaseContext"]["manifestRevision"], "season-manifest:r17")
        self.assertEqual(envelope["releaseContext"]["pointerGeneration"], 9)
        self.assertEqual(
            envelope["releaseContext"]["communityTemplateRevision"],
            "community-release:r17",
        )
        self.assertEqual(envelope["releaseContext"]["talentCatalogRevision"], "talent-catalog:r17")
        self.assertTrue(envelope["releaseContext"]["formalActiveManifest"])

    def test_candidate_shadow_resolves_only_through_exact_release_reader(self):
        fixture = self.fixture()
        gear_release_id = fixture["intent"]["authoredAgainst"]["gearCatalogRevision"]
        store = FakeCandidateStore(fixture["authorityContext"])

        status, envelope = gear_runtime.resolve_candidate_selection_intent(
            fixture["intent"],
            store=store,
            gear_release_id=gear_release_id,
            simc_runtime_revision="simc-v1",
            request_id="request-candidate",
        )

        self.assertEqual(status, 200)
        self.assertEqual(envelope["status"], "resolved")
        self.assertEqual(len(store.calls), 1)
        self.assertEqual(store.calls[0]["gearReleaseId"], gear_release_id)

        unavailable = FakeCandidateStore(error=RuntimeError("release content missing"))
        failed_status, failed = gear_runtime.resolve_candidate_selection_intent(
            fixture["intent"],
            store=unavailable,
            gear_release_id=gear_release_id,
            simc_runtime_revision="simc-v1",
            request_id="request-candidate-missing",
        )
        self.assertEqual(failed_status, 503)
        self.assertEqual(failed["problems"][0]["code"], "GEAR_AUTHORITY_READ_UNAVAILABLE")

    def test_illegal_intent_returns_200_blocked_with_snapshot_problems(self):
        fixture = self.fixture()
        fixture["intent"]["slots"]["head"] = {
            "itemId": "item-unique-ring",
            "variantKey": "variant-unique-ring",
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        }

        _store, status, envelope = self.resolve(fixture)

        self.assertEqual(status, 200)
        self.assertEqual(envelope["status"], "blocked")
        self.assertEqual(envelope["data"]["status"], "blocked")
        self.assertTrue(any(problem["kind"] == "ILLEGAL_SELECTION" for problem in envelope["problems"]))

    def test_revision_conflict_returns_409_with_current_release_context(self):
        fixture = self.fixture()
        fixture["authorityContext"]["manifest"]["gearCatalogRevision"] = "gear-r18"
        fixture["authorityContext"]["dependencyVector"]["gearCatalogRevision"] = "gear-r18"

        _store, status, envelope = self.resolve(fixture)

        self.assertEqual(status, 409)
        self.assertEqual(envelope["status"], "blocked")
        self.assertEqual(envelope["releaseContext"]["gearCatalogRevision"], "gear-r18")
        self.assertTrue(any(problem["kind"] == "REVISION_CONFLICT" for problem in envelope["problems"]))

    def test_missing_authority_returns_503_without_client_fallback(self):
        fixture = self.fixture()
        fixture["authorityContext"].pop("itemsById")

        _store, status, envelope = self.resolve(fixture)

        self.assertEqual(status, 503)
        self.assertEqual(envelope["status"], "unavailable")
        self.assertTrue(any(problem["kind"] == "AUTHORITY_UNAVAILABLE" for problem in envelope["problems"]))

    def test_missing_simc_runtime_revision_returns_503_without_store_call(self):
        fixture = self.fixture()
        store = FakeStore(error=AssertionError("missing runtime revision must not query authority"))

        status, envelope = gear_runtime.resolve_selection_intent(
            fixture["intent"],
            store=store,
            simc_runtime_revision="",
            request_id="request-missing-simc",
        )

        self.assertEqual(status, 503)
        self.assertEqual(envelope["status"], "unavailable")
        self.assertEqual(envelope["problems"][0]["kind"], "AUTHORITY_UNAVAILABLE")
        self.assertEqual(
            envelope["problems"][0]["code"],
            "GEAR_SIMC_RUNTIME_REVISION_UNAVAILABLE",
        )
        self.assertEqual(store.calls, [])

    def test_store_failure_returns_sanitized_503(self):
        fixture = self.fixture()
        store = FakeStore(
            error=RuntimeError(
                "postgresql://secret-user:secret-password@db/production SELECT private_table"
            )
        )

        status, envelope = gear_runtime.resolve_selection_intent(
            fixture["intent"],
            store=store,
            simc_runtime_revision="simc-v1",
            request_id="request-store-failure",
        )

        self.assertEqual(status, 503)
        self.assertEqual(envelope["status"], "unavailable")
        self.assertTrue(any(problem["kind"] == "AUTHORITY_UNAVAILABLE" for problem in envelope["problems"]))
        serialized = json.dumps(envelope)
        self.assertNotIn("secret-user", serialized)
        self.assertNotIn("private_table", serialized)

    def test_unexpected_resolver_failure_returns_sanitized_500(self):
        fixture = self.fixture()
        store = FakeStore(fixture["authorityContext"])

        with patch.object(gear_runtime.gear_resolver, "resolve", side_effect=TypeError("private resolver detail")):
            status, envelope = gear_runtime.resolve_selection_intent(
                fixture["intent"],
                store=store,
                simc_runtime_revision="simc-v1",
                request_id="request-internal",
            )

        self.assertEqual(status, 500)
        self.assertEqual(envelope["status"], "unavailable")
        self.assertTrue(any(problem["kind"] == "INTERNAL_ERROR" for problem in envelope["problems"]))
        self.assertNotIn("private resolver detail", json.dumps(envelope))

    def test_profile_mode_re_resolves_and_filters_client_final_facts(self):
        fixture = self.fixture()
        store = FakeStore(fixture["authorityContext"])
        builder_calls = []

        def profile_builder(snapshot, source_context=None):
            builder_calls.append(
                {
                    "snapshot": copy.deepcopy(snapshot),
                    "sourceContext": copy.deepcopy(source_context),
                }
            )
            return {
                "status": "resolved",
                "profile": 'warrior="Canonical"',
                "gearItems": snapshot["serializerInput"]["gearItems"],
                "simcItems": snapshot["serializerInput"]["gearItems"],
                "talentEncoding": {"status": "external", "errors": []},
                "profileReadiness": snapshot["profileReadiness"],
                "resolvedGearSignature": snapshot["resolvedGearSignature"],
                "evidenceLedger": snapshot["evidenceLedger"],
                "problems": [],
            }

        status, envelope = gear_runtime.build_profile_from_selection_intent(
            {
                "selectionIntent": fixture["intent"],
                "profileContext": {
                    "name": "Canonical",
                    "race": "orc",
                    "scenarioKey": "single",
                    "heroKey": "",
                    "talents": "external-talent-code",
                    "talentImport": "external-talent-code",
                    "websimExportCode": "websim:warrior:fury::",
                    "talentState": {"selectedNodes": []},
                    "classKey": "mage",
                    "specKey": "arcane",
                    "level": 1,
                    "gearSelection": {"items": [{"itemId": "forged"}]},
                    "enhancementBySlot": {"head": {"gemOptionIds": ["forged"]}},
                    "serializerInput": {"gearItems": [{"itemId": "forged"}]},
                    "resolvedSlots": {"head": {"itemId": "forged"}},
                    "evidenceLedger": {"claims": [{"status": "verified"}]},
                    "profileReadiness": {"simcReady": True},
                },
                "resolvedSnapshot": {"status": "verified", "serializerInput": {"gearItems": []}},
            },
            store=store,
            simc_runtime_revision="simc-v1",
            request_id="request-profile",
            profile_builder=profile_builder,
        )

        self.assertEqual(status, 200)
        self.assertEqual(envelope["status"], "resolved")
        self.assertEqual(envelope["data"]["profile"], 'warrior="Canonical"')
        self.assertEqual(len(store.calls), 1)
        self.assertEqual(len(builder_calls), 1)
        self.assertEqual(builder_calls[0]["snapshot"]["status"], "verified")
        self.assertEqual(
            set(builder_calls[0]["sourceContext"]),
            {
                "name",
                "race",
                "scenarioKey",
                "heroKey",
                "talents",
                "talentImport",
                "websimExportCode",
                "talentState",
            },
        )
        serialized_context = json.dumps(builder_calls[0]["sourceContext"])
        self.assertNotIn("forged", serialized_context)
        self.assertNotIn("classKey", builder_calls[0]["sourceContext"])

    def test_profile_mode_blocks_facade_result_without_executable_talents(self):
        fixture = self.fixture()
        store = FakeStore(fixture["authorityContext"])

        status, envelope = gear_runtime.build_profile_from_selection_intent(
            {
                "selectionIntent": fixture["intent"],
                "profileContext": {},
            },
            store=store,
            simc_runtime_revision="simc-v1",
            request_id="request-profile-no-talents",
        )

        self.assertEqual(status, 200)
        self.assertEqual(envelope["status"], "blocked")
        self.assertEqual(envelope["data"]["status"], "blocked")
        self.assertEqual(envelope["data"]["profile"], "")
        self.assertFalse(envelope["data"]["profileReadiness"]["simcReady"])
        self.assertEqual(envelope["data"]["profileReadiness"]["status"], "blocked")
        self.assertEqual(envelope["problems"][0]["code"], "GEAR_PROFILE_NOT_READY")

    def test_candidate_profile_re_resolves_through_exact_release_reader(self):
        fixture = self.fixture()
        gear_release_id = fixture["intent"]["authoredAgainst"]["gearCatalogRevision"]
        store = FakeCandidateStore(fixture["authorityContext"])

        def profile_builder(snapshot, source_context=None):
            return {
                "status": "resolved",
                "profile": 'warrior="Candidate"',
                "talentEncoding": {"status": "external"},
                "profileReadiness": {"status": "verified", "simcReady": True},
                "problems": [],
            }

        status, envelope = gear_runtime.build_candidate_profile_from_selection_intent(
            {
                "selectionIntent": fixture["intent"],
                "profileContext": {"talents": "external-talent-code"},
            },
            store=store,
            gear_release_id=gear_release_id,
            simc_runtime_revision="simc-v1",
            request_id="request-candidate-profile",
            profile_builder=profile_builder,
        )

        self.assertEqual(status, 200)
        self.assertEqual(envelope["status"], "resolved")
        self.assertEqual(envelope["data"]["profile"], 'warrior="Candidate"')
        self.assertEqual(store.calls[0]["gearReleaseId"], gear_release_id)

    def test_candidate_profile_fails_closed_without_release_id(self):
        fixture = self.fixture()
        store = FakeCandidateStore(fixture["authorityContext"])

        status, envelope = gear_runtime.build_candidate_profile_from_selection_intent(
            {"selectionIntent": fixture["intent"], "profileContext": {}},
            store=store,
            gear_release_id="",
            simc_runtime_revision="simc-v1",
            request_id="request-candidate-profile-missing-release",
        )

        self.assertEqual(status, 503)
        self.assertEqual(envelope["problems"][0]["code"], "GEAR_RELEASE_ID_UNAVAILABLE")
        self.assertEqual(store.calls, [])

    def test_legacy_profile_request_is_not_claimed_by_canonical_mode(self):
        self.assertFalse(gear_runtime.is_canonical_profile_request({"classKey": "mage"}))
        self.assertFalse(gear_runtime.is_canonical_profile_request(None))
        self.assertTrue(gear_runtime.is_canonical_profile_request({"selectionIntent": {}}))


if __name__ == "__main__":
    unittest.main()
