import unittest

from server.websim_payload import expected_hero_tree_triplets


class ObservedBuildCharacterizationTest(unittest.TestCase):
    def test_current_hero_matrix_is_exactly_eighty_unique_mythic_plus_slots(self):
        triplets = expected_hero_tree_triplets()
        slots = [f"{triplet}:mythic_plus" for triplet in triplets]

        self.assertEqual(len(triplets), 80)
        self.assertEqual(len(set(triplets)), 80)
        self.assertEqual(len(slots), 80)
        self.assertTrue(all(slot.count(":") == 3 for slot in slots))


if __name__ == "__main__":
    unittest.main()
