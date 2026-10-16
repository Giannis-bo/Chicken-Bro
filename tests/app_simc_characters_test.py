"""Character input and account binding contracts; no engine execution."""
from copy import deepcopy
from dataclasses import replace
from server.app.simulation.domain import SourceProvider
from uuid import uuid4
import unittest

from tests.app_simc_api_test import build_simc_test_client
from tests.app_chat_api_test import browser_session_headers


class SimcCharactersApiTest(unittest.TestCase):
    def setUp(self):
        self.client, self.repository, _ = build_simc_test_client()
        self.characters = {}
        self.repository.read_characters = lambda owner: deepcopy(self.characters.get(owner, {"items": [], "selectedId": None}))
        def mutate(owner, operation):
            value = operation(self.repository.read_characters(owner))
            self.characters[owner] = deepcopy(value)
            return value
        self.repository.mutate_characters = mutate
        self.headers = browser_session_headers()

    def tearDown(self):
        self.client.close()

    def snapshot(self, name='Stormsample', realm='area-52', region='us'):
        return self.client.post('/api/v2/simc/snapshots', headers=self.headers,
            json={'character': {'name': name, 'realm': realm, 'region': region}})

    def bind(self, snapshot_id):
        return self.client.post('/api/v2/simc/characters', headers=self.headers, json={'snapshotId': snapshot_id})

    def test_manual_input_defaults_to_cn_and_encodes_chinese_safely(self):
        response = self.client.post('/api/v2/simc/snapshots', headers=self.headers,
            json={'character': {'name': ' 炸鸡 ', 'realm': ' 白银之手 '}})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['sourceUrl'], 'https://raider.io/characters/cn/%E7%99%BD%E9%93%B6%E4%B9%8B%E6%89%8B/%E7%82%B8%E9%B8%A1')

    def test_manual_rejects_invalid_fields_and_ambiguous_source_without_writing_snapshot(self):
        for character in ({'name': '', 'realm': 'x'}, {'name': 'x', 'realm': 'x', 'region': 'xx'},
                          {'name': 'x/y', 'realm': 'x'}, {'name': 'x', 'realm': 'x\n'}):
            response = self.client.post('/api/v2/simc/snapshots', headers=self.headers, json={'character': character})
            self.assertEqual(response.status_code, 422, response.text)
        response = self.client.post('/api/v2/simc/snapshots', headers=self.headers,
            json={'sourceUrl': 'https://raider.io/characters/us/area-52/Stormsample', 'character': {'name': 'x', 'realm': 'y'}})
        self.assertEqual(response.status_code, 422)
        self.assertFalse(self.repository.snapshots)

    def test_binding_is_persistent_deduplicated_and_selected(self):
        snapshot = self.snapshot()
        self.assertEqual(snapshot.status_code, 201, snapshot.text)
        bound = self.bind(snapshot.json()['id'])
        self.assertEqual(bound.status_code, 200, bound.text)
        payload = bound.json()
        self.assertEqual(len(payload['items']), 1)
        self.assertEqual(payload['selectedId'], payload['items'][0]['id'])
        self.assertEqual(payload['items'][0]['name'], 'Stormsample')
        self.assertNotIn('user_id', bound.text)
        self.assertEqual(self.bind(snapshot.json()['id']).json(), payload)
        self.assertEqual(self.client.get('/api/v2/simc/characters', headers=self.headers).json(), payload)

    def test_binding_requires_own_snapshot_and_mutations_require_csrf(self):
        missing = self.bind(str(uuid4()))
        self.assertEqual(missing.status_code, 404)
        snapshot = self.snapshot().json()
        owner, sid = next(iter(self.repository.snapshots))
        self.repository.snapshots[(uuid4(), sid)] = self.repository.snapshots.pop((owner, sid))
        self.assertEqual(self.bind(snapshot['id']).status_code, 404)
        response = self.client.post('/api/v2/simc/characters', json={'snapshotId': snapshot['id']})
        self.assertIn(response.status_code, (401, 403))

    def test_research_snapshot_cannot_poison_raiderio_shortcuts(self):
        snapshot = self.snapshot().json()
        key = next(iter(self.repository.snapshots))
        self.repository.snapshots[key] = replace(self.repository.snapshots[key], provider=SourceProvider.WARCRAFTLOGS,
            source_url='https://www.warcraftlogs.com/reports/AbCd1234')
        response = self.bind(snapshot['id'])
        self.assertEqual(response.status_code, 409, response.text)
        self.assertFalse(self.characters)

    def test_select_and_unbind_are_owner_scoped_and_keep_history(self):
        snapshot = self.snapshot().json()
        payload = self.bind(snapshot['id']).json()
        bound_id = payload['items'][0]['id']
        for suffix in ('select', 'unbind'):
            response = self.client.post(f'/api/v2/simc/characters/{uuid4()}/{suffix}', headers=self.headers)
            self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(self.client.post(f'/api/v2/simc/characters/{bound_id}/select', headers=self.headers).json()['selectedId'], bound_id)
        cleared = self.client.post(f'/api/v2/simc/characters/{bound_id}/unbind', headers=self.headers)
        self.assertEqual(cleared.json(), {'items': [], 'selectedId': None})
        self.assertEqual(len(self.repository.snapshots), 1)
        self.assertEqual(self.bind(snapshot['id']).status_code, 200)
