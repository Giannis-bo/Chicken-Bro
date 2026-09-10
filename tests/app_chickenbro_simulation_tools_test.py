import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import UUID, uuid4

from server.app.chickenbro import simulation_tools
from server.app.simulation.domain import SimulationJobStatus, SimulationResult
from tests import app_simulation_application_test as application_fixtures


class SimulationToolGatewayTest(unittest.TestCase):
    def setUp(self):
        fixture = application_fixtures.SimulationApplicationTest()
        fixture.setUp()
        self.application = fixture.application
        self.repository = fixture.repository
        self.queue = fixture.queue
        self.owner = fixture.owner
        self.other = fixture.other
        self.now = fixture.now
        self.ticks = 0.0
        self.gateway = simulation_tools.SimulationToolGateway(
            self.application, clock=lambda: self.ticks, sleep=self.advance,
        )
        self.context = simulation_tools.SimulationToolContext(self.owner, uuid4(), uuid4())
        self.token = self.gateway.issue_capability(self.context)
        self.url = "https://raider.io/characters/us/area-52/Stormsample"

    def advance(self, seconds):
        self.ticks += seconds

    def prepare(self, token=None):
        return self.gateway.execute(token or self.token, "prepare", {"sourceUrl": self.url})

    def submit(self, snapshot_id, scenario=None, token=None):
        return self.gateway.execute(token or self.token, "submit", {
            "snapshotId": snapshot_id, "scenario": scenario or {},
        })

    def complete(self, packet):
        job_id = UUID(packet["jobId"])
        job = self.repository.jobs[(self.owner.user_id, job_id)]
        snapshot = self.repository.snapshots[(self.owner.user_id, job.snapshot_id)]
        provenance = {
            "snapshotId": str(snapshot.id), "sourceRevision": snapshot.provenance["sourceRevision"],
            "sourceRawSha256": snapshot.raw_sha256, "profileSha256": "a" * 64,
            "compilerRevision": job.compiler_revision, "runtimeRevision": job.runtime_revision,
            "scenarioHash": job.scenario_hash,
        }
        self.repository.save_job(replace(job, status=SimulationJobStatus.SUCCEEDED))
        result = SimulationResult(
            uuid4(), job_id, self.owner.user_id, "a" * 64,
            {"metricName": "dps", "metricValue": 12345.0, "provenance": provenance,
             "metricError": 12.0, "metricErrorPct": 0.0972,
             "stdout": "PRIVATE_RAW", "storagePath": "/private/run"},
            "dps", 12345.0, job.compiler_revision, job.runtime_revision, provenance, self.now,
        )
        self.repository.save_result(result)
        return result

    def test_rerun_by_job_id_preserves_scenario_and_checks_owner(self):
        caps = replace(self.application._runtime_capabilities, compiler_revision="chickenbro-simc-compiler-v4")
        self.application._runtime_capabilities = caps
        self.application._compiler = application_fixtures.SimcProfileCompiler(capabilities=caps)
        baseline = self.submit(self.prepare()["snapshotId"], {"maxTime": 120, "desiredTargets": 5,
            "varyCombatLength": 0.1, "raidBuffs": False, "bloodlust": False})
        args = {"baseJobId": baseline["jobId"], "scenario": {"equipmentOverrides": {
            "trinket1": {"itemId": 9999, "itemLevel": 285, "bonusIds": [], "gems": [], "enchant": None}}}}
        variant = self.gateway.execute(self.token, "submit", args)
        self.assertEqual(variant["status"], "queued")
        self.assertNotEqual(variant["jobId"], baseline["jobId"])
        self.assertEqual(variant["snapshotId"], baseline["snapshotId"])
        self.assertEqual(variant["scenario"]["maxTime"], 120)
        self.assertEqual(variant["scenario"]["desiredTargets"], 5)
        self.assertFalse(variant["scenario"]["raidBuffs"])
        self.assertEqual(self.gateway.execute(self.token, "submit", args)["jobId"], variant["jobId"])
        original = self.gateway.execute(self.token, "get", {"jobId": baseline["jobId"]})
        self.assertNotIn("equipmentOverrides", original["scenario"])
        self.assertIn("gear", original)
        other_token = self.gateway.issue_capability(replace(self.context, principal=self.other, run_id=uuid4()))
        denied = self.gateway.execute(other_token, "submit", args)
        self.assertEqual(denied["errorCode"], "SIMULATION_NOT_FOUND")
        self.assertEqual(len(self.queue.calls), 2)

    def test_result_exposes_only_profile_bound_enchant_input_proof(self):
        packet = self.submit(self.prepare()['snapshotId'])
        result = self.complete(packet)
        proof = {'status': 'verified', 'profileSha256': result.profile_sha256,
                 'checked': ['talents', 'equipmentItemIds', 'overriddenItemLevels', 'overriddenEnchantIds'],
                 'overriddenEnchants': {'finger1': 123}, 'privatePath': '/private/report'}
        for profile_hash, expected in ((result.profile_sha256, True), ('b' * 64, False)):
            proof['profileSha256'] = profile_hash
            self.repository.save_result(replace(result, result={**result.result, 'effectiveConfig': proof}))
            read = self.gateway.execute(self.token, 'get', {'jobId': packet['jobId']})['result']
            if expected:
                self.assertEqual(read['effectiveConfig']['overriddenEnchants'], {'finger1': 123})
                self.assertEqual(read['effectiveConfig']['enchantEvidenceScope'], 'engine_reported_input_identity')
                self.assertNotIn('privatePath', read['effectiveConfig'])
            else:
                self.assertNotIn('effectiveConfig', read)

    def test_custom_rotation_preview_submit_reuse_and_owner_isolation(self):
        caps = replace(self.application._runtime_capabilities, compiler_revision="chickenbro-simc-compiler-v6")
        self.application._runtime_capabilities = caps
        self.application._compiler = application_fixtures.SimcProfileCompiler(capabilities=caps)
        baseline = self.submit(self.prepare()["snapshotId"], {"maxTime":60})
        args = {"baseJobId":baseline["jobId"], "scenario":{"actionLists":{"default":["stormkeeper", "lightning_bolt"]}}}
        preview = self.gateway.execute(self.token, "preview", args)
        self.assertEqual(preview['status'], 'ready')
        self.assertEqual(len(self.queue.calls), 1)
        variant = self.gateway.execute(self.token, "submit", args)
        self.assertEqual(variant['status'], 'queued')
        self.assertEqual(variant['scenarioHash'], preview['scenarioHash'])
        self.assertEqual(variant['scenario']['maxTime'], 60)
        self.assertEqual(variant['gear'], baseline['gear'])
        self.assertEqual(variant['talents'], baseline['talents'])
        self.assertEqual(self.gateway.execute(self.token, 'submit', args)['jobId'], variant['jobId'])
        other_token = self.gateway.issue_capability(replace(self.context, principal=self.other, run_id=uuid4()))
        self.assertEqual(self.gateway.execute(other_token, 'preview', args)['errorCode'], 'SIMULATION_NOT_FOUND')
        self.assertEqual(len(self.queue.calls), 2)

    def test_base_job_requires_owned_source_and_recorded_scenario(self):
        base = self.submit(self.prepare()["snapshotId"])
        self.queue.calls.clear()
        result = self.gateway.execute(self.token, "submit", {"baseJobId": base["jobId"], "scenario": {}})
        self.assertEqual(result["errorCode"], "SIMC_BASE_SCENARIO_UNAVAILABLE")
        result = self.gateway.execute(self.token, "submit", {"baseJobId": base["jobId"],
            "snapshotId": base["snapshotId"], "scenario": {}})
        self.assertEqual(result["errorCode"], "SIMC_ARGUMENTS_INVALID")
        self.assertEqual(len(self.queue.calls), 0)

    def test_effective_gear_preserves_known_unenchanted_item_for_rerun(self):
        prepared = self.prepare()
        self.assertIn("enchant", prepared["gear"]["trinket1"])
        self.assertIsNone(prepared["gear"]["trinket1"]["enchant"])
        baseline = self.submit(prepared["snapshotId"])
        read = self.gateway.execute(self.token, "get", {"jobId": baseline["jobId"]})
        self.assertIn("enchant", read["gear"]["trinket1"])
        self.assertIsNone(read["gear"]["trinket1"]["enchant"])

    def test_preparation_is_deduplicated_and_projects_real_gems(self):
        first = self.prepare()
        second = self.prepare()
        self.assertEqual(first["snapshotId"], second["snapshotId"])
        self.assertEqual(len(self.repository.snapshots), 1)
        self.assertEqual(first["status"], "ready")
        self.assertEqual(first["gear"]["neck"]["gems"], [2001])
        self.assertEqual(first["character"]["level"], 80)
        self.assertNotIn(str(self.owner.user_id), json.dumps(first))
        self.assertEqual(len(self.queue.calls), 0)

    def test_new_run_can_identify_baseline_and_gem_variant_from_persisted_jobs(self):
        capabilities = replace(self.application._runtime_capabilities,
            compiler_revision="chickenbro-simc-compiler-v2")
        self.application._runtime_capabilities = capabilities
        self.application._compiler = application_fixtures.SimcProfileCompiler(capabilities=capabilities)
        snapshot = self.prepare()
        baseline = self.submit(snapshot["snapshotId"], {"maxTime": 60})
        variant = self.submit(snapshot["snapshotId"], {"maxTime": 60, "gemOverrides": {"neck": [2002]}})
        self.gateway.revoke(self.token)
        gateway = simulation_tools.SimulationToolGateway(self.application)
        token = gateway.issue_capability(replace(self.context, run_id=uuid4()))
        jobs = {row["jobId"]: row for row in gateway.execute(token, "list", {})["jobs"]}
        self.assertEqual(jobs[baseline["jobId"]]["scenario"],
            {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 300, "maxTime": 60})
        self.assertEqual(jobs[variant["jobId"]]["scenario"]["gemOverrides"], {"neck": [2002]})
        read = gateway.execute(token, "get", {"jobId": variant["jobId"]})
        self.assertEqual(read["scenario"], jobs[variant["jobId"]]["scenario"])
        self.assertEqual(len(self.queue.calls), 2)

    def test_legacy_job_without_scenario_is_explicitly_limited(self):
        queued = self.submit(self.prepare()["snapshotId"])
        self.queue.calls.clear()
        packet = self.gateway.execute(self.token, "get", {"jobId": queued["jobId"]})
        self.assertIsNone(packet["scenario"])
        self.assertTrue(any("scenario" in value for value in packet["limitations"]))

    def test_foreign_owner_cannot_submit_or_read_or_list_jobs(self):
        snapshot = self.prepare()
        queued = self.submit(snapshot["snapshotId"])
        other_token = self.gateway.issue_capability(replace(self.context, principal=self.other))
        rejected = self.submit(snapshot["snapshotId"], token=other_token)
        self.assertEqual(rejected["errorCode"], "SNAPSHOT_NOT_FOUND")
        rejected = self.gateway.execute(other_token, "get", {"jobId": queued["jobId"]})
        self.assertEqual(rejected["errorCode"], "SIMULATION_NOT_FOUND")
        self.assertEqual(self.gateway.execute(other_token, "list", {})["jobs"], [])
        self.assertEqual(len(self.queue.calls), 1)

    def test_invalid_expired_and_revoked_capabilities_cannot_act(self):
        for bad in ("", "invalid", None):
            with self.assertRaises(simulation_tools.SimulationToolUnauthorized):
                self.gateway.execute(bad, "list", {})
        self.gateway.revoke(self.token)
        with self.assertRaises(simulation_tools.SimulationToolUnauthorized):
            self.prepare()
        token = self.gateway.issue_capability(replace(self.context, run_id=uuid4()))
        self.advance(901)
        with self.assertRaises(simulation_tools.SimulationToolUnauthorized):
            self.prepare(token)
        self.assertEqual(len(self.repository.snapshots), 0)

    def test_invalid_arguments_and_identity_injection_have_no_side_effects(self):
        invalid = [
            ("prepare", {"sourceUrl": self.url, "userId": str(self.other.user_id)}),
            ("submit", {"snapshotId": "bad", "scenario": {}}),
            ("submit", {"snapshotId": str(uuid4()), "scenario": {"userId": "attacker"}}),
            ("submit", {"snapshotId": str(uuid4()), "scenario": [], "idempotencyKey": "evil"}),
            ("get", {"jobId": str(uuid4()), "waitSeconds": 21}),
            ("get", {"jobId": str(uuid4()), "waitSeconds": True}),
            ("list", {"limit": 11}), ("list", {"limit": "1"}),
            ("list", {"cursor": "x" * 1025}), ("unknown", {}),
        ]
        for operation, args in invalid:
            with self.subTest(operation=operation, args=args):
                packet = self.gateway.execute(self.token, operation, args)
                self.assertEqual(packet["status"], "blocked")
        self.assertEqual(len(self.queue.calls), 0)

    def test_budget_shared_between_capabilities_and_idempotent_retry(self):
        snapshot = self.prepare()
        token2 = self.gateway.issue_capability(self.context)
        first = self.submit(snapshot["snapshotId"])
        repeated = self.submit(snapshot["snapshotId"], {"desiredTargets": 1}, token2)
        self.assertEqual(first["jobId"], repeated["jobId"])
        for targets in (2, 3, 4):
            self.assertEqual(self.submit(snapshot["snapshotId"], {"desiredTargets": targets})["status"], "queued")
        rejected = self.submit(snapshot["snapshotId"], {"desiredTargets": 5}, token2)
        self.assertEqual(rejected["errorCode"], "SIMC_JOB_BUDGET_EXCEEDED")
        self.assertEqual(len(self.queue.calls), 4)
        self.assertEqual(self.submit(snapshot["snapshotId"])["jobId"], first["jobId"])

    def test_concurrent_retries_enqueue_once_and_prepare_budget_is_bounded(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            snapshots = list(pool.map(lambda _: self.prepare(), range(16)))
            jobs = list(pool.map(lambda _: self.submit(snapshots[0]["snapshotId"]), range(16)))
        self.assertEqual(len({packet["snapshotId"] for packet in snapshots}), 1)
        self.assertEqual(len({packet["jobId"] for packet in jobs}), 1)
        self.assertEqual(len(self.queue.calls), 1)
        for name in ("Other", "Third"):
            self.gateway.execute(self.token, "prepare", {"sourceUrl": self.url.replace("Stormsample", name)})
        rejected = self.gateway.execute(self.token, "prepare", {"sourceUrl": self.url + "fourth"})
        self.assertEqual(rejected["errorCode"], "SIMC_PREPARE_BUDGET_EXCEEDED")
        self.assertEqual(len(self.repository.snapshots), 3)

    def test_success_requires_semantic_result_and_returns_only_safe_fields(self):
        queued = self.submit(self.prepare()["snapshotId"])
        result = self.complete(queued)
        packet = self.gateway.execute(self.token, "get", {"jobId": queued["jobId"]})
        self.assertEqual(packet["status"], "succeeded")
        self.assertEqual(packet["result"]["metricValue"], 12345.0)
        self.assertEqual(packet["result"]["metricError"], 12.0)
        self.assertEqual(packet["result"]["metricErrorPct"], 0.0972)
        raw = json.dumps(packet)
        for private in ("PRIVATE_RAW", "storagePath", str(self.owner.user_id)):
            self.assertNotIn(private, raw)
        self.repository.save_result(replace(result, primary_metric_value=0))
        rejected = self.gateway.execute(self.token, "get", {"jobId": queued["jobId"]})
        self.assertEqual(rejected["errorCode"], "SIMC_RESULT_INVALID")

    def test_polling_stops_at_bound_and_does_not_invent_results(self):
        queued = self.submit(self.prepare()["snapshotId"])
        packet = self.gateway.execute(self.token, "get", {"jobId": queued["jobId"], "waitSeconds": 3})
        self.assertEqual(self.ticks, 3)
        self.assertEqual(packet["status"], "queued")
        self.assertIsNone(packet["result"])
        self.assertTrue(packet["limitations"])

    def test_polling_rechecks_revocation(self):
        queued = self.submit(self.prepare()["snapshotId"])
        def revoke_during_sleep(seconds):
            self.advance(seconds)
            self.gateway.revoke(self.token)
        self.gateway._sleep = revoke_during_sleep
        with self.assertRaises(simulation_tools.SimulationToolUnauthorized):
            self.gateway.execute(self.token, "get", {"jobId": queued["jobId"], "waitSeconds": 3})

    def test_failed_preparations_are_deduplicated_and_cannot_exceed_budget(self):
        for suffix in ("one", "two", "three"):
            self.gateway.execute(self.token, "prepare", {"sourceUrl": "https://untrusted.example/" + suffix})
        rejected = self.prepare()
        self.assertEqual(rejected["errorCode"], "SIMC_PREPARE_BUDGET_EXCEEDED")
        self.assertEqual(len(self.repository.snapshots), 0)

    def test_uncertain_submission_retains_budget_and_retries_idempotently(self):
        snapshot_id = self.prepare()["snapshotId"]
        original = self.application.submit
        def lost_response(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("PRIVATE_DATABASE_CONNECTION")
        self.application.submit = lost_response
        for targets in (1, 2, 3, 4):
            packet = self.submit(snapshot_id, {"desiredTargets": targets})
            self.assertEqual(packet["status"], "blocked")
            self.assertNotIn("PRIVATE_DATABASE_CONNECTION", json.dumps(packet))
        self.application.submit = original
        self.assertEqual(self.submit(snapshot_id, {"desiredTargets": 5})["errorCode"], "SIMC_JOB_BUDGET_EXCEEDED")
        self.assertEqual(self.submit(snapshot_id)["status"], "queued")
        self.assertEqual(len(self.queue.calls), 4)


if __name__ == "__main__":
    unittest.main()

class SimulationExperimentTest(unittest.TestCase):
    setUp = SimulationToolGatewayTest.setUp
    advance = SimulationToolGatewayTest.advance
    prepare = SimulationToolGatewayTest.prepare
    submit = SimulationToolGatewayTest.submit
    complete = SimulationToolGatewayTest.complete
    def test_job_returns_owned_character_source_and_talents(self):
        prepared = self.prepare()
        job = self.submit(prepared['snapshotId'])
        self.assertEqual(job['character'],prepared['character'])
        self.assertEqual(job['source'],prepared['source'])
        self.assertEqual(job['talents'],prepared['talents'])

    def test_preflight_does_not_enqueue_and_exposes_exact_diff(self):
        prepared = self.prepare()
        baseline = self.submit(prepared['snapshotId'])
        caps=replace(self.application._runtime_capabilities, compiler_revision='chickenbro-simc-compiler-v5')
        self.application._runtime_capabilities=caps
        self.application._compiler=application_fixtures.SimcProfileCompiler(capabilities=caps)
        item={'itemId':9999,'itemLevel':285,'bonusIds':[],'gems':[],'enchant':None}
        preview=self.gateway.execute(self.token,'preview',{'baseJobId':baseline['jobId'],'scenario':{'equipmentOverrides':{'trinket1':item}}})
        self.assertEqual(preview['status'],'ready')
        self.assertEqual(preview['changes']['equipment']['trinket1']['after'],item)
        self.assertEqual(preview['gear']['trinket1'],item)
        self.assertEqual(len(self.queue.calls),1)
        self.assertNotIn('profile',preview)

    def test_compare_requires_matching_controls_and_owned_completed_results(self):
        a=self.submit(self.prepare()['snapshotId']);self.complete(a)
        b=self.submit(a['snapshotId'],{'desiredTargets':5});self.complete(b)
        result=self.gateway.execute(self.token,'compare',{'baselineJobId':a['jobId'],'variantJobId':b['jobId']})
        self.assertEqual(result['errorCode'],'SIMC_COMPARISON_CONTROLS_MISMATCH')
        result=self.gateway.execute(self.token,'compare',{'baselineJobId':a['jobId'],'variantJobId':a['jobId']})
        self.assertEqual(result['errorCode'],'SIMC_COMPARISON_SAME_JOB')

    def test_item_search_uses_engine_names_when_localization_is_missing(self):
        from tests.app_simulation_talent_editor_test import RUNTIME
        from copy import deepcopy
        source=self.prepare();sid=UUID(source['snapshotId'])
        old=self.repository.snapshots[(self.owner.user_id,sid)]
        raw=deepcopy(old.snapshot)
        raw['gear']['trinket2']={'itemId':270167,'itemLevel':308,'bonusIds':[12838],'gems':[],'enchant':None}
        self.repository.snapshots[(self.owner.user_id,sid)]=replace(old,snapshot=raw)
        self.application._runtime_capabilities=replace(self.application._runtime_capabilities,runtime_revision=RUNTIME)
        query=lambda text:self.gateway.execute(self.token,'options',{'snapshotId':str(sid),'kind':'items','query':text})
        english=query('Bottomless Bag')['options']['items']
        self.assertEqual(english[0]['itemId'],270164)
        self.assertEqual(english[0]['sameUpgradeVariants'][0]['equipment']['itemLevel'],308)
        self.assertEqual(query('270164')['options']['items'][0]['itemId'],270164)
        missing=query('无底袋')['options']
        self.assertIn(270164,[x['itemId'] for x in missing['supportedVariantItems']])

    def test_talent_preview_submit_followup_and_owner_isolation(self):
        from copy import deepcopy
        from pathlib import Path
        from tests.app_simulation_talent_editor_test import RUNTIME
        prepared=self.prepare(); sid=UUID(prepared['snapshotId'])
        old=self.repository.snapshots[(self.owner.user_id,sid)]
        raw=deepcopy(old.snapshot);raw['character']['level']=90
        raw['talents']={'string':json.loads(Path('tests/fixtures/simc/fusionbolt_raider_talents_12_1.json').read_text())['talents']}
        self.repository.snapshots[(self.owner.user_id,sid)]=replace(old,snapshot=raw)
        caps=replace(self.application._runtime_capabilities,compiler_revision='chickenbro-simc-compiler-v5',runtime_revision=RUNTIME)
        self.application._runtime_capabilities=caps
        self.application._compiler=application_fixtures.SimcProfileCompiler(capabilities=caps)
        base=self.submit(str(sid),{'desiredTargets':5,'maxTime':300})
        options=self.gateway.execute(self.token,'options',{'baseJobId':base['jobId'],'kind':'talents','query':'Master of the Elements'})
        node=options['options']['nodes'][0]
        target=next(e for e in node['entries'] if e['name']=='Molten Wrath')
        args={'baseJobId':base['jobId'],'scenario':{'talentOverrides':{'nodes':[{'nodeId':node['nodeId'],'entryId':target['entryId'],'rank':1}]}}}
        preview=self.gateway.execute(self.token,'preview',args)
        self.assertEqual(preview['status'],'ready',preview)
        self.assertEqual(len(preview['changes']['talents']),1)
        self.assertEqual(preview['changes']['equipment'],{})
        self.assertEqual(preview['changes']['parameters'],{})
        self.assertEqual(len(self.queue.calls),1)
        variant=self.gateway.execute(self.token,'submit',args)
        self.assertEqual(variant['status'],'queued',variant)
        self.assertEqual(variant['talents']['string'],preview['talents']['string'])
        self.assertEqual(variant['scenarioHash'],preview['scenarioHash'])
        self.assertEqual(self.gateway.execute(self.token,'submit',args)['jobId'],variant['jobId'])
        follow=self.gateway.execute(self.token,'submit',{'baseJobId':variant['jobId'],'scenario':{'iterations':1000}})
        self.assertEqual(follow['talents'],variant['talents'])
        self.assertEqual(follow['gear'],base['gear'])
        follow_preview=self.gateway.execute(self.token,'preview',{'baseJobId':variant['jobId'],'scenario':{'iterations':1000}})
        self.assertEqual(follow_preview['changes']['talents'],[])
        other=self.gateway.issue_capability(replace(self.context,principal=self.other,run_id=uuid4()))
        for operation, arguments in [('preview',args),('options',{'baseJobId':base['jobId'],'kind':'talents'}),
                                     ('compare',{'baselineJobId':base['jobId'],'variantJobId':variant['jobId']})]:
            self.assertEqual(self.gateway.execute(other,operation,arguments)['errorCode'],'SIMULATION_NOT_FOUND')
        self.assertEqual(len(self.queue.calls),3)

    def test_comparison_reports_measured_delta_and_conservative_uncertainty(self):
        caps=replace(self.application._runtime_capabilities,compiler_revision='chickenbro-simc-compiler-v4')
        self.application._runtime_capabilities=caps
        self.application._compiler=application_fixtures.SimcProfileCompiler(capabilities=caps)
        base=self.submit(self.prepare()['snapshotId']);self.complete(base)
        variant=self.gateway.execute(self.token,'submit',{'baseJobId':base['jobId'],'scenario':{'equipmentOverrides':{
            'trinket1':{'itemId':9999,'itemLevel':285,'bonusIds':[],'gems':[],'enchant':None}}}})
        args={'baselineJobId':base['jobId'],'variantJobId':variant['jobId']}
        self.assertEqual(self.gateway.execute(self.token,'compare',args)['errorCode'],'SIMC_COMPARISON_NOT_READY')
        result=self.complete(variant)
        compare=self.gateway.execute(self.token,'compare',args)['comparison']
        self.assertEqual(compare['assessment'],'within_reported_error')
        self.assertEqual(compare['combinedErrorBound'],24)
        self.repository.save_result(replace(result,primary_metric_value=13000,result={**result.result,'metricValue':13000}))
        compare=self.gateway.execute(self.token,'compare',args)['comparison']
        self.assertEqual(compare['assessment'],'higher')
        self.assertEqual(compare['delta'],655)
        self.assertAlmostEqual(compare['deltaPct'],655/12345*100)
        missing={**result.result,'metricValue':13000};missing.pop('metricError')
        self.repository.save_result(replace(result,primary_metric_value=13000,result=missing))
        self.assertEqual(self.gateway.execute(self.token,'compare',args)['comparison']['assessment'],'uncertainty_unavailable')
