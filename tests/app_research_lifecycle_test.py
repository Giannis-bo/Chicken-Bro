import json
import unittest
from server.app.chickenbro.research_budget import ResearchBudget


class ResearchStateTest(unittest.TestCase):
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
