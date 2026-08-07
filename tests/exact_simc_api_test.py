import unittest

try:
    from server.exact_simc_api import (
        AuthenticatedExactSourceMaterializer,
        ExactSimcApi,
        exact_simc_job_owner_key_hash_for_user_id,
    )
except ImportError:  # RED: the Task 5A owner does not exist yet.
    AuthenticatedExactSourceMaterializer = None
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
