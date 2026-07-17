import unittest

from server.gear_attribute_static_facts import option_static_facts


class GearAttributeStaticFactsTest(unittest.TestCase):
    def test_known_mage_sample_enhancements_have_exact_structured_facts(self):
        mage = {"classKey": "mage", "specKey": "frost", "level": 90}
        cases = [
            ("gem", {"gem_id": "240892"}, "verified", {"haste_rating": 16, "mastery_rating": 7}),
            ("gem", {"gem_id": "240908"}, "verified", {"crit_rating": 16, "mastery_rating": 7}),
            ("gem", {"gem_id": "240983"}, "verified", {"intellect": 32}),
            ("gem", {"gem_id": "240967"}, "verified", {"intellect": 23}),
            ("enchant", {"enchant_id": "7963"}, "verified", {"avoidance_rating": 19, "stamina": 232}),
            ("enchant", {"enchant_id": "8001"}, "verified", {"avoidance_rating": 111}),
            ("enchant", {"enchant_id": "8031"}, "verified", {"leech_rating": 166}),
            ("enchant", {"enchant_id": "7987"}, "verified", {"intellect": 50}),
            ("enchant", {"enchant_id": "7967"}, "not_applicable", {}),
            ("enchant", {"enchant_id": "4223"}, "not_applicable", {}),
            ("enchant", {"enchant_id": "4897"}, "not_applicable", {}),
            ("enchant", {"enchant_id": "8039"}, "not_applicable", {}),
            ("enchant", {"enchant_id": "8041"}, "not_applicable", {}),
        ]

        for option_type, simc_options, status, stat_deltas in cases:
            with self.subTest(option_type=option_type, simc_options=simc_options):
                facts = option_static_facts(option_type, simc_options, mage)
                self.assertIsNotNone(facts)
                self.assertEqual(facts["status"], status)
                self.assertEqual(facts["statDeltas"], stat_deltas)
                self.assertTrue(
                    facts["sourceRef"].startswith("simc-dbc-12.0.7.68453:"),
                )


if __name__ == "__main__":
    unittest.main()
