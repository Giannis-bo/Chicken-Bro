import unittest
from contextlib import contextmanager
from server.app.chickenbro.research_lifecycle import PostgresResearchBudget

class ResearchStatusTest(unittest.TestCase):
    def test_remaining_scope_is_cumulative_but_execution_usage_is_per_run(self):
        budget=object.__new__(PostgresResearchBudget)
        budget.run_id='run';budget.user_id='owner'
        class Cursor:
            def execute(self,*args): pass
            def fetchone(self): return ({'calls':2,'events':300},)
        @contextmanager
        def locked():
            yield Cursor(),'research','active',{'source':{'calls':50,'players':['a','b'],'fights':['a:1'],'groups':['g']},'submissions':['j1','j2','j3']}
        budget._locked=locked
        result=budget.status()
        self.assertEqual(result.get('scopeRemaining'),{'players':8,'fights':2,'groups':2,'simulations':None})
        self.assertEqual(result.get('executionRemaining'),{'sourceCalls':46,'eventUnits':19700})
        self.assertEqual(result['sourceCalls'],50)

    def test_historical_simulations_do_not_block_new_submissions(self):
        budget = object.__new__(PostgresResearchBudget)
        data = {'submissions': ['0', '1', '2', '3']}
        @contextmanager
        def locked():
            yield None, 'research', 'active', data
        budget._locked = locked
        budget._save = lambda *args: None
        self.assertIsNone(budget.reserve_simulation('4'))
        self.assertIsNone(budget.reserve_simulation('0'))
        self.assertEqual(data['submissions'], ['0', '1', '2', '3', '4'])
