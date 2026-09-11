import unittest
class UsageTest(unittest.TestCase):
    def test_only_nonnegative_numeric_provider_usage_is_retained(self):
        from server.app.chickenbro.codex_stdio import clean_token_usage
        self.assertEqual(clean_token_usage({'total':{'inputTokens':10,'cachedInputTokens':4,'outputTokens':2,'reasoningOutputTokens':1,'totalTokens':12,'secret':'x'}}),{'inputTokens':10,'cachedInputTokens':4,'outputTokens':2,'reasoningOutputTokens':1,'totalTokens':12})
        self.assertIsNone(clean_token_usage({'total':{'inputTokens':True,'outputTokens':-1}}))
