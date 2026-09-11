import unittest
from unittest.mock import patch
from server.app.chickenbro.research_budget import ResearchBudget
from server.app.chickenbro.source_gateway import ChickenbroSourceGateway, ServerConfiguredSourceQuery

class ResearchCompletionTest(unittest.TestCase):
    def test_local_invalid_wcl_options_do_not_spend_budget(self):
        budget=ResearchBudget()
        service=ServerConfiguredSourceQuery(wcl_reader=lambda _:self.fail('invalid request reached upstream'))
        gateway=ChickenbroSourceGateway(query_service=service,research_budget=budget)
        result=gateway.query(gateway.issue_capability(),'warcraftlogs','https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1&source=2',{'view':'unknown'})
        self.assertEqual(result.get('errorCode'),'SOURCE_INVALID_ARGUMENTS')
        self.assertEqual(budget.calls,0)

    def test_report_actor_and_character_are_one_player(self):
        budget=ResearchBudget();url='https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1&source=2'
        budget.reserve('warcraftlogs',url,{'view':'overview'})
        budget.observe([],{'status':'verified','facts':[{'reportCode':'AAAAAAAAAAAAAAAA','fightId':'1','players':[{'id':2,'name':'example','server':'realm','region':'US'}]}]})
        budget.reserve('raiderio','https://raider.io/characters/us/realm/example',{})
        self.assertEqual(len(budget.players),1)

    def test_healing_aggregate_does_not_spend_event_rows(self):
        budget=ResearchBudget()
        budget.reserve('warcraftlogs','https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1&source=2',{'view':'healing'})
        self.assertEqual(budget.events,0)

    def test_all_local_rejections_are_free(self):
        budget=ResearchBudget();gateway=ChickenbroSourceGateway(query_service=ServerConfiguredSourceQuery(),research_budget=budget)
        token=gateway.issue_capability()
        for provider,target,options in [('warcraftlogs_rankings','wrong-target',{}),('warcraftlogs_rankings','rankings',{'limit':100}),('raiderio_rankings','rankings',{}),('warcraftlogs_character','character',{}),('raiderio_batch','characters',{'targets':['bad']}),('warcraftlogs','https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1',{'view':'healing'}),('unknown','x',{})]:
            with self.subTest(provider=provider,target=target):
                self.assertEqual(gateway.query(token,provider,target,options)['errorCode'],'SOURCE_INVALID_ARGUMENTS')
        self.assertEqual(budget.calls,0)

    def test_history_reserves_scope_without_spending_calls(self):
        budget=ResearchBudget();gateway=ChickenbroSourceGateway(query_service=ServerConfiguredSourceQuery(),research_budget=budget)
        token=gateway.issue_capability()
        facts=[{'reportCode':'AAAAAAAAAAAAAAAA','fightId':n,'players':[{'id':n}]} for n in range(1,5)]
        result=gateway.seed_evidence(token,{'status':'verified','facts':facts})
        self.assertEqual(len(result['facts']),3)
        self.assertEqual(len(budget.fights),3)
        self.assertEqual(budget.calls,0)
        error,_=budget.reserve('warcraftlogs','https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=5&source=5',{'view':'overview'})
        self.assertEqual(error['errorCode'],'RESEARCH_BUDGET_EXCEEDED')

    def test_ended_scope_reuse_does_not_expand(self):
        budget=ResearchBudget();url='https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1&source=2'
        self.assertIsNone(budget.reserve_scope('warcraftlogs',url,{'view':'overview'}))
        self.assertIsNone(budget.reserve_scope('warcraftlogs',url,{'view':'overview'},ended=True))
        self.assertIsNotNone(budget.reserve_scope('warcraftlogs',url.replace('source=2','source=3'),{'view':'overview'},ended=True))
        self.assertEqual(budget.calls,0)
