import unittest
from unittest.mock import patch
from server.app.chickenbro.character_discovery import discover_wcl_character
from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery
from server.app.simulation.sources import InvalidSourceLink

SERVER = {'id': 584, 'name': '凤凰之神', 'slug': 'alar', 'region': {'slug': 'CN'}}
class CharacterDiscoveryTest(unittest.TestCase):
    def query(self, query, variables):
        if 'worldData' in query:
            return {'worldData': {'server': SERVER}}
        return {'characterData': {'character': {'id': 10, 'name': 'Fusionbolt', 'hidden': False,
            'server': SERVER, 'recentReports': {'data': [{'code': 'JMy4CPTmR2WXrQ1F', 'title': 'test', 'startTime': 1000, 'endTime': 2000}], 'current_page': variables['page'], 'has_more_pages': True}}}}

    def test_name_to_report_preserves_identity_and_pagination(self):
        with patch('server.app.chickenbro.character_discovery._graphql', side_effect=self.query):
            result = ServerConfiguredSourceQuery().query('warcraftlogs_character', 'character', {'name': 'Fusionbolt', 'realm': '凤凰之神', 'region': 'cn', 'page': 2})
        self.assertEqual(result['status'], 'source_reference')
        self.assertEqual(result['facts'][0]['character']['realmSlug'], 'alar')
        self.assertEqual(result['facts'][0]['reports'][0]['url'], 'https://www.warcraftlogs.com/reports/JMy4CPTmR2WXrQ1F')
        self.assertEqual(result['pagination']['nextPage'], 3)

    def test_invalid_inputs_do_not_query(self):
        with patch('server.app.chickenbro.character_discovery._graphql') as query:
            for change in [{'region': 'world'}, {'page': True}, {'limit': 1000}, {'owner': 'someone'}, {'name': 'https://evil.test'}, {'region': ''}]:
                with self.subTest(change=change), self.assertRaises(InvalidSourceLink):
                    discover_wcl_character({'name':'A','realm':'alar','region':'cn',**change})
            query.assert_not_called()

    def test_unknown_hidden_wrong_identity_and_upstream_failure(self):
        for label, expected in [('missing','not_found'), ('hidden','access_restricted'), ('wrong','identity_mismatch'), ('error','unavailable')]:
            def query(q,v):
                if 'worldData' in q: return self.query(q,v)
                if label == 'error': raise RuntimeError('secret must not escape')
                data=self.query(q,v)
                char=data['characterData']['character']
                if label == 'missing': data['characterData']['character']=None
                if label == 'hidden': char['hidden']=True
                if label == 'wrong': char['name']='SomeoneElse'
                return data
            with self.subTest(label=label), patch('server.app.chickenbro.character_discovery._graphql',side_effect=query):
                result=discover_wcl_character({'name':'Fusionbolt','realm':'alar','region':'cn'})
                self.assertEqual(result['status'],expected)
                self.assertEqual(result['facts'],[])
                self.assertNotIn('secret',str(result))

    def test_mcp_call_returns_discovered_reports_through_gateway(self):
        from server import chickenbro_native_mcp as mcp
        service=ServerConfiguredSourceQuery()
        with patch.object(mcp,'query_source_gateway',side_effect=service.query), patch('server.app.chickenbro.character_discovery._graphql',side_effect=self.query):
            response=mcp.handle_rpc_request({'id':1,'method':'tools/call','params':{
                'name':'query_warcraftlogs_character','arguments':{'name':'Fusionbolt','realm':'凤凰之神','region':'cn'}}})
        import json
        packet=json.loads(response['result']['content'][0]['text'])
        self.assertEqual(packet['facts'][0]['reports'][0]['code'],'JMy4CPTmR2WXrQ1F')

    def test_empty_page_preserves_character_without_claiming_nonexistence(self):
        def query(q,v):
            data=self.query(q,v)
            if 'characterData' in data:
                data['characterData']['character']['recentReports'].update(data=[],has_more_pages=False)
            return data
        with patch('server.app.chickenbro.character_discovery._graphql',side_effect=query):
            result=discover_wcl_character({'name':'Fusionbolt','realm':'alar','region':'cn'})
        self.assertEqual(result['facts'][0]['character']['name'],'Fusionbolt')
        self.assertEqual(result['facts'][0]['reports'],[])
        self.assertIsNone(result['pagination']['nextPage'])

    def test_wrong_server_is_rejected(self):
        def query(q,v):
            data=self.query(q,v)
            if 'characterData' in data:
                data['characterData']['character']['server']={**SERVER,'id':999}
            return data
        with patch('server.app.chickenbro.character_discovery._graphql',side_effect=query):
            result=discover_wcl_character({'name':'Fusionbolt','realm':'alar','region':'cn'})
        self.assertEqual(result['status'],'identity_mismatch')
