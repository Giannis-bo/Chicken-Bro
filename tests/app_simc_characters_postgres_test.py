"""Real transactions catch cross-account leakage and concurrent binding overflows."""
import importlib
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier
from uuid import uuid4
import unittest

from server.app.identity.domain import Principal
from server.app.simulation.application import SimulationApplicationError
from server.app.simulation.characters import CharacterBindings
from server.app.simulation.repository import PostgresSimulationRepository
from tests.app_simc_api_test import build_simc_test_client
from tests.app_chat_api_test import browser_session_headers


@unittest.skipUnless(os.environ.get('WOW_PG_TEST_DSN_V2'), 'isolated PostgreSQL required')
class SimcCharactersPostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.dsn = os.environ['WOW_PG_TEST_DSN_V2']
        with psycopg.connect(cls.dsn, autocommit=True) as connection:
            importlib.import_module('server.migrations.product.apply').apply_product_migrations(
                connection, Path(__file__).resolve().parents[1] / 'server/migrations/product')

    def setUp(self):
        import psycopg
        self.connect = lambda: psycopg.connect(self.dsn)
        self.owner, self.other = uuid4(), uuid4()
        with self.connect() as connection:
            connection.execute('INSERT INTO identity.users(id) VALUES (%s),(%s)', (self.owner, self.other))
        self.principal = Principal(self.owner, 'web_cookie')
        self.other_principal = Principal(self.other, 'web_cookie')
        self.repo = PostgresSimulationRepository(self.connect)
        self.service = CharacterBindings(self.repo)
        client, memory, _ = build_simc_test_client()
        with client:
            response = client.post('/api/v2/simc/snapshots', headers=browser_session_headers(),
                json={'sourceUrl': 'https://raider.io/characters/us/area-52/Stormsample'})
            self.assertEqual(response.status_code, 201)
        template = next(iter(memory.snapshots.values()))
        self.snapshots = [replace(template, id=uuid4(), user_id=self.owner,
            source_url=f'https://raider.io/characters/us/area-52/Role{i}', source_key=f'us|area-52|Role{i}',
            snapshot={**template.snapshot, 'character': {**template.snapshot['character'], 'name': f'Role{i}'}})
            for i in range(4)]

    def test_concurrent_distinct_binds_never_exceed_three(self):
        gate = Barrier(4)
        def bind(snapshot):
            gate.wait(timeout=10)
            try:
                self.service.bind(self.principal, snapshot)
                return 'ok'
            except SimulationApplicationError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(bind, self.snapshots))
        self.assertEqual(results.count('ok'), 3)
        self.assertEqual(results.count('CHARACTER_LIMIT_REACHED'), 1)
        collection = CharacterBindings(PostgresSimulationRepository(self.connect)).read(self.principal)
        self.assertEqual(len(collection['items']), 3)
        self.assertIn(collection['selectedId'], [row['id'] for row in collection['items']])
        self.assertEqual(self.service.read(self.other_principal), {'items': [], 'selectedId': None})

    def test_duplicate_binds_selection_and_unbinding_persist_across_connections(self):
        gate = Barrier(3)
        def bind(_):
            gate.wait(timeout=10)
            return self.service.bind(self.principal, self.snapshots[0])
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = list(pool.map(bind, range(3)))
        self.assertEqual(len({row['selectedId'] for row in rows}), 1)
        first_id = rows[0]['selectedId']
        second = self.service.bind(self.principal, self.snapshots[1])
        second_id = second['selectedId']
        self.assertNotEqual(first_id, second_id)
        self.service.change(self.principal, first_id)
        self.assertEqual(CharacterBindings(PostgresSimulationRepository(self.connect)).read(self.principal)['selectedId'], first_id)
        for unbind in (False, True):
            with self.assertRaises(SimulationApplicationError) as caught:
                self.service.change(self.other_principal, first_id, unbind=unbind)
            self.assertEqual(caught.exception.code, 'CHARACTER_NOT_BOUND')
        self.assertEqual(self.service.change(self.principal, first_id, unbind=True)['selectedId'], second_id)
        self.assertEqual(len(self.service.bind(self.principal, self.snapshots[0])['items']), 2)

    def test_runtime_role_can_persist_shortcuts_without_deleting_history(self):
        import psycopg
        from contextlib import contextmanager
        @contextmanager
        def runtime_connection():
            with psycopg.connect(self.dsn) as connection:
                connection.execute('SET ROLE wow_app')
                yield connection
        service = CharacterBindings(PostgresSimulationRepository(runtime_connection))
        bound = service.bind(self.principal, self.snapshots[0])
        self.assertEqual(len(service.read(self.principal)['items']), 1)
        self.assertEqual(service.change(self.principal, bound['selectedId'], unbind=True)['items'], [])
