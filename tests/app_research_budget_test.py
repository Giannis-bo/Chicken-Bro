import unittest
from concurrent.futures import ThreadPoolExecutor
from server.app.chickenbro.source_gateway import ChickenbroSourceGateway


class Service:
    def __init__(self):
        self.calls = []
    def query(self, provider, target, options=None):
        self.calls.append((provider, target, options))
        return {'status': 'source_reference', 'facts': []}


class ResearchBudgetTest(unittest.TestCase):
    def setUp(self):
        self.service = Service()
        self.gateway = ChickenbroSourceGateway(query_service=self.service)
        self.token = self.gateway.issue_capability()
    def query(self, provider, target='rankings', **options):
        return self.gateway.query(self.token, provider, target, options)
    def blocked(self, result):
        self.assertEqual(result.get('errorCode'), 'RESEARCH_BUDGET_EXCEEDED')
        self.assertEqual(result['facts'], [])
    def test_top11_refused_before_source_work(self):
        self.blocked(self.query('raiderio_rankings', limit=11))
        self.assertEqual(len(self.service.calls), 0)
    def test_rank_pages_and_providers_share_total(self):
        self.assertEqual(self.query('raiderio_rankings', limit=6)['status'], 'source_reference')
        self.assertEqual(self.query('warcraftlogs_rankings', encounterId=1, limit=4)['status'], 'source_reference')
        self.blocked(self.query('raiderio_rankings', offset=10, limit=1))
        self.assertEqual(len(self.service.calls), 2)
    def test_parallel_single_characters_cannot_exceed_ten(self):
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda n: self.query('raiderio', f'https://raider.io/characters/us/area-52/p{n}'), range(12)))
        self.assertEqual(sum(r['status'] == 'source_reference' for r in results), 10)
        self.assertEqual(len(self.service.calls), 10)
    def test_repeated_character_is_not_a_new_player(self):
        for _ in range(12):
            self.assertEqual(self.query('raiderio', 'https://raider.io/characters/us/area-52/same')['status'], 'source_reference')
    def test_batch_is_reserved_atomically(self):
        urls = [f'https://raider.io/characters/us/area-52/p{n}' for n in range(11)]
        self.blocked(self.query('raiderio_batch', 'characters', targets=urls))
        self.assertEqual(len(self.service.calls), 0)
    def test_fourth_comparison_group_blocked(self):
        for n in range(3):
            self.query('warcraftlogs_rankings', encounterId=n+1, limit=1)
        self.blocked(self.query('warcraftlogs_rankings', encounterId=4, limit=1))
    def test_batch_cannot_expand_past_three_fights(self):
        url = 'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA'
        self.query('warcraftlogs_batch', 'reports', queries=[{'target':f'{url}?fight={n}', 'options':{'view':'overview'}} for n in range(1,4)])
        self.blocked(self.query('warcraftlogs', url+'?fight=4', view='overview'))
        self.assertEqual(len(self.service.calls), 1)
    def test_new_capability_has_independent_budget(self):
        self.query('raiderio_rankings', limit=10)
        token = self.gateway.issue_capability()
        self.assertEqual(self.gateway.query(token, 'raiderio_rankings', 'rankings', {'limit':10})['status'], 'source_reference')
    def test_failed_samples_still_consume_slots(self):
        self.query('raiderio_rankings', limit=10)
        self.blocked(self.query('raiderio_rankings', offset=10, limit=1))
    def test_catalog_does_not_count_as_player_sampling(self):
        for zone in range(4):
            self.assertEqual(self.query('warcraftlogs_rankings', zoneId=zone+1)['status'], 'source_reference')
        self.assertEqual(self.query('raiderio_rankings', limit=10)['status'], 'source_reference')
    def test_event_pagination_has_total_work_bound(self):
        url = 'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1&source=2'
        for n in range(4):
            self.assertEqual(self.query('warcraftlogs', url, view='statistics', limit=1000, maxPages=5, startTime=n*10000)['status'], 'source_reference')
        self.blocked(self.query('warcraftlogs', url, view='events', limit=1, startTime=50000))
    def test_ranked_profiles_reuse_reservations_but_eleventh_player_is_blocked(self):
        urls = [f'https://raider.io/characters/us/area-52/p{n}' for n in range(10)]
        self.service.query = lambda *a, **kw: {'status':'source_reference', 'facts':[{'character':{'url':url}} for url in urls]}
        self.query('raiderio_rankings', limit=10)
        self.service.query = lambda *a, **kw: {'status':'source_reference', 'facts':[]}
        for url in urls:
            self.assertEqual(self.query('raiderio', url)['status'], 'source_reference')
        self.blocked(self.query('raiderio', urls[0]+'other'))
    def test_source_call_budget_counts_batch_members(self):
        url = 'https://raider.io/characters/us/area-52/same'
        for _ in range(16):
            self.assertEqual(self.query('raiderio_batch', 'characters', targets=[url]*3)['status'], 'source_reference')
        self.blocked(self.query('raiderio', url))
    def test_sixth_public_page_blocked_continuation_allowed(self):
        for n in range(5):
            self.query('public_web', f'https://example.com/{n}')
        self.assertEqual(self.query('public_web', 'https://example.com/0', start=6000)['status'], 'source_reference')
        self.blocked(self.query('public_web', 'https://example.com/5'))
    def test_search_reserves_both_pages(self):
        self.query('public_web', 'wow talent guide')
        self.query('public_web', 'wow talent patch notes')
        self.query('public_web', 'https://example.com/last')
        self.blocked(self.query('public_web', 'wow more guides'))
    def test_server_public_web_is_available_through_authenticated_gateway(self):
        from unittest.mock import patch
        from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery
        gateway = ChickenbroSourceGateway(query_service=ServerConfiguredSourceQuery())
        token = gateway.issue_capability()
        with patch('server.chickenbro_public_web_research.build_public_web_research_tool_result', return_value={'status':'source_reference', 'facts':[]}) as fetch:
            result = gateway.query(token, 'public_web', 'https://example.com/a', {'start':6000})
        self.assertEqual(result['status'], 'source_reference')
        self.assertEqual(fetch.call_args.args, ({'target':'https://example.com/a', 'start':6000},))
        self.assertIsNotNone(fetch.call_args.kwargs['state'])
    def test_public_web_rate_state_is_isolated_between_generations(self):
        from unittest.mock import patch
        from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery
        from server.chickenbro_public_web_research import build_public_web_research_tool_result as read
        def local_read(intent, *, state=None):
            return read(intent, state=state, fetcher=lambda *a, **kw:'<article>Verified guide text.</article>', clock=lambda:10)
        gateway = ChickenbroSourceGateway(query_service=ServerConfiguredSourceQuery())
        first, second = gateway.issue_capability(), gateway.issue_capability()
        with patch('server.chickenbro_public_web_research.build_public_web_research_tool_result', side_effect=local_read):
            for n in range(8):
                gateway.query(first, 'public_web', 'https://example.com/a', {'start':n})
            result = gateway.query(second, 'public_web', 'https://example.com/b')
        self.assertEqual(result['status'], 'source_reference')
    def test_ranked_wcl_followup_requires_observed_actor_match(self):
        url = 'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1'
        rows = [{'name':f'p{n}','server':{'name':'area-52','region':'us'},'reportUrl':url} for n in range(10)]
        self.service.query = lambda *a, **kw: {'status':'source_reference','rankings':rows,'facts':[]}
        self.query('warcraftlogs_rankings', encounterId=1, limit=10)
        self.service.query = lambda *a, **kw: {'status':'verified', 'facts':[{'reportCode':'AAAAAAAAAAAAAAAA','fightId':1,'actors':[{'id':42,'name':'p0'},{'id':43,'name':'stranger'}]}]}
        self.query('warcraftlogs', url, view='overview')
        self.assertEqual(self.query('warcraftlogs', url+'&source=42', view='events')['status'], 'verified')
        self.blocked(self.query('warcraftlogs', url+'&source=43', view='events'))
    def test_rank_reservation_does_not_authorize_arbitrary_actor(self):
        url = 'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1'
        self.service.query = lambda *a, **kw: {'status':'source_reference','rankings':[{'name':f'p{n}','server':{'name':'realm','region':'us'},'reportUrl':url} for n in range(10)],'facts':[]}
        self.query('warcraftlogs_rankings', encounterId=1, limit=10)
        self.blocked(self.query('warcraftlogs', url+'&source=999', view='events'))
    def test_requerying_live_rank_positions_cannot_replace_counted_players(self):
        self.service.query = lambda *a, **kw: {'status':'source_reference','facts':[{'character':{'url':f'https://raider.io/characters/us/realm/old{n}'}} for n in range(10)]}
        self.query('raiderio_rankings', limit=10)
        self.blocked(self.query('raiderio_rankings', limit=10))
    def test_expired_research_time_stops_new_source_work(self):
        from unittest.mock import patch
        with patch('server.app.chickenbro.research_budget.monotonic', return_value=0):
            gateway = ChickenbroSourceGateway(query_service=self.service)
            token = gateway.issue_capability()
        with patch('server.app.chickenbro.research_budget.monotonic', return_value=360):
            self.blocked(gateway.query(token, 'raiderio_rankings', 'rankings', {'limit':1}))
        self.assertEqual(self.service.calls, [])
    def test_report_directory_does_not_consume_a_deep_fight(self):
        url = 'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA'
        self.query('warcraftlogs', url)
        for n in range(1,4):
            self.assertEqual(self.query('warcraftlogs', url+f'?fight={n}', view='overview')['status'], 'source_reference')
    def test_report_wide_event_window_requires_a_specific_fight(self):
        self.blocked(self.query('warcraftlogs', 'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA', view='events', startTime=0, endTime=900000))
        self.assertEqual(self.service.calls, [])
