import unittest
from unittest.mock import patch

from tests.app_simc_api_test import build_simc_test_client
from tests.app_chat_api_test import mini_headers


class WorkbenchApiTest(unittest.TestCase):
    def setUp(self):
        self.client, self.repository, self.queue = build_simc_test_client()

    def tearDown(self):
        self.client.close()

    def test_opt_in_character_and_task_context_preserves_old_contract(self):
        body = {'sourceUrl': 'https://raider.io/characters/us/area-52/Stormsample'}
        old = self.client.post('/api/v2/simc/snapshots', headers=mini_headers(), json=body).json()
        snapshot = self.client.post('/api/v2/simc/snapshots?view=workbench', headers=mini_headers(), json=body).json()
        self.assertNotIn('character', old)
        self.assertEqual(snapshot['character']['name'], 'Stormsample')
        response = self.client.post('/api/v2/simc/jobs?view=workbench',
            headers={**mini_headers(), 'Idempotency-Key': 'workbench-create-1'},
            json={'snapshotId':snapshot['id'], 'scenario':{'iterations':100}})
        self.assertEqual(response.status_code, 202, response.text)
        job = response.json()
        self.assertEqual(job['character']['name'], 'Stormsample')
        self.assertEqual(job['scenario']['iterations'], 100)
        self.assertIsNone(job['metric'])
        legacy = self.client.get('/api/v2/simc/jobs/' + job['id'], headers=mini_headers()).json()
        self.assertNotIn('scenario', legacy)
        self.assertNotIn('character', legacy)

    def test_runtime_requires_authentication(self):
        self.assertEqual(self.client.get('/api/v2/simc/runtime').status_code, 401)
        with patch('server.app.simulation.application.get_simc_runtime_info', return_value={
            'status':'available','version':'1210-01','gameVersion':'12.1.0','build':'69299',
            'sourceCommit':'a'*40,'runtimeRevision':'simc:test'}):
            response = self.client.get('/api/v2/simc/runtime', headers=mini_headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['version'], '1210-01')
