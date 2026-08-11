import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

try:
    from server.catalog_candidate_evidence_assembly import (
        assemble_catalog_candidate_evidence,
    )
    from server.catalog_candidate_evidence_runner import (
        _build_variant_smoke_callback,
        run_catalog_candidate_evidence,
    )
    from server.gear_variant_materialization_matrix import (
        build_gear_variant_materialization_matrix,
    )
    from server.gear_variant_simc_matrix import (
        build_gear_variant_simc_matrix,
    )
except ModuleNotFoundError:
    assemble_catalog_candidate_evidence = None
    build_gear_variant_materialization_matrix = None
    build_gear_variant_simc_matrix = None
    _build_variant_smoke_callback = None
    run_catalog_candidate_evidence = None


def _load_cli_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "catalog-candidate-evidence.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("catalog_candidate_evidence_cli", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RecordingFactory:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        return copy.deepcopy(self.response)


class PointerReader:
    def __init__(self, responses):
        self.responses = [copy.deepcopy(value) for value in responses]
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if not self.responses:
            raise AssertionError("unexpected extra pointer read")
        return copy.deepcopy(self.responses.pop(0))


class RequestJson:
    def __init__(self, expected_identity, *, payload_builder=None, profile_text="player=Candidate\nclass=mage"):
        self.expected_identity = copy.deepcopy(expected_identity)
        self.payload_builder = payload_builder
        self.profile_text = profile_text
        self.calls = []

    def __call__(self, method, path, payload, headers):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "payload": copy.deepcopy(payload),
                "headers": copy.deepcopy(headers),
            }
        )
        if method == "GET" and path.startswith("/api/websim/gear?"):
            query = parse_qs(urlparse(path).query)
            class_key = query["class"][0]
            spec_key = query["spec"][0]
            slot = query["slot"][0]
            if self.payload_builder is None:
                return 200, {}, 1.0
            return 200, self.payload_builder(class_key, spec_key, slot), 1.0
        if method == "POST" and path == "/api/websim/profile":
            body = payload if isinstance(payload, dict) else {}
            selection_intent = (
                body.get("selectionIntent")
                if isinstance(body.get("selectionIntent"), dict)
                else {}
            )
            eligibility = (
                selection_intent.get("eligibilityContext")
                if isinstance(selection_intent.get("eligibilityContext"), dict)
                else {}
            )
            return 200, {
                "status": "resolved",
                "releaseContext": {
                    "manifestRevision": self.expected_identity["manifestRevision"],
                    "pointerGeneration": self.expected_identity["pointerGeneration"],
                    "gearCatalogRevision": self.expected_identity["gearCatalogRevision"],
                    "gearExactRegistryRevision": self.expected_identity["gearExactRegistryRevision"],
                    "simcRuntimeRevision": self.expected_identity["simcRuntimeRevision"],
                },
                "data": {
                    "status": "resolved",
                    "profile": self.profile_text,
                    "profileReadiness": {
                        "status": "verified",
                        "simcReady": True,
                    },
                    "selectionIntentEcho": {
                        "classKey": eligibility.get("classKey"),
                        "specKey": eligibility.get("specKey"),
                    },
                },
            }, 1.0
        raise AssertionError((method, path, payload, headers))


class SimcExecutor:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, profile):
        self.calls.append(profile)
        return copy.deepcopy(self.response)


class CatalogCandidateEvidenceRunnerTest(unittest.TestCase):
    maxDiff = None

    def test_cli_pointer_adapter_reads_revisions_from_nested_active_manifest(self):
        cli = _load_cli_module()
        self.assertIsNotNone(cli)

        binding = {
            "generation": 35,
            "manifestRevision": "season-manifest:sha256:" + "1" * 64,
            "manifest": {
                "gearCatalogRevision": "gear-catalog:sha256:" + "2" * 64,
                "gearExactRegistryRevision": "gear-exact-registry:sha256:" + "3" * 64,
            },
        }

        self.assertEqual(
            cli._pointer_from_binding(binding),
            {
                "generation": 35,
                "manifestRevision": binding["manifestRevision"],
                "gearCatalogRevision": binding["manifest"]["gearCatalogRevision"],
                "gearExactRegistryRevision": binding["manifest"]["gearExactRegistryRevision"],
            },
        )

    def expected_identity(self, **overrides):
        payload = {
            "manifestRevision": "manifest:sha256:" + "1" * 64,
            "pointerGeneration": 35,
            "gearCatalogRevision": "gear-catalog:sha256:" + "2" * 64,
            "gearExactRegistryRevision": "gear-exact-registry:sha256:" + "3" * 64,
            "simcRuntimeRevision": "simc:" + "4" * 40,
            "gearReleaseId": "gear-release:sha256:" + "5" * 64,
            "communityReleaseId": "community-release:sha256:" + "6" * 64,
        }
        payload.update(overrides)
        return payload

    def pointer(self, **overrides):
        identity = self.expected_identity()
        payload = {
            "generation": identity["pointerGeneration"],
            "manifestRevision": identity["manifestRevision"],
            "gearCatalogRevision": identity["gearCatalogRevision"],
            "gearExactRegistryRevision": identity["gearExactRegistryRevision"],
        }
        payload.update(overrides)
        return payload

    def catalog(self, **overrides):
        identity = self.expected_identity()
        payload = {
            "status": "verified",
            "schemaRevision": "gear-catalog-v3",
            "seasonRevision": "season-r1",
            "catalogRevision": identity["gearCatalogRevision"],
            "contentSummary": {
                "exactDerivedVariantCount": 0,
            },
            "itemDefinitions": [
                {"itemId": "1001", "slot": "head"},
                {"itemId": "1002", "slot": "neck"},
            ],
            "browseVariants": [
                {"browseVariantKey": "browse-a", "itemId": "1001"},
                {"browseVariantKey": "browse-b", "itemId": "1002"},
            ],
            "problemCodes": [],
        }
        payload.update(overrides)
        return payload

    def exact_registry(self, **overrides):
        identity = self.expected_identity()
        payload = {
            "schemaRevision": "gear-exact-item-registry-v1",
            "status": "verified",
            "registryRevision": identity["gearExactRegistryRevision"],
            "gearExactRegistryRevision": identity["gearExactRegistryRevision"],
            "problemCodes": [],
            "templateReferences": [
                {
                    "validationStatus": "verified",
                    "exactItemInstanceKey": "exact-1",
                    "problemCodes": [],
                }
            ],
        }
        payload.update(overrides)
        return payload

    def supported_materialization_report(self, **overrides):
        payload = {
            "schemaRevision": "gear-variant-materialization-matrix-v1",
            "status": "verified",
            "expected_unique_variant_count": 1,
            "materialized_unique_variant_count": 1,
            "unique_variant_materialization_count": 1,
            "catalog_non_simulatable_count": 0,
            "silent_default_fill_count": 0,
            "missing_provenance_count": 0,
            "failureCodes": [],
            "failureSamples": [],
            "ledger": {
                "browse-a": {
                    "status": "verified",
                    "itemId": "1001",
                    "classKey": "mage",
                    "specKey": "frost",
                    "slot": "head",
                    "materializedItemId": "1001",
                    "materializedBrowseVariantKey": "browse-a",
                    "failureCodes": [],
                }
            },
        }
        payload.update(overrides)
        return payload

    def simc_26_14_report(self, **overrides):
        identity = self.expected_identity()
        payload = {
            "status": "pass",
            "manifestRevision": identity["manifestRevision"],
            "pointerGeneration": identity["pointerGeneration"],
            "gearCatalogRevision": identity["gearCatalogRevision"],
            "gearExactRegistryRevision": identity["gearExactRegistryRevision"],
            "simcRuntimeRevision": identity["simcRuntimeRevision"],
            "supported": {
                "expectedSpecCount": 26,
                "profileReadySpecCount": 26,
                "executedSpecCount": 26,
                "dpsMetricSpecCount": 26,
            },
            "unsupported": {
                "expectedSpecCount": 14,
                "deterministicallyBlockedSpecCount": 14,
            },
            "failureCount": 0,
            "failureCodes": {},
            "failureSamples": [],
        }
        payload.update(overrides)
        return payload

    def expected_specs_40(self):
        return [("class%02d" % index, "spec%02d" % index) for index in range(40)]

    def slot_payload(self, identity, class_key, spec_key, slot):
        variants = []
        if slot == "head":
            variants.append(
                {
                    "variantKey": "browse-a",
                    "itemId": "1001",
                    "status": "verified",
                    "itemLevel": 1,
                    "sourceType": "raid",
                    "progressionState": {},
                }
            )
        if slot == "neck" and class_key == "class00" and spec_key == "spec00":
            variants.append(
                {
                    "variantKey": "browse-b",
                    "itemId": "1002",
                    "status": "verified",
                    "itemLevel": 1,
                    "sourceType": "raid",
                    "progressionState": {},
                }
            )
        items = []
        if variants:
            item_id = variants[0]["itemId"]
            items.append(
                {
                    "itemId": item_id,
                    "slot": slot,
                    "compatibility": {
                        "classKey": class_key,
                        "specKey": spec_key,
                        "status": "compatible",
                    },
                    "defaultVariantKey": variants[0]["variantKey"],
                    "variants": variants,
                }
            )
        return {
            "candidatePreview": True,
            "formalActiveManifest": False,
            "manifestRevision": identity["manifestRevision"],
            "pointerGeneration": identity["pointerGeneration"],
            "gearCatalogReleaseId": identity["gearReleaseId"],
            "communityTemplateReleaseId": identity["communityReleaseId"],
            "gearCatalogRevision": identity["gearCatalogRevision"],
            "gearExactRegistryRevision": identity["gearExactRegistryRevision"],
            "replacementCandidates": [{"slot": slot, "items": items}],
        }

    def test_successful_run_records_40x16_contexts_and_assembles_verified_report(self):
        self.assertIsNotNone(run_catalog_candidate_evidence)
        self.assertIsNotNone(assemble_catalog_candidate_evidence)

        identity = self.expected_identity()
        request_json = RequestJson(
            identity,
            payload_builder=lambda class_key, spec_key, slot: self.slot_payload(
                identity, class_key, spec_key, slot
            ),
        )
        profile_factory = RecordingFactory(
            {
                "classKey": "class00",
                "specKey": "spec00",
                "race": "human",
                "scenarioKey": "single",
                "talents": "TALENTS",
                "level": 80,
            }
        )
        old_active_pointer = self.pointer(
            manifestRevision="season-manifest:sha256:" + "8" * 64,
            gearCatalogRevision="gear-catalog:sha256:" + "a" * 64,
            gearExactRegistryRevision="gear-exact-registry:sha256:" + "b" * 64,
        )
        pointer_reader = PointerReader([old_active_pointer, old_active_pointer])
        http_calls = []
        materializer_calls = []
        matrix_specs = {}

        def run_http_matrix(recording_request_json, **kwargs):
            self.assertEqual(len(kwargs["expected_specs"]), 40)
            matrix_specs["http"] = kwargs["expected_specs"]
            for class_key, spec_key in kwargs["expected_specs"]:
                for slot in (
                    "head",
                    "neck",
                    "shoulder",
                    "back",
                    "chest",
                    "wrist",
                    "hands",
                    "waist",
                    "legs",
                    "feet",
                    "finger1",
                    "finger2",
                    "trinket1",
                    "trinket2",
                    "main_hand",
                    "off_hand",
                ):
                    http_calls.append((class_key, spec_key, slot))
                    recording_request_json(
                        "GET",
                        f"/api/websim/gear?class={class_key}&spec={spec_key}&compact=1&mode=slot&slot={slot}",
                        None,
                        {"X-Wow-Platform": "miniprogram"},
                    )
            return {
                "schemaRevision": "gear-catalog-http-completeness-matrix-v2",
                "status": "pass",
                "bindingMode": "candidate_preview",
                "manifestRevision": identity["manifestRevision"],
                "pointerGeneration": identity["pointerGeneration"],
                "gearReleaseId": identity["gearReleaseId"],
                "communityReleaseId": identity["communityReleaseId"],
                "catalogRevision": identity["gearCatalogRevision"],
                "exactRegistryRevision": identity["gearExactRegistryRevision"],
                "failureCount": 0,
                "failureCodes": {},
                "failureSamples": [],
            }

        def build_materialization_runner(**_kwargs):
            def materialize(**kwargs):
                materializer_calls.append(copy.deepcopy(kwargs))
                return {
                    "status": "verified",
                    "selectionIntent": copy.deepcopy(kwargs["selection_intent"]),
                    "materializedItemId": kwargs["item_id"],
                    "materializedBrowseVariantKey": kwargs["browse_variant_key"],
                    "resolverStatus": "resolved",
                    "profileStatus": "resolved",
                    "simcReady": True,
                    "usedDefaultVariant": False,
                    "failureCodes": [],
                }

            return materialize

        def build_materialization_matrix(catalog, relation_contexts, materializer):
            self.assertEqual(catalog["catalogRevision"], identity["gearCatalogRevision"])
            self.assertEqual(
                [row["browseVariantKey"] for row in relation_contexts],
                ["browse-a", "browse-b"],
            )
            self.assertEqual(
                relation_contexts[0]["selectionIntent"],
                {
                    "schemaRevision": "selection-intent-v1",
                    "authoredAgainst": {
                        "seasonRevision": "season-r1",
                        "gearCatalogRevision": identity["gearCatalogRevision"],
                    },
                    "eligibilityContext": {
                        "classKey": "class00",
                        "specKey": "spec00",
                        "level": 80,
                    },
                    "slots": {
                        "head": {
                            "itemId": "1001",
                            "variantKey": "browse-a",
                        }
                    },
                },
            )
            self.assertEqual(
                relation_contexts[1]["selectionIntent"]["slots"],
                {
                    "neck": {
                        "itemId": "1002",
                        "variantKey": "browse-b",
                    }
                },
            )
            for row in relation_contexts:
                materializer(
                    item_id=row["itemId"],
                    browse_variant_key=row["browseVariantKey"],
                    class_key=row["classKey"],
                    spec_key=row["specKey"],
                    slot=row["slot"],
                    selection_intent=row["selectionIntent"],
                )
            return {
                "schemaRevision": "gear-variant-materialization-matrix-v1",
                "status": "verified",
                "expected_unique_variant_count": 2,
                "materialized_unique_variant_count": 2,
                "unique_variant_materialization_count": 2,
                "catalog_non_simulatable_count": 0,
                "silent_default_fill_count": 0,
                "missing_provenance_count": 0,
                "failureCodes": [],
                "failureSamples": [],
                "ledger": {
                    "browse-a": {
                        "status": "verified",
                        "itemId": "1001",
                        "classKey": "class00",
                        "specKey": "spec00",
                        "slot": "head",
                        "materializedItemId": "1001",
                        "materializedBrowseVariantKey": "browse-a",
                        "failureCodes": [],
                    },
                    "browse-b": {
                        "status": "verified",
                        "itemId": "1002",
                        "classKey": "class00",
                        "specKey": "spec00",
                        "slot": "neck",
                        "materializedItemId": "1002",
                        "materializedBrowseVariantKey": "browse-b",
                        "failureCodes": [],
                    },
                },
            }

        def run_simc_matrix(_request_json, _simc_executor, **_kwargs):
            matrix_specs["simc"] = _kwargs["expected_specs"]
            return self.simc_26_14_report()

        def build_variant_simc_matrix(materialization_report, smoke_callback):
            self.assertEqual(materialization_report["status"], "verified")
            first = smoke_callback(
                item_id="1001",
                browse_variant_key="browse-a",
                class_key="class00",
                spec_key="spec00",
                slot="head",
            )
            second = smoke_callback(
                item_id="1002",
                browse_variant_key="browse-b",
                class_key="class00",
                spec_key="spec00",
                slot="neck",
            )
            return {
                "schemaRevision": "gear-variant-simc-matrix-v1",
                "status": "verified",
                "expected_supported_variant_smoke_count": 2,
                "passed_supported_variant_smoke_count": 2,
                "supported_variant_simc_smoke_count": 2,
                "failureCodes": [],
                "failureSamples": [],
                "ledger": {
                    "browse-a": first,
                    "browse-b": second,
                },
                "gearCatalogRevision": identity["gearCatalogRevision"],
                "gearExactRegistryRevision": identity["gearExactRegistryRevision"],
                "simcRuntimeRevision": identity["simcRuntimeRevision"],
            }

        simc_executor = SimcExecutor(
            {
                "ran": True,
                "timedOut": False,
                "hasDps": True,
                "durationMs": 4.0,
                "executionMode": "real",
                "simcRuntimeRevision": identity["simcRuntimeRevision"],
                "iterations": 1,
                "maxTimeSeconds": 5,
            }
        )

        report = run_catalog_candidate_evidence(
            load_catalog=lambda: self.catalog(),
            load_exact_registry=lambda: self.exact_registry(),
            request_json=request_json,
            profile_context_factory=profile_factory,
            simc_executor=simc_executor,
            pointer_reader=pointer_reader,
            run_catalog_http_matrix=run_http_matrix,
            build_materialization_runner=build_materialization_runner,
            build_materialization_matrix=build_materialization_matrix,
            run_simc_execution_matrix=run_simc_matrix,
            build_variant_simc_matrix=build_variant_simc_matrix,
            assemble_evidence=assemble_catalog_candidate_evidence,
            expected_specs=self.expected_specs_40(),
            expected_identity=identity,
            observed_at="2026-08-10T00:00:00+00:00",
        )

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["componentEvidence"]["catalog_http_report"]["status"], "pass")
        self.assertEqual(len(report["componentEvidence"]["catalog_gate_counts"]["relationContexts"]), 2)
        self.assertEqual(len(http_calls), 40 * 16)
        self.assertEqual(len(materializer_calls), 2)
        self.assertEqual(pointer_reader.calls, 2)
        self.assertEqual(report["pointerBefore"], old_active_pointer)
        self.assertEqual(report["pointerAfter"], old_active_pointer)
        self.assertEqual(len(profile_factory.calls), 40)
        self.assertIs(matrix_specs["http"], matrix_specs["simc"])
        self.assertNotIn("player=Candidate", json.dumps(report, ensure_ascii=False, sort_keys=True))

    def test_variant_smoke_blocks_on_simc_runtime_revision_mismatch(self):
        self.assertIsNotNone(_build_variant_smoke_callback)
        self.assertIsNotNone(build_gear_variant_simc_matrix)

        identity = self.expected_identity()
        context = {
            "browseVariantKey": "browse-a",
            "itemId": "1001",
            "classKey": "mage",
            "specKey": "frost",
            "slot": "head",
            "selectionIntent": {
                "schemaRevision": "selection-intent-v1",
                "authoredAgainst": {
                    "seasonRevision": "season-r1",
                    "gearCatalogRevision": identity["gearCatalogRevision"],
                },
                "eligibilityContext": {
                    "classKey": "mage",
                    "specKey": "frost",
                    "level": 80,
                },
                "slots": {
                    "head": {
                        "itemId": "1001",
                        "variantKey": "browse-a",
                    }
                },
            },
        }
        callback = _build_variant_smoke_callback(
            request_json=RequestJson(identity),
            simc_executor=SimcExecutor(
                {
                    "status": "verified",
                    "ran": True,
                    "timedOut": False,
                    "hasDps": True,
                    "executionMode": "real",
                    "simcRuntimeRevision": "simc:wrong",
                    "iterations": 1,
                    "maxTimeSeconds": 5,
                }
            ),
            relation_contexts=[context],
            get_profile_context=lambda _class_key, _spec_key: {
                "classKey": "mage",
                "specKey": "frost",
                "race": "human",
                "scenarioKey": "single",
                "talents": "TALENTS",
                "level": 80,
            },
            expected_identity=identity,
        )

        smoke = callback(
            item_id="1001",
            browse_variant_key="browse-a",
            class_key="mage",
            spec_key="frost",
            slot="head",
        )
        materialization = self.supported_materialization_report()
        materialization["ledger"]["browse-a"].update(
            {
                "classKey": "mage",
                "specKey": "frost",
                "slot": "head",
                "materializedItemId": "1001",
                "materializedBrowseVariantKey": "browse-a",
            }
        )
        variant_report = build_gear_variant_simc_matrix(materialization, callback)

        self.assertEqual(smoke["status"], "blocked")
        self.assertIn(
            "CATALOG_CANDIDATE_EVIDENCE_VARIANT_SIMC_RUNTIME_REVISION_MISMATCH",
            smoke["failureCodes"],
        )
        self.assertEqual(
            variant_report["ledger"]["browse-a"]["simcRuntimeRevision"],
            "simc:wrong",
        )
        self.assertIn(
            "CATALOG_CANDIDATE_EVIDENCE_VARIANT_SIMC_RUNTIME_REVISION_MISMATCH",
            variant_report["ledger"]["browse-a"]["failureCodes"],
        )

    def test_expected_specs_must_be_40_unique_non_empty_before_execution(self):
        self.assertIsNotNone(run_catalog_candidate_evidence)

        identity = self.expected_identity()
        valid_specs = self.expected_specs_40()
        cases = {
            "missing": valid_specs[:-1],
            "duplicate": valid_specs + [valid_specs[0]],
            "empty": [("", spec_key) for _class_key, spec_key in valid_specs],
        }
        for name, specs in cases.items():
            with self.subTest(name=name):
                loader_calls = []
                http_calls = []
                report = run_catalog_candidate_evidence(
                    load_catalog=lambda: loader_calls.append("catalog") or self.catalog(),
                    load_exact_registry=lambda: loader_calls.append("exact") or self.exact_registry(),
                    request_json=RequestJson(identity),
                    profile_context_factory=RecordingFactory({"level": 80}),
                    simc_executor=SimcExecutor({}),
                    pointer_reader=PointerReader([self.pointer(), self.pointer()]),
                    run_catalog_http_matrix=lambda *_args, **_kwargs: http_calls.append(True),
                    build_materialization_runner=lambda **_kwargs: (_ for _ in ()).throw(
                        AssertionError("materialization runner must not be built")
                    ),
                    build_materialization_matrix=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                        AssertionError("materialization matrix must not run")
                    ),
                    run_simc_execution_matrix=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                        AssertionError("26/14 matrix must not run")
                    ),
                    build_variant_simc_matrix=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                        AssertionError("variant SimC matrix must not run")
                    ),
                    assemble_evidence=lambda **_kwargs: (_ for _ in ()).throw(
                        AssertionError("assembly must not run")
                    ),
                    expected_specs=specs,
                    expected_identity=identity,
                    observed_at="2026-08-10T00:00:00+00:00",
                )
                self.assertEqual(report["status"], "blocked")
                self.assertEqual(loader_calls, [])
                self.assertEqual(http_calls, [])
                self.assertTrue(
                    any(
                        problem["code"].startswith(
                            "CATALOG_CANDIDATE_EVIDENCE_EXPECTED_SPECS_"
                        )
                        for problem in report["problems"]
                    )
                )

    def test_loader_exception_returns_stable_blocked_report(self):
        self.assertIsNotNone(run_catalog_candidate_evidence)

        identity = self.expected_identity()
        pointer_reader = PointerReader([self.pointer(), self.pointer()])
        report = run_catalog_candidate_evidence(
            load_catalog=lambda: (_ for _ in ()).throw(OSError("database unavailable")),
            load_exact_registry=lambda: self.exact_registry(),
            request_json=RequestJson(identity),
            profile_context_factory=RecordingFactory({"level": 80}),
            simc_executor=SimcExecutor({}),
            pointer_reader=pointer_reader,
            expected_specs=self.expected_specs_40(),
            expected_identity=identity,
            observed_at="2026-08-10T00:00:00+00:00",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(
            report["problems"][0]["code"],
            "CATALOG_CANDIDATE_EVIDENCE_CATALOG_LOADER_EXCEPTION",
        )
        self.assertEqual(report["pointerBefore"], self.pointer())
        self.assertEqual(report["pointerAfter"], self.pointer())
        self.assertEqual(
            report["componentEvidence"]["catalog"]["failureCodes"],
            ["CATALOG_CANDIDATE_EVIDENCE_CATALOG_LOADER_EXCEPTION"],
        )

    def test_matrix_exception_returns_stable_blocked_report(self):
        self.assertIsNotNone(run_catalog_candidate_evidence)

        identity = self.expected_identity()
        report = run_catalog_candidate_evidence(
            load_catalog=lambda: self.catalog(),
            load_exact_registry=lambda: self.exact_registry(),
            request_json=RequestJson(identity),
            profile_context_factory=RecordingFactory({"level": 80}),
            simc_executor=SimcExecutor({}),
            pointer_reader=PointerReader([self.pointer(), self.pointer()]),
            run_catalog_http_matrix=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("candidate network unavailable")
            ),
            expected_specs=self.expected_specs_40(),
            expected_identity=identity,
            observed_at="2026-08-10T00:00:00+00:00",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(
            report["problems"][0]["code"],
            "CATALOG_CANDIDATE_EVIDENCE_HTTP_MATRIX_EXCEPTION",
        )
        self.assertEqual(report["pointerBefore"], report["pointerAfter"])
        self.assertEqual(
            report["componentEvidence"]["catalog_http_report"]["failureCodes"],
            ["CATALOG_CANDIDATE_EVIDENCE_HTTP_MATRIX_EXCEPTION"],
        )

    def test_profile_context_exception_returns_stable_blocked_report(self):
        self.assertIsNotNone(run_catalog_candidate_evidence)

        identity = self.expected_identity()
        request_json = RequestJson(
            identity,
            payload_builder=lambda class_key, spec_key, slot: self.slot_payload(
                identity, class_key, spec_key, slot
            ),
        )

        def run_http_matrix(recording_request_json, **_kwargs):
            recording_request_json(
                "GET",
                "/api/websim/gear?class=mage&spec=frost&compact=1&mode=slot&slot=head",
                None,
                {},
            )
            return {
                "schemaRevision": "gear-catalog-http-completeness-matrix-v2",
                "status": "pass",
                "failureCount": 0,
                "failureCodes": {},
            }

        report = run_catalog_candidate_evidence(
            load_catalog=lambda: self.catalog(
                itemDefinitions=[{"itemId": "1001", "slot": "head"}],
                browseVariants=[{"browseVariantKey": "browse-a", "itemId": "1001"}],
            ),
            load_exact_registry=lambda: self.exact_registry(),
            request_json=request_json,
            profile_context_factory=lambda **_kwargs: (_ for _ in ()).throw(
                RuntimeError("profile context unavailable")
            ),
            simc_executor=SimcExecutor({}),
            pointer_reader=PointerReader([self.pointer(), self.pointer()]),
            run_catalog_http_matrix=run_http_matrix,
            expected_specs=self.expected_specs_40(),
            expected_identity=identity,
            observed_at="2026-08-10T00:00:00+00:00",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(
            report["problems"][0]["code"],
            "CATALOG_CANDIDATE_EVIDENCE_PROFILE_CONTEXT_FACTORY_EXCEPTION",
        )
        self.assertEqual(report["pointerBefore"], report["pointerAfter"])

    def test_cli_loader_exception_writes_blocked_json_without_bubbling(self):
        module = _load_cli_module()
        self.assertIsNotNone(module)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report.json"
            identity = self.expected_identity()
            exit_code = module.main(
                [
                    "--base-url",
                    "http://127.0.0.1",
                    "--manifest-revision",
                    identity["manifestRevision"],
                    "--pointer-generation",
                    str(identity["pointerGeneration"]),
                    "--gear-release-id",
                    identity["gearReleaseId"],
                    "--community-release-id",
                    identity["communityReleaseId"],
                    "--gear-catalog-revision",
                    identity["gearCatalogRevision"],
                    "--gear-exact-registry-revision",
                    identity["gearExactRegistryRevision"],
                    "--simc-runtime-revision",
                    identity["simcRuntimeRevision"],
                    "--simc-bin",
                    "/bin/true",
                    "--output",
                    str(output),
                ],
                load_catalog_fn=lambda _args: (_ for _ in ()).throw(
                    OSError("database unavailable")
                ),
                load_exact_registry_fn=lambda _args: self.exact_registry(),
                pointer_reader_fn=lambda _args: self.pointer(),
            )

            self.assertEqual(exit_code, 2)
            written = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(written["status"], "blocked")
            self.assertEqual(
                written["problems"][0]["code"],
                "CATALOG_CANDIDATE_EVIDENCE_CATALOG_LOADER_EXCEPTION",
            )

    def test_cli_rejects_untrusted_report_file_overrides(self):
        module = _load_cli_module()
        self.assertIsNotNone(module)

        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                module._parser().parse_args(["--catalog-report", "/tmp/untrusted.json"])

    def test_cli_request_network_error_returns_blocked_payload_without_bubbling(self):
        module = _load_cli_module()
        self.assertIsNotNone(module)
        args = module._parser().parse_args(
            [
                "--base-url",
                "http://127.0.0.1",
                "--manifest-revision",
                "manifest:sha256:" + "1" * 64,
                "--pointer-generation",
                "35",
                "--gear-release-id",
                "gear-release:sha256:" + "5" * 64,
                "--community-release-id",
                "community-release:sha256:" + "6" * 64,
                "--gear-catalog-revision",
                "gear-catalog:sha256:" + "2" * 64,
                "--gear-exact-registry-revision",
                "gear-exact-registry:sha256:" + "3" * 64,
                "--simc-runtime-revision",
                "simc:" + "4" * 40,
                "--simc-bin",
                "/bin/true",
                "--output",
                "/tmp/candidate-evidence.json",
            ]
        )
        request_json = module._request_json_builder(args)
        with patch.object(module, "urlopen", side_effect=URLError("offline")):
            status, payload, _duration_ms = request_json(
                "GET",
                "/api/websim/gear?class=mage&spec=frost",
                None,
                {},
            )

        self.assertEqual(status, 0)
        self.assertEqual(
            payload["failureCodes"],
            ["CATALOG_CANDIDATE_EVIDENCE_NETWORK_EXCEPTION"],
        )

    def test_variant_smoke_posts_exact_intent_and_uses_real_short_executor_fields(self):
        self.assertIsNotNone(run_catalog_candidate_evidence)
        self.assertIsNotNone(build_gear_variant_simc_matrix)

        identity = self.expected_identity()
        request_json = RequestJson(identity)
        profile_factory = RecordingFactory(
            {
                "classKey": "mage",
                "specKey": "frost",
                "race": "human",
                "scenarioKey": "single",
                "talents": "TALENTS",
                "level": 80,
            }
        )
        simc_executor = SimcExecutor(
            {
                "ran": True,
                "timedOut": False,
                "hasDps": True,
                "durationMs": 2.0,
                "executionMode": "real",
                "simcRuntimeRevision": identity["simcRuntimeRevision"],
                "iterations": 1,
                "maxTimeSeconds": 5,
            }
        )

        def run_http_matrix(_request_json, **_kwargs):
            return {
                "schemaRevision": "gear-catalog-http-completeness-matrix-v2",
                "status": "pass",
                "bindingMode": "candidate_preview",
                "manifestRevision": identity["manifestRevision"],
                "pointerGeneration": identity["pointerGeneration"],
                "gearReleaseId": identity["gearReleaseId"],
                "communityReleaseId": identity["communityReleaseId"],
                "catalogRevision": identity["gearCatalogRevision"],
                "exactRegistryRevision": identity["gearExactRegistryRevision"],
                "failureCount": 0,
                "failureCodes": {},
                "failureSamples": [],
            }

        def build_materialization_runner(**_kwargs):
            return lambda **_ignored: {
                "status": "verified",
                "materializedItemId": "1001",
                "materializedBrowseVariantKey": "browse-a",
                "resolverStatus": "resolved",
                "profileStatus": "resolved",
                "simcReady": True,
                "usedDefaultVariant": False,
                "failureCodes": [],
            }

        def build_materialization_matrix(_catalog, relation_contexts, materializer):
            row = relation_contexts[0]
            materializer(
                item_id=row["itemId"],
                browse_variant_key=row["browseVariantKey"],
                class_key=row["classKey"],
                spec_key=row["specKey"],
                slot=row["slot"],
                selection_intent=row["selectionIntent"],
            )
            return self.supported_materialization_report()

        def run_simc_matrix(_request_json, _simc_executor, **_kwargs):
            return self.simc_26_14_report()

        report = run_catalog_candidate_evidence(
            load_catalog=lambda: self.catalog(
                itemDefinitions=[{"itemId": "1001", "slot": "head"}],
                browseVariants=[{"browseVariantKey": "browse-a", "itemId": "1001"}],
            ),
            load_exact_registry=lambda: self.exact_registry(),
            request_json=request_json,
            profile_context_factory=profile_factory,
            simc_executor=simc_executor,
            pointer_reader=PointerReader([self.pointer(), self.pointer()]),
            run_catalog_http_matrix=run_http_matrix,
            build_materialization_runner=build_materialization_runner,
            build_materialization_matrix=build_materialization_matrix,
            run_simc_execution_matrix=run_simc_matrix,
            build_variant_simc_matrix=build_gear_variant_simc_matrix,
            assemble_evidence=assemble_catalog_candidate_evidence,
            expected_specs=self.expected_specs_40(),
            observed_relation_contexts=[
                {
                    "browseVariantKey": "browse-a",
                    "itemId": "1001",
                    "classKey": "mage",
                    "specKey": "frost",
                    "slot": "head",
                    "selectionIntent": {
                        "schemaRevision": "selection-intent-v1",
                        "authoredAgainst": {
                            "seasonRevision": "season-r1",
                            "gearCatalogRevision": identity["gearCatalogRevision"],
                        },
                        "eligibilityContext": {
                            "classKey": "mage",
                            "specKey": "frost",
                            "level": 80,
                        },
                        "slots": {
                            "head": {
                                "itemId": "1001",
                                "variantKey": "browse-a",
                            }
                        },
                    },
                }
            ],
            expected_identity=identity,
            observed_at="2026-08-10T00:00:00+00:00",
        )

        self.assertEqual(report["status"], "verified")
        profile_posts = [
            call for call in request_json.calls if call["method"] == "POST" and call["path"] == "/api/websim/profile"
        ]
        self.assertEqual(len(profile_posts), 1)
        self.assertEqual(
            profile_posts[0]["payload"],
            {
                "selectionIntent": {
                    "schemaRevision": "selection-intent-v1",
                    "authoredAgainst": {
                        "seasonRevision": "season-r1",
                        "gearCatalogRevision": identity["gearCatalogRevision"],
                    },
                    "eligibilityContext": {
                        "classKey": "mage",
                        "specKey": "frost",
                        "level": 80,
                    },
                    "slots": {
                        "head": {
                            "itemId": "1001",
                            "variantKey": "browse-a",
                        }
                    },
                },
                "profileContext": {
                    "classKey": "mage",
                    "specKey": "frost",
                    "race": "human",
                    "scenarioKey": "single",
                    "talents": "TALENTS",
                    "level": 80,
                },
            },
        )
        self.assertEqual(simc_executor.calls, ["player=Candidate\nclass=mage"])
        ledger = report["componentEvidence"]["variant_simc_report"]["ledger"]["browse-a"]
        self.assertEqual(ledger["executionMode"], "real")
        self.assertEqual(ledger["iterations"], 1)
        self.assertEqual(ledger["maxTimeSeconds"], 5)

    def test_missing_relation_context_blocks_and_never_executes_variant_smoke(self):
        self.assertIsNotNone(run_catalog_candidate_evidence)
        self.assertIsNotNone(build_gear_variant_materialization_matrix)
        self.assertIsNotNone(build_gear_variant_simc_matrix)

        identity = self.expected_identity()
        simc_executor = SimcExecutor(
            {
                "ran": True,
                "timedOut": False,
                "hasDps": True,
                "durationMs": 2.0,
                "executionMode": "real",
                "simcRuntimeRevision": identity["simcRuntimeRevision"],
                "iterations": 1,
                "maxTimeSeconds": 5,
            }
        )

        report = run_catalog_candidate_evidence(
            load_catalog=lambda: self.catalog(),
            load_exact_registry=lambda: self.exact_registry(),
            request_json=RequestJson(identity),
            profile_context_factory=RecordingFactory(
                {
                    "classKey": "mage",
                    "specKey": "frost",
                    "race": "human",
                    "scenarioKey": "single",
                    "talents": "TALENTS",
                    "level": 80,
                }
            ),
            simc_executor=simc_executor,
            pointer_reader=PointerReader([self.pointer(), self.pointer()]),
            run_catalog_http_matrix=lambda _request_json, **_kwargs: {
                "schemaRevision": "gear-catalog-http-completeness-matrix-v2",
                "status": "pass",
                "bindingMode": "candidate_preview",
                "manifestRevision": identity["manifestRevision"],
                "pointerGeneration": identity["pointerGeneration"],
                "gearReleaseId": identity["gearReleaseId"],
                "communityReleaseId": identity["communityReleaseId"],
                "catalogRevision": identity["gearCatalogRevision"],
                "exactRegistryRevision": identity["gearExactRegistryRevision"],
                "failureCount": 0,
                "failureCodes": {},
                "failureSamples": [],
            },
            build_materialization_runner=lambda **_kwargs: (
                lambda **kwargs: {
                    "status": "verified",
                    "materializedItemId": kwargs["item_id"],
                    "materializedBrowseVariantKey": kwargs["browse_variant_key"],
                    "resolverStatus": "resolved",
                    "profileStatus": "resolved",
                    "simcReady": True,
                    "usedDefaultVariant": False,
                    "failureCodes": [],
                }
            ),
            build_materialization_matrix=build_gear_variant_materialization_matrix,
            run_simc_execution_matrix=lambda _request_json, _simc_executor, **_kwargs: self.simc_26_14_report(),
            build_variant_simc_matrix=build_gear_variant_simc_matrix,
            assemble_evidence=assemble_catalog_candidate_evidence,
            expected_specs=self.expected_specs_40(),
            observed_relation_contexts=[
                {
                    "browseVariantKey": "browse-a",
                    "itemId": "1001",
                    "classKey": "mage",
                    "specKey": "frost",
                    "slot": "head",
                    "selectionIntent": {
                        "schemaRevision": "selection-intent-v1",
                        "authoredAgainst": {
                            "seasonRevision": "season-r1",
                            "gearCatalogRevision": identity["gearCatalogRevision"],
                        },
                        "eligibilityContext": {
                            "classKey": "mage",
                            "specKey": "frost",
                            "level": 80,
                        },
                        "slots": {
                            "head": {
                                "itemId": "1001",
                                "variantKey": "browse-a",
                            }
                        },
                    },
                }
            ],
            expected_identity=identity,
            observed_at="2026-08-10T00:00:00+00:00",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "MATERIALIZATION_MATRIX_MISSING_RELATION_CONTEXT",
            report["componentEvidence"]["materialization_report"]["failureCodes"],
        )
        self.assertEqual(simc_executor.calls, [])

    def test_identity_mismatch_stops_before_http_matrix(self):
        self.assertIsNotNone(run_catalog_candidate_evidence)

        identity = self.expected_identity()
        http_matrix_calls = []

        report = run_catalog_candidate_evidence(
            load_catalog=lambda: self.catalog(catalogRevision="gear-catalog:sha256:wrong"),
            load_exact_registry=lambda: self.exact_registry(),
            request_json=RequestJson(identity),
            profile_context_factory=RecordingFactory({"level": 80}),
            simc_executor=SimcExecutor({}),
            pointer_reader=PointerReader([self.pointer()]),
            run_catalog_http_matrix=lambda *_args, **_kwargs: http_matrix_calls.append(True),
            build_materialization_runner=lambda **_kwargs: None,
            build_materialization_matrix=lambda *_args, **_kwargs: {},
            run_simc_execution_matrix=lambda *_args, **_kwargs: {},
            build_variant_simc_matrix=lambda *_args, **_kwargs: {},
            assemble_evidence=lambda **_kwargs: {},
            expected_specs=self.expected_specs_40(),
            expected_identity=identity,
            observed_at="2026-08-10T00:00:00+00:00",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(http_matrix_calls, [])
        self.assertEqual(
            report["problems"][0]["code"],
            "CATALOG_CANDIDATE_EVIDENCE_INPUT_IDENTITY_MISMATCH",
        )

    def test_pointer_drift_is_reported_by_final_assembly(self):
        self.assertIsNotNone(run_catalog_candidate_evidence)

        identity = self.expected_identity()

        report = run_catalog_candidate_evidence(
            load_catalog=lambda: self.catalog(
                itemDefinitions=[{"itemId": "1001", "slot": "head"}],
                browseVariants=[{"browseVariantKey": "browse-a", "itemId": "1001"}],
            ),
            load_exact_registry=lambda: self.exact_registry(),
            request_json=RequestJson(identity),
            profile_context_factory=RecordingFactory(
                {
                    "classKey": "mage",
                    "specKey": "frost",
                    "race": "human",
                    "scenarioKey": "single",
                    "talents": "TALENTS",
                    "level": 80,
                }
            ),
            simc_executor=SimcExecutor(
                {
                    "ran": True,
                    "timedOut": False,
                    "hasDps": True,
                    "durationMs": 2.0,
                    "executionMode": "real",
                    "simcRuntimeRevision": identity["simcRuntimeRevision"],
                    "iterations": 1,
                    "maxTimeSeconds": 5,
                }
            ),
            pointer_reader=PointerReader(
                [self.pointer(), self.pointer(manifestRevision="manifest:sha256:" + "9" * 64)]
            ),
            run_catalog_http_matrix=lambda _request_json, **_kwargs: {
                "schemaRevision": "gear-catalog-http-completeness-matrix-v2",
                "status": "pass",
                "bindingMode": "candidate_preview",
                "manifestRevision": identity["manifestRevision"],
                "pointerGeneration": identity["pointerGeneration"],
                "gearReleaseId": identity["gearReleaseId"],
                "communityReleaseId": identity["communityReleaseId"],
                "catalogRevision": identity["gearCatalogRevision"],
                "exactRegistryRevision": identity["gearExactRegistryRevision"],
                "failureCount": 0,
                "failureCodes": {},
                "failureSamples": [],
            },
            build_materialization_runner=lambda **_kwargs: (
                lambda **kwargs: {
                    "status": "verified",
                    "materializedItemId": kwargs["item_id"],
                    "materializedBrowseVariantKey": kwargs["browse_variant_key"],
                    "resolverStatus": "resolved",
                    "profileStatus": "resolved",
                    "simcReady": True,
                    "usedDefaultVariant": False,
                    "failureCodes": [],
                }
            ),
            build_materialization_matrix=lambda *_args, **_kwargs: self.supported_materialization_report(),
            run_simc_execution_matrix=lambda _request_json, _simc_executor, **_kwargs: self.simc_26_14_report(),
            build_variant_simc_matrix=lambda *_args, **_kwargs: {
                "schemaRevision": "gear-variant-simc-matrix-v1",
                "status": "verified",
                "expected_supported_variant_smoke_count": 1,
                "passed_supported_variant_smoke_count": 1,
                "supported_variant_simc_smoke_count": 1,
                "failureCodes": [],
                "failureSamples": [],
                "ledger": {
                    "browse-a": {
                        "status": "verified",
                        "itemId": "1001",
                        "browseVariantKey": "browse-a",
                        "classKey": "mage",
                        "specKey": "frost",
                        "slot": "head",
                        "ran": True,
                        "timedOut": False,
                        "hasDps": True,
                        "executionMode": "real",
                        "simcRuntimeRevision": identity["simcRuntimeRevision"],
                        "iterations": 1,
                        "maxTimeSeconds": 5,
                    }
                },
                "gearCatalogRevision": identity["gearCatalogRevision"],
                "gearExactRegistryRevision": identity["gearExactRegistryRevision"],
                "simcRuntimeRevision": identity["simcRuntimeRevision"],
            },
            assemble_evidence=assemble_catalog_candidate_evidence,
            expected_specs=self.expected_specs_40(),
            observed_relation_contexts=[
                {
                    "browseVariantKey": "browse-a",
                    "itemId": "1001",
                    "classKey": "mage",
                    "specKey": "frost",
                    "slot": "head",
                    "selectionIntent": {
                        "schemaRevision": "selection-intent-v1",
                        "authoredAgainst": {
                            "seasonRevision": "season-r1",
                            "gearCatalogRevision": identity["gearCatalogRevision"],
                        },
                        "eligibilityContext": {
                            "classKey": "mage",
                            "specKey": "frost",
                            "level": 80,
                        },
                        "slots": {
                            "head": {
                                "itemId": "1001",
                                "variantKey": "browse-a",
                            }
                        },
                    },
                }
            ],
            expected_identity=identity,
            observed_at="2026-08-10T00:00:00+00:00",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["pointerStable"])
        self.assertEqual(report["problems"][-1]["code"], "CANDIDATE_EVIDENCE_POINTER_DRIFT")

    def test_unsupported_variant_never_invokes_executor(self):
        self.assertIsNotNone(run_catalog_candidate_evidence)
        self.assertIsNotNone(build_gear_variant_simc_matrix)

        identity = self.expected_identity()
        simc_executor = SimcExecutor(
            {
                "ran": True,
                "timedOut": False,
                "hasDps": True,
                "durationMs": 2.0,
                "executionMode": "real",
                "simcRuntimeRevision": identity["simcRuntimeRevision"],
                "iterations": 1,
                "maxTimeSeconds": 5,
            }
        )

        report = run_catalog_candidate_evidence(
            load_catalog=lambda: self.catalog(
                itemDefinitions=[{"itemId": "1001", "slot": "head"}],
                browseVariants=[{"browseVariantKey": "browse-a", "itemId": "1001"}],
            ),
            load_exact_registry=lambda: self.exact_registry(),
            request_json=RequestJson(identity),
            profile_context_factory=RecordingFactory(
                {
                    "classKey": "paladin",
                    "specKey": "holy",
                    "race": "human",
                    "scenarioKey": "single",
                    "talents": "TALENTS",
                    "level": 80,
                }
            ),
            simc_executor=simc_executor,
            pointer_reader=PointerReader([self.pointer(), self.pointer()]),
            run_catalog_http_matrix=lambda _request_json, **_kwargs: {
                "schemaRevision": "gear-catalog-http-completeness-matrix-v2",
                "status": "pass",
                "bindingMode": "candidate_preview",
                "manifestRevision": identity["manifestRevision"],
                "pointerGeneration": identity["pointerGeneration"],
                "gearReleaseId": identity["gearReleaseId"],
                "communityReleaseId": identity["communityReleaseId"],
                "catalogRevision": identity["gearCatalogRevision"],
                "exactRegistryRevision": identity["gearExactRegistryRevision"],
                "failureCount": 0,
                "failureCodes": {},
                "failureSamples": [],
            },
            build_materialization_runner=lambda **_kwargs: (
                lambda **kwargs: {
                    "status": "verified",
                    "materializedItemId": kwargs["item_id"],
                    "materializedBrowseVariantKey": kwargs["browse_variant_key"],
                    "resolverStatus": "resolved",
                    "profileStatus": "resolved",
                    "simcReady": True,
                    "usedDefaultVariant": False,
                    "failureCodes": [],
                }
            ),
            build_materialization_matrix=lambda *_args, **_kwargs: {
                "schemaRevision": "gear-variant-materialization-matrix-v1",
                "status": "verified",
                "expected_unique_variant_count": 1,
                "materialized_unique_variant_count": 1,
                "unique_variant_materialization_count": 1,
                "catalog_non_simulatable_count": 0,
                "silent_default_fill_count": 0,
                "missing_provenance_count": 0,
                "failureCodes": [],
                "failureSamples": [],
                "ledger": {
                    "browse-a": {
                        "status": "verified",
                        "itemId": "1001",
                        "classKey": "paladin",
                        "specKey": "holy",
                        "slot": "head",
                        "materializedItemId": "1001",
                        "materializedBrowseVariantKey": "browse-a",
                        "failureCodes": [],
                    }
                },
            },
            run_simc_execution_matrix=lambda _request_json, _simc_executor, **_kwargs: self.simc_26_14_report(),
            build_variant_simc_matrix=build_gear_variant_simc_matrix,
            assemble_evidence=assemble_catalog_candidate_evidence,
            expected_specs=self.expected_specs_40(),
            observed_relation_contexts=[
                {
                    "browseVariantKey": "browse-a",
                    "itemId": "1001",
                    "classKey": "paladin",
                    "specKey": "holy",
                    "slot": "head",
                    "selectionIntent": {
                        "schemaRevision": "selection-intent-v1",
                        "authoredAgainst": {
                            "seasonRevision": "season-r1",
                            "gearCatalogRevision": identity["gearCatalogRevision"],
                        },
                        "eligibilityContext": {
                            "classKey": "paladin",
                            "specKey": "holy",
                            "level": 80,
                        },
                        "slots": {
                            "head": {
                                "itemId": "1001",
                                "variantKey": "browse-a",
                            }
                        },
                    },
                }
            ],
            expected_identity=identity,
            observed_at="2026-08-10T00:00:00+00:00",
        )

        self.assertEqual(report["status"], "verified")
        self.assertEqual(simc_executor.calls, [])
        ledger = report["componentEvidence"]["variant_simc_report"]["ledger"]["browse-a"]
        self.assertEqual(ledger["status"], "blocked")
        self.assertFalse(ledger["smokeInvoked"])

    def test_literal_partial_and_pending_statuses_are_preserved_in_reports(self):
        self.assertIsNotNone(run_catalog_candidate_evidence)

        identity = self.expected_identity()

        report = run_catalog_candidate_evidence(
            load_catalog=lambda: self.catalog(
                itemDefinitions=[{"itemId": "1001", "slot": "head"}],
                browseVariants=[{"browseVariantKey": "browse-a", "itemId": "1001"}],
            ),
            load_exact_registry=lambda: self.exact_registry(
                status="partial",
                problemCodes=["ENHANCEMENT_SINGLE_VALUE_MALFORMED"],
                templateReferences=[
                    {
                        "validationStatus": "partial",
                        "exactItemInstanceKey": "",
                        "problemCodes": ["ENHANCEMENT_SINGLE_VALUE_MALFORMED"],
                    }
                ],
            ),
            request_json=RequestJson(identity),
            profile_context_factory=RecordingFactory(
                {
                    "classKey": "mage",
                    "specKey": "frost",
                    "race": "human",
                    "scenarioKey": "single",
                    "talents": "TALENTS",
                    "level": 80,
                }
            ),
            simc_executor=SimcExecutor(
                {
                    "ran": True,
                    "timedOut": False,
                    "hasDps": True,
                    "durationMs": 2.0,
                    "executionMode": "real",
                    "simcRuntimeRevision": identity["simcRuntimeRevision"],
                    "iterations": 1,
                    "maxTimeSeconds": 5,
                }
            ),
            pointer_reader=PointerReader([self.pointer(), self.pointer()]),
            run_catalog_http_matrix=lambda _request_json, **_kwargs: {
                "schemaRevision": "gear-catalog-http-completeness-matrix-v2",
                "status": "pass",
                "bindingMode": "candidate_preview",
                "manifestRevision": identity["manifestRevision"],
                "pointerGeneration": identity["pointerGeneration"],
                "gearReleaseId": identity["gearReleaseId"],
                "communityReleaseId": identity["communityReleaseId"],
                "catalogRevision": identity["gearCatalogRevision"],
                "exactRegistryRevision": identity["gearExactRegistryRevision"],
                "failureCount": 0,
                "failureCodes": {},
                "failureSamples": [],
            },
            build_materialization_runner=lambda **_kwargs: (
                lambda **kwargs: {
                    "status": "pending",
                    "materializedItemId": kwargs["item_id"],
                    "materializedBrowseVariantKey": kwargs["browse_variant_key"],
                    "resolverStatus": "pending",
                    "profileStatus": "",
                    "simcReady": None,
                    "usedDefaultVariant": False,
                    "failureCodes": ["MATERIALIZATION_RUNNER_PROFILE_STATUS_NOT_READY"],
                }
            ),
            build_materialization_matrix=lambda *_args, **_kwargs: {
                "schemaRevision": "gear-variant-materialization-matrix-v1",
                "status": "pending",
                "expected_unique_variant_count": 1,
                "materialized_unique_variant_count": 0,
                "unique_variant_materialization_count": 0,
                "catalog_non_simulatable_count": 1,
                "silent_default_fill_count": 0,
                "missing_provenance_count": 0,
                "failureCodes": ["MATERIALIZATION_RUNNER_PROFILE_STATUS_NOT_READY"],
                "failureSamples": [],
                "ledger": {
                    "browse-a": {
                        "status": "pending",
                        "itemId": "1001",
                        "classKey": "mage",
                        "specKey": "frost",
                        "slot": "head",
                        "materializedItemId": "1001",
                        "materializedBrowseVariantKey": "browse-a",
                        "failureCodes": ["MATERIALIZATION_RUNNER_PROFILE_STATUS_NOT_READY"],
                    }
                },
            },
            run_simc_execution_matrix=lambda _request_json, _simc_executor, **_kwargs: self.simc_26_14_report(),
            build_variant_simc_matrix=lambda *_args, **_kwargs: {
                "schemaRevision": "gear-variant-simc-matrix-v1",
                "status": "blocked",
                "expected_supported_variant_smoke_count": 1,
                "passed_supported_variant_smoke_count": 0,
                "supported_variant_simc_smoke_count": 0,
                "failureCodes": ["GEAR_VARIANT_SIMC_MATERIALIZATION_NOT_READY"],
                "failureSamples": [],
                "ledger": {},
                "gearCatalogRevision": identity["gearCatalogRevision"],
                "gearExactRegistryRevision": identity["gearExactRegistryRevision"],
                "simcRuntimeRevision": identity["simcRuntimeRevision"],
            },
            assemble_evidence=assemble_catalog_candidate_evidence,
            expected_specs=self.expected_specs_40(),
            observed_relation_contexts=[
                {
                    "browseVariantKey": "browse-a",
                    "itemId": "1001",
                    "classKey": "mage",
                    "specKey": "frost",
                    "slot": "head",
                    "selectionIntent": {
                        "schemaRevision": "selection-intent-v1",
                        "authoredAgainst": {
                            "seasonRevision": "season-r1",
                            "gearCatalogRevision": identity["gearCatalogRevision"],
                        },
                        "eligibilityContext": {
                            "classKey": "mage",
                            "specKey": "frost",
                            "level": 80,
                        },
                        "slots": {
                            "head": {
                                "itemId": "1001",
                                "variantKey": "browse-a",
                            }
                        },
                    },
                }
            ],
            expected_identity=identity,
            observed_at="2026-08-10T00:00:00+00:00",
        )

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["componentStatuses"]["materialization_report"], "pending")
        self.assertEqual(report["componentStatuses"]["exact_registry_report"], "partial")
        self.assertEqual(report["componentEvidence"]["variant_simc_report"]["status"], "blocked")

    def test_cli_writes_json_and_exits_nonzero_unless_verified(self):
        module = _load_cli_module()
        self.assertIsNotNone(module)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report.json"
            exit_code = module.main(
                [
                    "--base-url",
                    "http://127.0.0.1",
                    "--manifest-revision",
                    "manifest:sha256:" + "1" * 64,
                    "--pointer-generation",
                    "35",
                    "--gear-release-id",
                    "gear-release:sha256:" + "5" * 64,
                    "--community-release-id",
                    "community-release:sha256:" + "6" * 64,
                    "--gear-catalog-revision",
                    "gear-catalog:sha256:" + "2" * 64,
                    "--gear-exact-registry-revision",
                    "gear-exact-registry:sha256:" + "3" * 64,
                    "--simc-runtime-revision",
                    "simc:" + "4" * 40,
                    "--simc-bin",
                    "/bin/true",
                    "--output",
                    str(output),
                ],
                load_catalog_fn=lambda _args: self.catalog(status="blocked"),
                load_exact_registry_fn=lambda _args: self.exact_registry(),
                pointer_reader_fn=lambda _args: self.pointer(),
                runner_fn=lambda **_kwargs: {"status": "blocked", "reportId": "runner:1"},
            )
            self.assertEqual(exit_code, 2)
            self.assertTrue(output.exists())
            written = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(written["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
