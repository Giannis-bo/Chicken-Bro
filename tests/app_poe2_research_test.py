import unittest
from server.app.poe2.research import reserve, status


class Poe2ResearchPolicyTests(unittest.TestCase):
    def test_soft_threshold_and_distinct_candidate_limit(self):
        data={}
        for i in range(60):
            self.assertIsNone(reserve(data, {}, str(i)))
            if i == 29:self.assertTrue(status(data,{})['advice'])
        self.assertEqual(reserve(data,{},'extra')['errorCode'],'POE2_RESEARCH_SCOPE_LIMIT')
        self.assertEqual(len(data['candidates']),60)
        self.assertIsNone(reserve(data,{},'0'))  # legitimate failed retry: no new candidate
        self.assertEqual(len(data['candidates']),60)

    def test_turn_limit_and_attempt_cap(self):
        data={}; work={'calls':4}
        for _ in range(12):self.assertIsNone(reserve(data,work,'same'))
        self.assertEqual(work['calls'],4)
        self.assertEqual(reserve(data,work,'same')['errorCode'],'POE2_RESEARCH_TURN_LIMIT')
        for _ in range(108):self.assertIsNone(reserve(data,{},'same'))
        self.assertEqual(reserve(data,{},'same')['errorCode'],'POE2_RESEARCH_SCOPE_LIMIT')
        self.assertEqual(data['attempts'],120)
