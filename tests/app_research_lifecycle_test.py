import json
import unittest
from server.app.chickenbro.research_budget import ResearchBudget


class ResearchStateTest(unittest.TestCase):
    def test_existing_research_reuses_actor_with_legacy_realm_spelling(self):
        # Shape observed in production before the fix: ten RIO identities and
        # a WCL actor already bound to the same character with a compact realm.
        state = {
            'players': ['character:us:bleeding-hollow:shadarek'] + [
                f'character:us:illidan:p{n}' for n in range(9)],
            'slots': {'ranking:0':'character:us:bleeding-hollow:shadarek'},
            'report_actors': {'AAAAAAAAAAAAAAAA:10:472':'character:us:bleedinghollow:shadarek'},
            'report_players': {'AAAAAAAAAAAAAAAA:10':{'character:us:bleeding-hollow:shadarek':'shadarek'}},
            'fights': ['AAAAAAAAAAAAAAAA:10'],
        }
        restored = ResearchBudget.restore(json.loads(json.dumps(state)))
        url = 'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=10&source=472'
        self.assertIsNone(restored.reserve('warcraftlogs', url, {'view':'overview'})[0])
        self.assertEqual(len(restored.players), 10)
        # Repeating a follow-up after another process reload must remain free
        # of new player charges, including when old ranking aliases are reused.
        restored = ResearchBudget.restore(json.loads(json.dumps(restored.dump())))
        self.assertIsNone(restored.reserve('raiderio', 'https://raider.io/characters/us/bleeding-hollow/Shadarek', {})[0])
        restored.observe(None, {'facts':[{'reportCode':'AAAAAAAAAAAAAAAA','fightId':10,
            'actors':[{'id':473,'name':'Shadarek'}]}]})
        self.assertIsNone(restored.reserve('warcraftlogs', url.replace('472','473'), {'view':'overview'})[0])
        for region, realm, name in [('eu','bleeding-hollow','Shadarek'),
                                     ('us','illidan','Shadarek'),
                                     ('us','bleeding-hollow','Shádarek')]:
            with self.subTest(region=region, realm=realm, name=name):
                error, _ = restored.reserve('warcraftlogs_character', 'character',
                    {'region':region,'realm':realm,'name':name})
                self.assertEqual(error['errorCode'], 'RESEARCH_BUDGET_EXCEEDED')

    def test_serialized_state_retains_cross_source_limits(self):
        budget = ResearchBudget()
        budget.reserve('raiderio_rankings', 'rankings', {'limit': 10})
        self.assertTrue(hasattr(budget, 'dump'), 'research budget must survive capability renewal')
        restored = ResearchBudget.restore(json.loads(json.dumps(budget.dump())))
        error, _ = restored.reserve('raiderio', 'https://raider.io/characters/us/area-52/another', {})
        self.assertEqual(error['errorCode'], 'RESEARCH_BUDGET_EXCEEDED')

    def test_identity_receipt_survives_reload(self):
        budget = ResearchBudget()
        _, receipt = budget.reserve('raiderio_rankings', 'rankings', {'limit': 10})
        url = 'https://raider.io/characters/us/area-52/known'
        budget.observe(receipt, {'facts': [{'character': {'url': url}}]})
        self.assertTrue(hasattr(budget, 'dump'), 'research receipt must survive process renewal')
        restored = ResearchBudget.restore(json.loads(json.dumps(budget.dump())))
        self.assertIsNone(restored.reserve('raiderio', url, {})[0])
