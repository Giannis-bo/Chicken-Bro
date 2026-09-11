import unittest
import json
from dataclasses import replace
from uuid import uuid4
from unittest.mock import patch

from server.app.simulation.domain import SimulationJobStatus, SimulationResult
from tests.app_simc_api_test import build_simc_test_client
from tests.app_chat_api_test import browser_session_headers, web_cookies


class WorkbenchApiTest(unittest.TestCase):
    def test_localized_names_share_owner_scoped_results_and_keep_legacy_shape(self):
        from tests.app_simulation_report_test import report_fixture
        from server.app.simulation.report import normalize_simc_report
        snapshot = self.client.post('/api/v2/simc/snapshots', headers=browser_session_headers(), json={
            'sourceUrl': 'https://raider.io/characters/us/area-52/Stormsample'}).json()
        self.client.post('/api/v2/simc/jobs', headers={**browser_session_headers(), 'Idempotency-Key': 'localized-test'},
            json={'snapshotId': snapshot['id'], 'scenario': {'iterations': 100}})
        job = next(iter(self.repository.jobs.values()))
        source = self.repository.get_snapshot(job.user_id, job.snapshot_id)
        provenance = {'snapshotId': str(job.snapshot_id), 'sourceRevision': source.provenance['sourceRevision'],
            'sourceRawSha256': source.raw_sha256, 'profileSha256': 'c' * 64,
            'compilerRevision': job.compiler_revision, 'runtimeRevision': job.runtime_revision, 'scenarioHash': job.scenario_hash}
        identity = {}
        report = normalize_simc_report(json.dumps(report_fixture()), expected_actor='Stormsample', identity_sink=identity)
        self.repository.save_job(replace(job, status=SimulationJobStatus.SUCCEEDED))
        self.repository.save_result(SimulationResult(id=uuid4(), job_id=job.id, user_id=job.user_id,
            profile_sha256='c' * 64, result={'report': report, 'reportIdentity': identity, 'metricName': 'dps',
                'metricValue': report['metric']['value'], 'provenance': provenance},
            primary_metric_name='dps', primary_metric_value=report['metric']['value'],
            compiler_revision=job.compiler_revision, runtime_revision=job.runtime_revision,
            provenance=provenance, created_at=job.created_at))
        path = f'/api/v2/simc/jobs/{job.id}?view=workbench'
        old = self.client.get(path, headers=browser_session_headers())
        self.assertEqual(old.status_code, 200, old.text)
        self.assertEqual(old.json()['result']['report']['schemaVersion'], 1)
        self.assertNotIn('localization', old.json()['result']['report'])
        new_path = path + '&reportLocale=zhCN'
        mini = self.client.get(new_path, headers=browser_session_headers())
        web = self.client.get(new_path, cookies=web_cookies())
        self.assertEqual(mini.status_code, 200, mini.text)
        self.assertEqual(web.status_code, 200, web.text)
        self.assertEqual(mini.json()['result'], web.json()['result'])
        projected = mini.json()['result']['report']
        self.assertEqual(projected['schemaVersion'], 2)
        self.assertEqual(projected['abilities'], report['abilities'])
        self.assertNotIn('reportIdentity', mini.text)
        self.client.cookies.clear()
        self.assertEqual(self.client.get(new_path, headers=browser_session_headers(other=True)).status_code, 404)
        self.assertEqual(self.client.get(new_path).status_code, 401)

    def setUp(self):
        self.client, self.repository, self.queue = build_simc_test_client()

    def tearDown(self):
        self.client.close()

    def test_opt_in_character_and_task_context_preserves_old_contract(self):
        body = {'sourceUrl': 'https://raider.io/characters/us/area-52/Stormsample'}
        old = self.client.post('/api/v2/simc/snapshots', headers=browser_session_headers(), json=body).json()
        snapshot = self.client.post('/api/v2/simc/snapshots?view=workbench', headers=browser_session_headers(), json=body).json()
        self.assertNotIn('character', old)
        self.assertEqual(snapshot['character']['name'], 'Stormsample')
        response = self.client.post('/api/v2/simc/jobs?view=workbench',
            headers={**browser_session_headers(), 'Idempotency-Key': 'workbench-create-1'},
            json={'snapshotId':snapshot['id'], 'scenario':{'iterations':100}})
        self.assertEqual(response.status_code, 202, response.text)
        job = response.json()
        self.assertEqual(job['character']['name'], 'Stormsample')
        self.assertEqual(job['scenario']['iterations'], 100)
        self.assertIsNone(job['metric'])
        legacy = self.client.get('/api/v2/simc/jobs/' + job['id'], headers=browser_session_headers()).json()
        self.assertNotIn('scenario', legacy)
        self.assertNotIn('character', legacy)

    def test_equipment_scenario_is_opt_in_for_older_web_clients(self):
        from server.app.api.routes.simc import _job_summary
        from server.app.simulation.application import SimulationJobView
        snapshot = self.client.post('/api/v2/simc/snapshots', headers=browser_session_headers(), json={
            'sourceUrl': 'https://raider.io/characters/us/area-52/Stormsample'}).json()
        self.client.post('/api/v2/simc/jobs', headers={**browser_session_headers(), 'Idempotency-Key': 'equipment-contract'},
            json={'snapshotId': snapshot['id'], 'scenario': {'iterations': 100}})
        job = next(iter(self.repository.jobs.values()))
        scenario = {'iterations': 100, 'equipmentOverrides': {'trinket1': {
            'itemId': 12345, 'itemLevel': 200, 'bonusIds': [], 'gems': [], 'enchant': None}}}
        view = SimulationJobView(job=job, attempts=(), result=None, scenario=scenario)
        self.assertEqual(_job_summary(view, True)['scenario'], {'iterations': 100})
        self.assertEqual(_job_summary(view, True, 2)['scenario'], scenario)
        self.assertIn('equipmentOverrides', view.scenario)

    def test_runtime_requires_authentication(self):
        self.assertEqual(self.client.get('/api/v2/simc/runtime').status_code, 401)
        with patch('server.app.simulation.application.get_simc_runtime_info', return_value={
            'status':'available','version':'1210-01','gameVersion':'12.1.0','build':'69299',
            'sourceCommit':'a'*40,'runtimeRevision':'simc:test'}):
            response = self.client.get('/api/v2/simc/runtime', headers=browser_session_headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['version'], '1210-01')

    def test_workbench_preserves_valid_legacy_metric_error_without_expanding_legacy_response(self):
        snapshot = self.client.post('/api/v2/simc/snapshots', headers=browser_session_headers(), json={
            'sourceUrl': 'https://raider.io/characters/us/area-52/Stormsample'}).json()
        created = self.client.post('/api/v2/simc/jobs', headers={**browser_session_headers(), 'Idempotency-Key': 'legacy-error-test'},
            json={'snapshotId': snapshot['id'], 'scenario': {'iterations': 100}}).json()
        job = next(iter(self.repository.jobs.values()))
        source = self.repository.get_snapshot(job.user_id, job.snapshot_id)
        provenance = {'snapshotId': str(job.snapshot_id), 'sourceRevision': source.provenance['sourceRevision'],
            'sourceRawSha256': source.raw_sha256, 'profileSha256': 'c' * 64,
            'compilerRevision': job.compiler_revision, 'runtimeRevision': job.runtime_revision, 'scenarioHash': job.scenario_hash}
        self.repository.save_job(replace(job, status=SimulationJobStatus.SUCCEEDED))
        for raw, expected in [(12.5, 12.5), (0, 0), (None, None), (-1, None), (float('inf'), None),
                              (float('nan'), None), (True, None), ('12.5', None), (10 ** 1000, None)]:
            with self.subTest(raw=str(raw)[:40]):
                self.repository.save_result(SimulationResult(id=uuid4(), job_id=job.id, user_id=job.user_id,
                    profile_sha256='c' * 64, result={'metricName': 'dps', 'metricValue': 12345.0,
                        'metricError': raw, 'provenance': provenance},
                    primary_metric_name='dps', primary_metric_value=12345.0,
                    compiler_revision=job.compiler_revision, runtime_revision=job.runtime_revision,
                    provenance=provenance, created_at=job.created_at))
                path = '/api/v2/simc/jobs/' + created['id']
                legacy = self.client.get(path, headers=browser_session_headers()).json()
                self.assertNotIn('metricError', legacy['result'])
                response = self.client.get(path + '?view=workbench', headers=browser_session_headers())
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()['result']
                self.assertIn('metricError', result)
                self.assertEqual(result['metricError'], expected)
                self.assertIsNone(result['report'])
        self.assertEqual(self.client.get(path + '?view=workbench', headers=browser_session_headers(other=True)).status_code, 404)

    def test_talent_scenario_is_opt_in_without_breaking_older_clients(self):
        from server.app.api.routes.simc import _job_summary
        from server.app.simulation.application import SimulationJobView
        body={'sourceUrl':'https://raider.io/characters/us/area-52/Stormsample'}
        snapshot=self.client.post('/api/v2/simc/snapshots',headers=browser_session_headers(),json=body).json()
        response=self.client.post('/api/v2/simc/jobs',headers={**browser_session_headers(),'Idempotency-Key':'talent-version'},
                                  json={'snapshotId':snapshot['id'],'scenario':{}})
        self.assertEqual(response.status_code,202)
        job=next(iter(self.repository.jobs.values()))
        view=SimulationJobView(job=job,result=None,attempts=(),snapshot=self.repository.get_snapshot(job.user_id,job.snapshot_id),
             scenario={'iterations':300,'talentOverrides':{'string':'A'*30},'equipmentOverrides':{},'actionLists':{'default':['lightning_bolt']},'food':'disabled','statBonuses':{'crit':72},'maxTime':20})
        self.assertNotIn('talentOverrides',_job_summary(view,True,1)['scenario'])
        self.assertNotIn('equipmentOverrides',_job_summary(view,True,1)['scenario'])
        self.assertNotIn('talentOverrides',_job_summary(view,True,2)['scenario'])
        self.assertIn('equipmentOverrides',_job_summary(view,True,2)['scenario'])
        self.assertIn('talentOverrides',_job_summary(view,True,3)['scenario'])
        self.assertNotIn('actionLists',_job_summary(view,True,3)['scenario'])
        self.assertIn('actionLists',_job_summary(view,True,4)['scenario'])
        self.assertNotIn('food',_job_summary(view,True,4)['scenario'])
        self.assertEqual(_job_summary(view,True,5)['scenario']['food'], 'disabled')
        self.assertNotIn('statBonuses',_job_summary(view,True,4)['scenario'])
        self.assertNotIn('maxTime',_job_summary(view,True,4)['scenario'])
        self.assertEqual(_job_summary(view,True,5)['scenario']['maxTime'],20)
