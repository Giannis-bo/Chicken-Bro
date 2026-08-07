import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from server.exact_simc_api import (
        AuthenticatedExactSourceMaterializer,
        AuthenticatedExactProfileMaterializer,
        ExactSimcMaterializer,
        ExactSimcApi,
        exact_simc_job_owner_key_hash_for_user_id,
    )
except ImportError:  # RED: the Task 5A owner does not exist yet.
    AuthenticatedExactSourceMaterializer = None
    AuthenticatedExactProfileMaterializer = None
    ExactSimcMaterializer = None
    ExactSimcApi = None
    exact_simc_job_owner_key_hash_for_user_id = None


def exact_dependency_vector():
    return {
        "seasonRevision": "season-1",
        "gameBuild": "12.0.1.12345",
        "gearRuleRevision": "gear-rule-v1",
        "resolverRevision": "resolver-v2",
        "compilerRevision": "compiler-v2",
        "workerRevision": "worker-v1",
        "simcRuntimeRevision": "simc:deadbeef",
        "effectAuthorityRevision": "effect-authority-v1",
    }


class CapturingJobStore:
    def __init__(self):
        self.enqueued = []

    def enqueue(self, owner_key_hash, request):
        self.enqueued.append((owner_key_hash, request))
        raise AssertionError("confirm must not enqueue an Exact SimC job")


class AcceptingJobStore:
    def __init__(self):
        self.enqueued = []

    def enqueue(self, owner_key_hash, request):
        self.enqueued.append((owner_key_hash, request))
        return {
            "jobId": 41,
            "requestKey": request.request_key,
            "status": "queued",
            "reused": False,
            "cooldownUntil": None,
        }


class ReadingJobStore:
    def __init__(self, rows_by_owner):
        self.rows_by_owner = rows_by_owner
        self.calls = []

    def read(self, owner_key_hash, job_id):
        self.calls.append((owner_key_hash, job_id))
        return self.rows_by_owner.get(owner_key_hash, {}).get(job_id)


class ExplodingJobStore:
    def enqueue(self, _owner_key_hash, _request):
        raise RuntimeError("private exact store outage")


class CapturingSourceReader:
    def __init__(self):
        self.calls = []

    def read(self, owner_id, template_id, **revisions):
        self.calls.append((owner_id, template_id, revisions))
        return {
            "status": "blocked",
            "problemCodes": ["LOADOUT_EFFECT_AUTHORITY_REQUIRED"],
            "problems": [{"code": "LOADOUT_EFFECT_AUTHORITY_REQUIRED"}],
        }


class VerifiedSourceReader(CapturingSourceReader):
    def read(self, owner_id, template_id, **revisions):
        self.calls.append((owner_id, template_id, revisions))
        return {
            "status": "verified",
            "source": object(),
            "binding": object(),
            "slotBundles": (),
            "problemCodes": [],
            "problems": [],
        }


class CapturingTalentStore:
    def __init__(self):
        self.calls = []

    def load_remote_talent_template_for_exact(self, owner_id, template_id):
        self.calls.append((owner_id, template_id))
        return {
            "ownerId": owner_id,
            "templateId": template_id,
            "templateType": "talent",
            "remote": True,
            "configHash": "a" * 64,
            "rawString": "talents=CAEAA",
            "simcLines": ["talents=CAEAA"],
            "classKey": "mage",
            "specKey": "frost",
            "heroKey": "spellslinger",
        }


class CapturingProfileCompiler:
    def __init__(self):
        self.calls = []

    def __call__(self, talent_source, execution_intent, gear_source):
        self.calls.append((talent_source, execution_intent, gear_source))
        return {
            "talentProfileKey": "talent-profile:sha256:" + "b" * 64,
            "talentLines": ["talents=CAEAA"],
            "characterContext": {
                "classKey": "mage",
                "specKey": "frost",
                "race": "human",
                "level": 90,
                "role": "spell",
                "position": "ranged_back",
            },
            "scenarioOptions": {
                "iterations": 10000,
                "fightStyle": "Patchwerk",
                "desiredTargets": 1,
                "maxTime": 300,
                "varyCombatLength": 0.2,
                "calculateScaleFactors": 1,
            },
            "preparationLines": ["potion=tempered_potion"],
        }


def verified_source_replay():
    from server.exact_template_authority_binding import (
        canonical_remote_template_source,
        seal_exact_template_authority_binding,
    )
    from tests.exact_template_authority_binding_test import (
        admission_proof,
        remote_source,
    )

    source = canonical_remote_template_source(remote_source())
    proof = admission_proof()
    binding = seal_exact_template_authority_binding(source, proof)
    exact_slot = {
        "itemId": "1001",
        "declaredItemLevel": 700,
        "bonusIds": [],
        "context": "",
        "gemIds": [],
        "gemBonusIds": [],
        "gemItemLevels": [],
        "enchantId": "",
        "craftedStats": [],
        "embellishmentIds": [],
        "redirectedBaseStats": [],
    }
    rows = []
    for relation in proof["exactAuthorityBySlot"]:
        rows.append({
            "slot": relation["slot"],
            "exactAuthorityEnvelopeKey": relation["exactAuthorityEnvelopeKey"],
            "bundle": SimpleNamespace(
                envelope=SimpleNamespace(
                    content_key=relation["exactAuthorityEnvelopeKey"],
                ),
                exact_item=SimpleNamespace(
                    canonical_bytes=json.dumps(exact_slot).encode("utf-8"),
                ),
            ),
        })
    return {
        "status": "verified",
        "source": source,
        "binding": binding,
        "slotBundles": tuple(rows),
        "problemCodes": [],
        "problems": [],
    }


def exact_materializer_dependency_vector():
    return {
        "seasonRevision": "season-17",
        "gameBuild": "12.0.1.12345",
        "gearRuleRevision": "gear-rule-v1",
        "resolverRevision": "resolver-v2",
        "compilerRevision": "compiler-v2",
        "workerRevision": "worker-v1",
        "simcRuntimeRevision": "simc-runtime-v1",
        "effectAuthorityRevision": "effect-authority-v1",
    }


class ReplayMaterializer:
    def __init__(self, replay):
        self.replay = replay
        self.calls = []

    def __call__(self, request, owner_key_hash):
        self.calls.append((request, owner_key_hash))
        return self.replay


class CapturingSnapshotStore:
    def __init__(self):
        self.calls = []

    def seal_loadout(self, row, **kwargs):
        self.calls.append(("loadout", row, kwargs))
        return row

    def seal_snapshot(self, row, **kwargs):
        self.calls.append(("snapshot", row, kwargs))
        return row


class ExactSimcApiTest(unittest.TestCase):
    def test_job_owner_hash_is_domain_separated_from_the_authenticated_user_id(self):
        """Routes keep the UUID in request memory; 0032 receives only this hash."""

        self.assertIsNotNone(exact_simc_job_owner_key_hash_for_user_id)
        owner_a = exact_simc_job_owner_key_hash_for_user_id(
            "12345678-1234-5678-1234-567812345678",
        )
        owner_b = exact_simc_job_owner_key_hash_for_user_id(
            "12345678-1234-5678-1234-567812345679",
        )
        self.assertRegex(owner_a, r"^sha256:[0-9a-f]{64}$")
        self.assertNotEqual(owner_a, owner_b)
        with self.assertRaises(ValueError):
            exact_simc_job_owner_key_hash_for_user_id("not-a-user-id")

    def test_authenticated_source_materializer_uses_private_user_scope_and_job_hash_only(self):
        """The client source ref cannot become a cross-owner UUID lookup."""

        self.assertIsNotNone(AuthenticatedExactSourceMaterializer)
        user_id = "12345678-1234-5678-1234-567812345678"
        template_id = "87654321-4321-8765-4321-876543218765"
        revisions = {
            "gear_exact_registry_revision": "gear-exact-registry:sha256:" + "a" * 64,
            "gear_rule_revision": "gear-rule-v1",
            "resolver_revision": "resolver-v2",
            "simc_runtime_revision": "simc-runtime-v1",
        }
        reader = CapturingSourceReader()
        materializer = AuthenticatedExactSourceMaterializer(
            authenticated_user_id=user_id,
            source_reader=reader,
            authority_revisions=revisions,
        )
        request = {
            "selectionIntent": {"client": "must-not-control-source"},
            "sourceRef": {
                "contractRevision": "exact-simc-source-ref-v1",
                "kind": "template",
                "sourceId": template_id,
                "remote": True,
            },
        }

        result = materializer(
            request,
            exact_simc_job_owner_key_hash_for_user_id(user_id),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(reader.calls, [(user_id, template_id, revisions)])
        wrong_owner = materializer(
            request,
            exact_simc_job_owner_key_hash_for_user_id(
                "12345678-1234-5678-1234-567812345679",
            ),
        )
        self.assertEqual(wrong_owner["status"], "blocked")
        self.assertEqual(wrong_owner["problems"], [{"code": "EXACT_SOURCE_AUTHORITY_REQUIRED"}])
        self.assertEqual(len(reader.calls), 1)

        bad_source = materializer(
            {
                "sourceRef": {
                    "contractRevision": "exact-simc-source-ref-v1",
                    "kind": "template",
                    "sourceId": "not-a-template-uuid",
                    "remote": True,
                },
            },
            exact_simc_job_owner_key_hash_for_user_id(user_id),
        )
        self.assertEqual(bad_source["status"], "blocked")
        self.assertEqual(len(reader.calls), 1)

    def test_source_only_materializer_never_exposes_a_ready_exact_confirmation(self):
        """A source binding is necessary but cannot bypass v2/effect/snapshot work."""

        user_id = "12345678-1234-5678-1234-567812345678"
        reader = VerifiedSourceReader()
        materializer = AuthenticatedExactSourceMaterializer(
            authenticated_user_id=user_id,
            source_reader=reader,
            authority_revisions={
                "gear_exact_registry_revision": "gear-exact-registry:sha256:" + "a" * 64,
                "gear_rule_revision": "gear-rule-v1",
                "resolver_revision": "resolver-v2",
                "simc_runtime_revision": "simc-runtime-v1",
            },
        )
        api = ExactSimcApi(materialize=materializer, job_store=CapturingJobStore())

        response = api.confirm(
            {
                "sourceRef": {
                    "contractRevision": "exact-simc-source-ref-v1",
                    "kind": "template",
                    "sourceId": "87654321-4321-8765-4321-876543218765",
                    "remote": True,
                },
            },
            owner_key_hash=exact_simc_job_owner_key_hash_for_user_id(user_id),
        )

        self.assertEqual(response, {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "confirm",
            "status": "blocked",
            "data": {},
            "problems": [{"code": "EXACT_AUTHORITY_UNAVAILABLE"}],
        })
        self.assertEqual(len(reader.calls), 1)

    def test_authenticated_profile_materializer_reloads_only_remote_source_and_never_returns_raw(self):
        """Removing the owner reload or accepting client profile text must fail here."""

        self.assertIsNotNone(AuthenticatedExactProfileMaterializer)
        user_id = "12345678-1234-5678-1234-567812345678"
        template_id = "87654321-4321-8765-4321-876543218765"
        store = CapturingTalentStore()
        compiler = CapturingProfileCompiler()
        materializer = AuthenticatedExactProfileMaterializer(
            authenticated_user_id=user_id,
            personal_store=store,
            profile_compiler=compiler,
        )
        gear_source = SimpleNamespace(selection_intent={
            "eligibilityContext": {
                "classKey": "mage",
                "specKey": "frost",
            },
        })
        request = {
            "profileRef": {
                "contractRevision": "exact-simc-profile-ref-v1",
                "kind": "talent-template",
                "sourceId": template_id,
                "remote": True,
            },
            "executionIntent": {
                "contractRevision": "exact-simc-execution-intent-v1",
                "raceKey": "human",
                "scenarioKey": "single",
            },
        }

        profile = materializer(request, gear_source)

        self.assertEqual(store.calls, [(user_id, template_id)])
        self.assertEqual(len(compiler.calls), 1)
        self.assertEqual(compiler.calls[0][1], request["executionIntent"])
        self.assertEqual(compiler.calls[0][2], gear_source)
        self.assertEqual(profile["talentProfileKey"], "talent-profile:sha256:" + "b" * 64)
        self.assertNotIn("rawString", profile)
        self.assertNotIn("talentSource", profile)

        blocked = materializer({
            **request,
            "profileContext": {"talents": "client-must-not-be-used"},
        }, gear_source)
        self.assertEqual(blocked, {
            "status": "blocked",
            "problems": [{"code": "EXACT_PROFILE_AUTHORITY_REQUIRED"}],
        })
        self.assertEqual(store.calls, [(user_id, template_id)])

    def test_authenticated_profile_materializer_blocks_talent_class_or_spec_drift_before_compile(self):
        """A mismatched saved talent row must not be compiled for another gear source."""

        user_id = "12345678-1234-5678-1234-567812345678"
        store = CapturingTalentStore()
        compiler = CapturingProfileCompiler()
        materializer = AuthenticatedExactProfileMaterializer(
            authenticated_user_id=user_id,
            personal_store=store,
            profile_compiler=compiler,
        )
        result = materializer({
            "profileRef": {
                "contractRevision": "exact-simc-profile-ref-v1",
                "kind": "talent-template",
                "sourceId": "87654321-4321-8765-4321-876543218765",
                "remote": True,
            },
            "executionIntent": {
                "contractRevision": "exact-simc-execution-intent-v1",
                "raceKey": "human",
                "scenarioKey": "single",
            },
        }, SimpleNamespace(selection_intent={
            "eligibilityContext": {
                "classKey": "mage",
                "specKey": "arcane",
            },
        }))

        self.assertEqual(result, {
            "status": "blocked",
            "problems": [{"code": "EXACT_PROFILE_AUTHORITY_REQUIRED"}],
        })
        self.assertEqual(compiler.calls, [])

    def test_full_materializer_derives_v2_job_input_only_from_replayed_exact_bundles(self):
        """A forged v1 request cannot alter the exact bytes that enter 0032."""

        self.assertIsNotNone(ExactSimcMaterializer)
        module = __import__("server.exact_simc_api", fromlist=["ExactSimcMaterializer"])
        replay = verified_source_replay()
        source_materializer = ReplayMaterializer(replay)
        store = CapturingSnapshotStore()
        dependencies = exact_materializer_dependency_vector()
        authority = {
            "authorityContext": {"server": "only"},
            "gearExactRegistryRevision": "gear-exact-registry:sha256:" + "1" * 64,
            "loadoutEffectAuthority": object(),
            "dependencyVector": dependencies,
        }
        materializer = ExactSimcMaterializer(
            source_materializer=source_materializer,
            authority_provider=lambda _source: authority,
            profile_materializer=lambda _request, _source: {
                "talentProfileKey": "talent-profile:sha256:" + "a" * 64,
                "talentLines": ["talents=CYQAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"],
                "characterContext": {"classKey": "mage", "specKey": "frost", "race": "human", "level": 80, "position": "back"},
                "scenarioOptions": {"iterations": 1000, "fightStyle": "patchwerk", "desiredTargets": 1, "durationSeconds": 300},
                "preparationLines": [],
            },
            snapshot_store=store,
        )
        request = {
            "selectionIntent": {"client": "forged-v1-is-not-used"},
            "sourceRef": {"contractRevision": "exact-simc-source-ref-v1", "kind": "template", "sourceId": replay["source"].template_id, "remote": True},
        }
        loadout = {"status": "ready", "resolvedLoadoutKey": "resolved-loadout-v2:sha256:" + "b" * 64}
        snapshot = {
            "status": "ready",
            "simulationSnapshotKey": "simulation-snapshot-v2:sha256:" + "c" * 64,
            "resolvedLoadoutKey": "resolved-loadout-v2:sha256:" + "b" * 64,
            "rowHash": "sha256:" + "d" * 64,
        }

        with patch.object(module, "resolve_v2", return_value={"status": "verified"}) as resolve, patch.object(
            module, "build_resolved_loadout_v2", return_value=loadout
        ) as build_loadout, patch.object(module, "build_simulation_snapshot_v2", return_value=snapshot) as build_snapshot:
            result = materializer(request, "sha256:" + "f" * 64)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["confirmation"]["resolvedLoadoutKey"], loadout["resolvedLoadoutKey"])
        self.assertEqual(result["confirmation"]["simulationSnapshotKey"], snapshot["simulationSnapshotKey"])
        self.assertEqual(result["confirmation"]["dependencyVector"], dependencies)
        self.assertEqual(
            result["jobRequest"].request_json["schemaRevision"],
            "exact-import-job-request-v2",
        )
        self.assertEqual(
            {
                "resolvedLoadoutKey": result["jobRequest"].request_json["resolvedLoadoutKey"],
                "simulationSnapshotKey": result["jobRequest"].request_json["simulationSnapshotKey"],
                "snapshotRowHash": result["jobRequest"].request_json["snapshotRowHash"],
            },
            {
                "resolvedLoadoutKey": loadout["resolvedLoadoutKey"],
                "simulationSnapshotKey": snapshot["simulationSnapshotKey"],
                "snapshotRowHash": snapshot["rowHash"],
            },
        )
        self.assertEqual(result["jobRequest"].request_json["exactLoadoutIntent"]["slots"]["head"]["itemId"], "1001")
        self.assertEqual(result["jobRequest"].request_json["exactLoadoutIntent"]["eligibilityContext"], replay["source"].selection_intent["eligibilityContext"])
        self.assertEqual(len(store.calls), 2)
        self.assertEqual(resolve.call_args.args[0], replay["source"].selection_intent)
        self.assertEqual(build_loadout.call_args.kwargs["exact_authority_by_slot"], json.loads(replay["binding"].canonical_bytes)["exactAuthorityBySlot"])
        self.assertEqual(build_snapshot.call_args.kwargs["resolved_loadout"], loadout)

    def test_full_materializer_blocks_before_snapshot_and_job_when_loadout_effect_is_missing(self):
        self.assertIsNotNone(ExactSimcMaterializer)
        module = __import__("server.exact_simc_api", fromlist=["ExactSimcMaterializer"])
        replay = verified_source_replay()
        store = CapturingSnapshotStore()
        materializer = ExactSimcMaterializer(
            source_materializer=ReplayMaterializer(replay),
            authority_provider=lambda _source: {
                "authorityContext": {"server": "only"},
                "gearExactRegistryRevision": "gear-exact-registry:sha256:" + "1" * 64,
                "loadoutEffectAuthority": None,
                "dependencyVector": exact_materializer_dependency_vector(),
            },
            profile_materializer=lambda _request, _source: {},
            snapshot_store=store,
        )

        with patch.object(module, "resolve_v2", return_value={
            "status": "blocked",
            "problems": [{"code": "LOADOUT_EFFECT_AUTHORITY_REQUIRED"}],
        }) as resolve:
            result = materializer({"sourceRef": {}}, "sha256:" + "f" * 64)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["problems"], [{"code": "LOADOUT_EFFECT_AUTHORITY_REQUIRED"}])
        self.assertEqual(store.calls, [])
        self.assertEqual(resolve.call_count, 1)

    def test_full_materializer_validates_exact_job_input_before_persisting_snapshot(self):
        replay = verified_source_replay()
        replay["slotBundles"][0]["bundle"].exact_item = SimpleNamespace(
            canonical_bytes=b"{}",
        )
        store = CapturingSnapshotStore()
        materializer = ExactSimcMaterializer(
            source_materializer=ReplayMaterializer(replay),
            authority_provider=lambda _source: {
                "authorityContext": {"server": "only"},
                "gearExactRegistryRevision": "gear-exact-registry:sha256:" + "1" * 64,
                "loadoutEffectAuthority": object(),
                "dependencyVector": exact_materializer_dependency_vector(),
            },
            profile_materializer=lambda _request, _source: {
                "talentProfileKey": "talent-profile:sha256:" + "a" * 64,
                "talentLines": ["talents=CYQAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"],
                "characterContext": {"classKey": "mage", "specKey": "frost", "race": "human", "level": 80, "position": "back"},
                "scenarioOptions": {"iterations": 1000, "fightStyle": "patchwerk", "desiredTargets": 1, "durationSeconds": 300},
                "preparationLines": [],
            },
            snapshot_store=store,
        )
        module = __import__("server.exact_simc_api", fromlist=["ExactSimcMaterializer"])

        with patch.object(module, "resolve_v2", return_value={"status": "verified"}), patch.object(
            module, "build_resolved_loadout_v2", return_value={"status": "ready", "resolvedLoadoutKey": "resolved-loadout-v2:sha256:" + "b" * 64}
        ), patch.object(
            module, "build_simulation_snapshot_v2", return_value={"status": "ready", "simulationSnapshotKey": "simulation-snapshot-v2:sha256:" + "c" * 64}
        ):
            result = materializer({"sourceRef": {}}, "sha256:" + "f" * 64)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(store.calls, [])

    def test_confirm_returns_literal_loadout_authority_block_without_creating_a_job(self):
        """A missing aggregate must not turn the old submit flow into a task."""

        self.assertIsNotNone(
            ExactSimcApi,
            "Task 5A needs a server-owned Exact confirm API before the page can bind it",
        )
        jobs = CapturingJobStore()
        api = ExactSimcApi(
            materialize=lambda _request, _owner_key_hash: {
                "status": "blocked",
                "problems": [{
                    "code": "LOADOUT_EFFECT_AUTHORITY_REQUIRED",
                    "path": "ruleMatrix.loadoutEffectSubjects",
                }],
            },
            job_store=jobs,
        )

        response = api.confirm({
            "selectionIntent": {"schemaRevision": "selection-intent-v1"},
            "profileContext": {"classKey": "mage", "specKey": "frost"},
            "sourceRef": {
                "contractRevision": "exact-simc-source-ref-v1",
                "kind": "template",
                "sourceId": "template-frost",
                "remote": True,
            },
        }, owner_key_hash="sha256:" + "f" * 64)

        self.assertEqual(response, {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "confirm",
            "status": "blocked",
            "data": {},
            "problems": [{
                "code": "LOADOUT_EFFECT_AUTHORITY_REQUIRED",
                "path": "ruleMatrix.loadoutEffectSubjects",
            }],
        })
        self.assertEqual(jobs.enqueued, [])

    def test_confirm_and_submit_fail_closed_when_injected_dependencies_raise(self):
        """Private dependency errors must not escape or create an Exact job."""

        owner = "sha256:" + "e" * 64
        source_ref = {
            "contractRevision": "exact-simc-source-ref-v1",
            "kind": "template",
            "sourceId": "template-frost",
            "remote": True,
        }
        unavailable = ExactSimcApi(
            materialize=lambda _request, _owner: (_ for _ in ()).throw(
                RuntimeError("private authority outage"),
            ),
            job_store=CapturingJobStore(),
        )
        self.assertEqual(unavailable.confirm({"sourceRef": source_ref}, owner_key_hash=owner), {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "confirm",
            "status": "blocked",
            "data": {},
            "problems": [{"code": "EXACT_AUTHORITY_UNAVAILABLE"}],
        })

        from server.gear_exact_import_job_store import build_exact_import_job_request
        from tests.gear_exact_import_job_store_test import (
            dependency_vector,
            exact_intent,
            snapshot_reference,
        )

        reference = snapshot_reference()
        request = build_exact_import_job_request(
            exact_intent(),
            dependency_vector(),
            snapshot_reference=reference,
        )
        confirmation = {
            "requestKey": request.request_key,
            "resolvedLoadoutKey": reference["resolvedLoadoutKey"],
            "simulationSnapshotKey": reference["simulationSnapshotKey"],
            "dependencyVector": dependency_vector(),
        }
        enqueue_failure = ExactSimcApi(
            materialize=lambda _request, _owner: {
                "status": "ready",
                "confirmation": confirmation,
                "jobRequest": request,
            },
            job_store=ExplodingJobStore(),
        )
        self.assertEqual(enqueue_failure.submit(
            {"sourceRef": source_ref},
            confirmation=confirmation,
            owner_key_hash=owner,
        ), {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "submit",
            "status": "blocked",
            "data": {},
            "problems": [{"code": "EXACT_JOB_ENQUEUE_INVALID"}],
        })

    def test_confirm_returns_only_server_materialized_exact_identities_when_ready(self):
        """The page can retain confirmation identities but not Exact payload facts."""

        self.assertIsNotNone(ExactSimcApi)
        jobs = CapturingJobStore()
        request_key = "exact-import-request:sha256:" + "a" * 64
        loadout_key = "resolved-loadout-v2:sha256:" + "b" * 64
        snapshot_key = "simulation-snapshot-v2:sha256:" + "c" * 64
        api = ExactSimcApi(
            materialize=lambda _request, _owner_key_hash: {
                "status": "ready",
                "confirmation": {
                    "requestKey": request_key,
                    "resolvedLoadoutKey": loadout_key,
                    "simulationSnapshotKey": snapshot_key,
                    "dependencyVector": exact_dependency_vector(),
                },
            },
            job_store=jobs,
        )

        response = api.confirm({
            "selectionIntent": {"schemaRevision": "selection-intent-v1"},
            "profileContext": {"classKey": "mage", "specKey": "frost"},
            "sourceRef": {
                "contractRevision": "exact-simc-source-ref-v1",
                "kind": "template",
                "sourceId": "template-frost",
                "remote": True,
            },
        }, owner_key_hash="sha256:" + "f" * 64)

        self.assertEqual(response, {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "confirm",
            "status": "ready",
            "data": {
                "requestKey": request_key,
                "resolvedLoadoutKey": loadout_key,
                "simulationSnapshotKey": snapshot_key,
                "dependencyVector": exact_dependency_vector(),
            },
            "problems": [],
        })
        self.assertEqual(jobs.enqueued, [])

    def test_submit_rejects_a_client_forged_confirmation_without_creating_a_job(self):
        """A copied v1 intent may not substitute a different Exact snapshot."""

        self.assertIsNotNone(ExactSimcApi)
        jobs = CapturingJobStore()
        confirmation = {
            "requestKey": "exact-import-request:sha256:" + "a" * 64,
            "resolvedLoadoutKey": "resolved-loadout-v2:sha256:" + "b" * 64,
            "simulationSnapshotKey": "simulation-snapshot-v2:sha256:" + "c" * 64,
            "dependencyVector": exact_dependency_vector(),
        }
        api = ExactSimcApi(
            materialize=lambda _request, _owner_key_hash: {
                "status": "ready",
                "confirmation": confirmation,
                "jobRequest": object(),
            },
            job_store=jobs,
        )

        self.assertTrue(
            hasattr(api, "submit"),
            "Task 5A needs an Exact submit operation distinct from confirm",
        )
        if not hasattr(api, "submit"):
            return

        response = api.submit(
            {
                "selectionIntent": {"schemaRevision": "selection-intent-v1"},
                "profileContext": {"classKey": "mage", "specKey": "frost"},
                "sourceRef": {
                    "contractRevision": "exact-simc-source-ref-v1",
                    "kind": "template",
                    "sourceId": "template-frost",
                    "remote": True,
                },
            },
            confirmation={
                **confirmation,
                "simulationSnapshotKey": "simulation-snapshot-v2:sha256:" + "d" * 64,
            },
            owner_key_hash="sha256:" + "e" * 64,
        )

        self.assertEqual(response, {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "submit",
            "status": "blocked",
            "data": {},
            "problems": [{"code": "EXACT_CONFIRMATION_MISMATCH"}],
        })
        self.assertEqual(jobs.enqueued, [])

    def test_submit_enqueues_only_the_server_rebuilt_confirmed_exact_request(self):
        """Changing submit to pass client facts or the legacy task store must fail here."""

        self.assertIsNotNone(ExactSimcApi)
        from server.gear_exact_import_job_store import build_exact_import_job_request
        from tests.gear_exact_import_job_store_test import (
            dependency_vector,
            exact_intent,
            snapshot_reference,
        )

        reference = snapshot_reference()
        request = build_exact_import_job_request(
            exact_intent(),
            dependency_vector(),
            snapshot_reference=reference,
        )
        confirmation = {
            "requestKey": request.request_key,
            "resolvedLoadoutKey": reference["resolvedLoadoutKey"],
            "simulationSnapshotKey": reference["simulationSnapshotKey"],
            "dependencyVector": dependency_vector(),
        }
        jobs = AcceptingJobStore()
        api = ExactSimcApi(
            materialize=lambda _request, _owner_key_hash: {
                "status": "ready",
                "confirmation": confirmation,
                "jobRequest": request,
            },
            job_store=jobs,
        )
        owner_key_hash = "sha256:" + "e" * 64

        response = api.submit(
            {
                "selectionIntent": {"schemaRevision": "selection-intent-v1"},
                "profileContext": {"classKey": "mage", "specKey": "frost"},
                "sourceRef": {
                    "contractRevision": "exact-simc-source-ref-v1",
                    "kind": "template",
                    "sourceId": "template-frost",
                    "remote": True,
                },
            },
            confirmation=confirmation,
            owner_key_hash=owner_key_hash,
        )

        self.assertEqual(response, {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "submit",
            "status": "queued",
            "data": {
                **confirmation,
                "jobId": 41,
                "jobStatus": "queued",
                "cooldownUntil": None,
            },
            "problems": [],
        })
        self.assertEqual(jobs.enqueued, [(owner_key_hash, request)])

    def test_submit_rejects_a_v1_job_when_confirmation_names_a_v2_snapshot(self):
        from server.gear_exact_import_job_store import build_exact_import_job_request
        from tests.gear_exact_import_job_store_test import dependency_vector, exact_intent

        request = build_exact_import_job_request(exact_intent(), dependency_vector())
        confirmation = {
            "requestKey": request.request_key,
            "resolvedLoadoutKey": "resolved-loadout-v2:sha256:" + "b" * 64,
            "simulationSnapshotKey": "simulation-snapshot-v2:sha256:" + "c" * 64,
            "dependencyVector": dependency_vector(),
        }
        jobs = AcceptingJobStore()
        api = ExactSimcApi(
            materialize=lambda _request, _owner_key_hash: {
                "status": "ready",
                "confirmation": confirmation,
                "jobRequest": request,
            },
            job_store=jobs,
        )

        response = api.submit(
            {
                "sourceRef": {
                    "contractRevision": "exact-simc-source-ref-v1",
                    "kind": "template",
                    "sourceId": "template-frost",
                    "remote": True,
                },
            },
            confirmation=confirmation,
            owner_key_hash="sha256:" + "e" * 64,
        )

        self.assertEqual(response, {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "submit",
            "status": "blocked",
            "data": {},
            "problems": [{"code": "EXACT_CONFIRMATION_MISMATCH"}],
        })
        self.assertEqual(jobs.enqueued, [])

    def test_read_exposes_only_owner_scoped_bounded_exact_job_state(self):
        """Readback cannot reveal another owner's job or an internal row shape."""

        owner_a = "sha256:" + "a" * 64
        owner_b = "sha256:" + "b" * 64
        request_key = "exact-import-request:sha256:" + "c" * 64
        jobs = ReadingJobStore({
            owner_a: {
                41: {
                    "jobId": 41,
                    "requestKey": request_key,
                    "status": "resolved",
                    "resultJson": {
                        "resultIdentity": "simc-result:sha256:" + "d" * 64,
                        "status": "resolved",
                        "dps": 123456,
                    },
                    "problemJson": None,
                    "queuedAt": "2026-08-07T00:00:00+00:00",
                    "startedAt": "2026-08-07T00:00:01+00:00",
                    "finishedAt": "2026-08-07T00:00:02+00:00",
                    "cooldownUntil": None,
                },
            },
        })
        api = ExactSimcApi(
            materialize=lambda _request, _owner_key_hash: {},
            job_store=jobs,
        )

        self.assertEqual(api.read(41, owner_key_hash=owner_b), {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "read",
            "status": "blocked",
            "data": {},
            "problems": [{"code": "EXACT_JOB_NOT_FOUND"}],
        })
        self.assertEqual(api.read(41, owner_key_hash=owner_a), {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "read",
            "status": "resolved",
            "data": {
                "jobId": 41,
                "requestKey": request_key,
                "jobStatus": "resolved",
                "result": {
                    "resultIdentity": "simc-result:sha256:" + "d" * 64,
                    "status": "resolved",
                    "dps": 123456,
                },
                "cooldownUntil": None,
            },
            "problems": [],
        })
        jobs.rows_by_owner[owner_a][42] = {
            **jobs.rows_by_owner[owner_a][41],
            "jobId": 42,
            "resultJson": {"rawProfile": "must-not-escape"},
        }
        self.assertEqual(api.read(42, owner_key_hash=owner_a), {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "read",
            "status": "blocked",
            "data": {},
            "problems": [{"code": "EXACT_JOB_READ_INVALID"}],
        })
        self.assertEqual(jobs.calls, [(owner_b, 41), (owner_a, 41), (owner_a, 42)])

    def test_submit_rejects_a_confirmation_whose_revisions_do_not_equal_the_typed_job_request(self):
        """A matching request key alone cannot hide a dependency-vector drift."""

        self.assertIsNotNone(ExactSimcApi)
        from server.gear_exact_import_job_store import build_exact_import_job_request
        from tests.gear_exact_import_job_store_test import dependency_vector, exact_intent

        request = build_exact_import_job_request(exact_intent(), dependency_vector())
        confirmation = {
            "requestKey": request.request_key,
            "resolvedLoadoutKey": "resolved-loadout-v2:sha256:" + "b" * 64,
            "simulationSnapshotKey": "simulation-snapshot-v2:sha256:" + "c" * 64,
            "dependencyVector": {
                **dependency_vector(),
                "simcRuntimeRevision": "simc:other-runtime",
            },
        }
        jobs = CapturingJobStore()
        api = ExactSimcApi(
            materialize=lambda _request, _owner_key_hash: {
                "status": "ready",
                "confirmation": confirmation,
                "jobRequest": request,
            },
            job_store=jobs,
        )

        response = api.submit(
            {
                "selectionIntent": {"schemaRevision": "selection-intent-v1"},
                "profileContext": {"classKey": "mage", "specKey": "frost"},
                "sourceRef": {
                    "contractRevision": "exact-simc-source-ref-v1",
                    "kind": "template",
                    "sourceId": "template-frost",
                    "remote": True,
                },
            },
            confirmation=confirmation,
            owner_key_hash="sha256:" + "e" * 64,
        )

        self.assertEqual(response, {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "submit",
            "status": "blocked",
            "data": {},
            "problems": [{"code": "EXACT_CONFIRMATION_MISMATCH"}],
        })
        self.assertEqual(jobs.enqueued, [])

    def test_confirm_rejects_missing_source_ref_before_materializing_v1_intent(self):
        """A v1 intent alone cannot identify the Exact authority it needs."""

        self.assertIsNotNone(ExactSimcApi)
        api = ExactSimcApi(
            materialize=lambda _request, _owner_key_hash: {
                "status": "ready",
                "confirmation": {
                    "requestKey": "exact-import-request:sha256:" + "a" * 64,
                    "resolvedLoadoutKey": "resolved-loadout-v2:sha256:" + "b" * 64,
                    "simulationSnapshotKey": "simulation-snapshot-v2:sha256:" + "c" * 64,
                    "dependencyVector": exact_dependency_vector(),
                },
            },
            job_store=CapturingJobStore(),
        )

        response = api.confirm({
            "selectionIntent": {"schemaRevision": "selection-intent-v1"},
            "profileContext": {"classKey": "mage", "specKey": "frost"},
        }, owner_key_hash="sha256:" + "f" * 64)

        self.assertEqual(response, {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "confirm",
            "status": "blocked",
            "data": {},
            "problems": [{"code": "EXACT_SOURCE_AUTHORITY_REQUIRED"}],
        })

    def test_confirm_reloads_the_same_remote_source_inside_the_authenticated_owner_scope(self):
        """A client-controlled template id cannot cross an account boundary."""

        self.assertIsNotNone(ExactSimcApi)
        owner_a = "sha256:" + "a" * 64
        owner_b = "sha256:" + "b" * 64
        request_key = "exact-import-request:sha256:" + "c" * 64
        materialized_owners = []

        def materialize(_request, owner_key_hash):
            materialized_owners.append(owner_key_hash)
            if owner_key_hash != owner_a:
                return {
                    "status": "blocked",
                    "problems": [{"code": "EXACT_SOURCE_AUTHORITY_REQUIRED"}],
                }
            return {
                "status": "ready",
                "confirmation": {
                    "requestKey": request_key,
                    "resolvedLoadoutKey": "resolved-loadout-v2:sha256:" + "d" * 64,
                    "simulationSnapshotKey": "simulation-snapshot-v2:sha256:" + "e" * 64,
                    "dependencyVector": exact_dependency_vector(),
                },
            }

        api = ExactSimcApi(materialize=materialize, job_store=CapturingJobStore())
        request = {
            "selectionIntent": {"schemaRevision": "selection-intent-v1"},
            "profileContext": {"classKey": "mage", "specKey": "frost"},
            "sourceRef": {
                "contractRevision": "exact-simc-source-ref-v1",
                "kind": "template",
                "sourceId": "template-frost",
                "remote": True,
            },
        }

        self.assertEqual(
            api.confirm(request, owner_key_hash=owner_b),
            {
                "contractRevision": "exact-simc-envelope-v1",
                "operation": "confirm",
                "status": "blocked",
                "data": {},
                "problems": [{"code": "EXACT_SOURCE_AUTHORITY_REQUIRED"}],
            },
        )
        self.assertEqual(api.confirm(request, owner_key_hash=owner_a)["status"], "ready")
        self.assertEqual(materialized_owners, [owner_b, owner_a])

    def test_confirm_refuses_a_malformed_dependency_vector_before_exposing_it_to_the_page(self):
        """The public confirmation can expose only the frozen exact job revisions."""

        self.assertIsNotNone(ExactSimcApi)
        api = ExactSimcApi(
            materialize=lambda _request, _owner_key_hash: {
                "status": "ready",
                "confirmation": {
                    "requestKey": "exact-import-request:sha256:" + "a" * 64,
                    "resolvedLoadoutKey": "resolved-loadout-v2:sha256:" + "b" * 64,
                    "simulationSnapshotKey": "simulation-snapshot-v2:sha256:" + "c" * 64,
                    "dependencyVector": {"rawProfile": "must-not-escape"},
                },
            },
            job_store=CapturingJobStore(),
        )

        response = api.confirm({
            "selectionIntent": {"schemaRevision": "selection-intent-v1"},
            "profileContext": {"classKey": "mage", "specKey": "frost"},
            "sourceRef": {
                "contractRevision": "exact-simc-source-ref-v1",
                "kind": "template",
                "sourceId": "template-frost",
                "remote": True,
            },
        }, owner_key_hash="sha256:" + "d" * 64)

        self.assertEqual(response, {
            "contractRevision": "exact-simc-envelope-v1",
            "operation": "confirm",
            "status": "blocked",
            "data": {},
            "problems": [{"code": "EXACT_AUTHORITY_UNAVAILABLE"}],
        })


if __name__ == "__main__":
    unittest.main()
