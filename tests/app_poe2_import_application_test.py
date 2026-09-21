import unittest
from unittest.mock import Mock, patch
from uuid import uuid4
from server.app.identity.domain import Principal
from server.app.poe2.imports.application import ImportApplication
from server.app.poe2.imports.worker import ImportWorker

class ImportApplicationTest(unittest.TestCase):
    def test_ninja_does_not_fetch(self):
        repo=Mock(); app=ImportApplication(repo)
        with patch('server.app.poe2.imports.application.packet',side_effect=lambda x:x):
            app.create(Principal(uuid4(),'web_cookie'),'ninja','https://poe.ninja/poe2/profile/a/league/character/c','key')
        self.assertEqual(repo.create.call_args.args[2]['status'],'needs_input')
        self.assertEqual(repo.create.call_args.args[2]['next_action'],'supply_pob')

    def test_unconfigured_wegame_blocked(self):
        repo=Mock(); row=Mock(id=uuid4(),attempt=1,source_xml=None,provider='wegame')
        repo.claim.return_value=row
        ImportWorker(repo,Mock()).run_once()
        self.assertEqual(repo.complete.call_args.args[3]['status'],'blocked')

    def test_collector_uses_claimed_owner_and_unknown_mapping_never_converts(self):
        from server.app.poe2.imports.mapping import map
        from tests.app_poe2_mapping_test import synthetic_snapshot
        snapshot=synthetic_snapshot();snapshot['equipment'][0]['explicitMods'].append({'description':'unknown'})
        repo=Mock(); row=Mock(id=uuid4(),user_id=uuid4(),attempt=1,source_xml=None,provider='wegame',
                             canonical_url='https://poe2.qq.com/act/a20240819poe2/index.html#/role/share?share_code='+'a'*64)
        repo.claim.return_value=row
        collect=Mock(return_value=snapshot);convert=Mock()
        with patch('server.app.poe2.imports.worker.parse_character_url',return_value=object()):
            ImportWorker(repo,Mock(),collect=collect,map=map,convert=convert).run_once()
        self.assertEqual(collect.call_args.kwargs,{'owner_id':row.user_id})
        convert.assert_not_called()
        self.assertEqual(repo.complete.call_args.args[3]['status'],'needs_input')
