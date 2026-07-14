import copy
import importlib
import json
from pathlib import Path
import unittest


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "midnight-mage-frost-socket-evidence-v1.json"


class GearSocketAuthorityTest(unittest.TestCase):
    def authority(self):
        try:
            return importlib.import_module("server.gear_socket_authority")
        except ModuleNotFoundError as exc:
            self.fail(f"pure socket authority must exist: {exc}")

    def test_nested_battle_net_socket_array_preserves_zero_one_two(self):
        authority = self.authority()

        self.assertEqual(authority.count_payload_socket_entries({}), 0)
        self.assertEqual(
            authority.count_payload_socket_entries({"preview_item": {"sockets": []}}),
            0,
        )
        self.assertEqual(
            authority.count_payload_socket_entries(
                {"preview_item": {"sockets": [{"socket_type": {"type": "PRISMATIC"}}]}}
            ),
            1,
        )
        self.assertEqual(
            authority.count_payload_socket_entries(
                {
                    "preview_item": {
                        "sockets": [
                            {"socket_type": {"type": "PRISMATIC"}},
                            {"socket_type": {"type": "PRISMATIC"}},
                        ]
                    }
                }
            ),
            2,
        )

    def test_midnight_jewelry_floor_does_not_generalize_two_sockets(self):
        authority = self.authority()
        two_socket_ring = {
            "itemId": "ring-two",
            "slot": "finger1",
            "payload": {
                "preview_item": {
                    "sockets": [
                        {"socket_type": {"type": "PRISMATIC"}},
                        {"socket_type": {"type": "PRISMATIC"}},
                    ]
                }
            },
        }
        different_ring = {
            "itemId": "ring-one",
            "slot": "finger2",
            "payload": {"preview_item": {"sockets": []}},
        }

        two_socket_fact = authority.derive_item_socket_fact(
            two_socket_ring,
            season_revision="midnight-season-1",
        )
        different_ring_fact = authority.derive_item_socket_fact(
            different_ring,
            season_revision="midnight-season-1",
        )
        live_revision_facts = [
            authority.derive_item_socket_fact(
                different_ring,
                season_revision=season_revision,
            )
            for season_revision in (
                "season-midnight-season-1-c09b0948e307",
                "season-17-f131dd36ddf1",
            )
        ]
        future_or_unknown_facts = [
            authority.derive_item_socket_fact(
                different_ring,
                season_revision=season_revision,
            )
            for season_revision in (
                "unknown-season",
                "season-18",
                "season-18-aaaaaaaaaaaa",
                "ptr-12.1-s2-build-12345",
                "season-midnight-season-1-c09b0948e307-extra",
                "season-17-f131dd36ddf1-extra",
            )
        ]

        self.assertEqual(two_socket_fact["minimumTotal"], 2)
        self.assertEqual(different_ring_fact["minimumTotal"], 1)
        self.assertEqual(
            [claim["source"] for claim in different_ring_fact["claims"]],
            ["midnight_s1_jewelry_floor"],
        )
        self.assertTrue(
            all(
                fact["minimumTotal"] == 1
                and [claim["source"] for claim in fact["claims"]]
                == ["midnight_s1_jewelry_floor"]
                for fact in live_revision_facts
            )
        )
        self.assertTrue(
            all(fact["minimumTotal"] == 0 and fact["claims"] == [] for fact in future_or_unknown_facts)
        )

    def test_exact_variant_sources_are_minimum_totals_and_never_sum(self):
        authority = self.authority()
        item = {
            "itemId": "neck-max-not-sum",
            "slot": "neck",
            "payload": {
                "preview_item": {
                    "sockets": [{"socket_type": {"type": "PRISMATIC"}}]
                }
            },
        }
        variant = {
            "variantId": "variant-neck-max-not-sum",
            "itemId": "neck-max-not-sum",
            "variantKey": "observed-two-socket",
            "slot": "neck",
            "payload": {
                "preview_item": {
                    "sockets": [
                        {"socket_type": {"type": "PRISMATIC"}},
                        {"socket_type": {"type": "PRISMATIC"}},
                    ]
                }
            },
            "simcOptions": {
                "bonus_id": "9300/9999",
                "gem_id": "240983/240892",
            },
        }

        fact = authority.derive_variant_socket_fact(
            item,
            variant,
            season_revision="midnight-season-1",
            socket_bonus_minimums={"9300": 2},
        )

        self.assertEqual(fact["minimumTotal"], 2)
        self.assertEqual(
            fact["minimumTotal"],
            max(claim["minimumTotal"] for claim in fact["claims"]),
        )
        self.assertEqual(
            {claim["source"] for claim in fact["claims"]},
            {
                "midnight_s1_jewelry_floor",
                "official_item_payload",
                "simc_bonus",
                "observed_gem_occupancy",
            },
        )
        self.assertNotEqual(
            fact["minimumTotal"],
            sum(claim["minimumTotal"] for claim in fact["claims"]),
        )

    def test_gem_sequence_is_exact_variant_lower_bound_only(self):
        authority = self.authority()
        item = {
            "itemId": "unknown-season-ring",
            "slot": "finger1",
            "payload": {"preview_item": {"sockets": []}},
        }
        observed_variant = {
            "variantId": "variant-with-two-gems",
            "itemId": "unknown-season-ring",
            "variantKey": "two-gems",
            "slot": "finger1",
            "simcOptions": {"gem_id": "240983/240983"},
        }
        different_variant = {
            "variantId": "variant-without-gems",
            "itemId": "unknown-season-ring",
            "variantKey": "no-gems",
            "slot": "finger1",
            "simcOptions": {},
        }
        malformed_variants = [
            {
                "variantId": f"variant-with-malformed-gem-token-{index}",
                "itemId": "unknown-season-ring",
                "variantKey": f"malformed-gem-token-{index}",
                "slot": "finger1",
                "simcOptions": {"gem_id": gem_sequence},
            }
            for index, gem_sequence in enumerate(
                (
                    "not-a-gem",
                    "240983/not-a-gem/240892",
                    "240983//240892",
                    "240983/0/240892",
                    "240983/-1/240892",
                )
            )
        ]

        item_fact = authority.derive_item_socket_fact(
            item,
            season_revision="unknown-season",
        )
        observed_fact = authority.derive_variant_socket_fact(
            item,
            observed_variant,
            season_revision="unknown-season",
        )
        different_fact = authority.derive_variant_socket_fact(
            item,
            different_variant,
            season_revision="unknown-season",
        )
        malformed_facts = [
            authority.derive_variant_socket_fact(
                item,
                malformed_variant,
                season_revision="unknown-season",
            )
            for malformed_variant in malformed_variants
        ]

        self.assertEqual(item_fact["minimumTotal"], 0)
        self.assertEqual(observed_fact["minimumTotal"], 2)
        self.assertEqual(different_fact["minimumTotal"], 0)
        self.assertTrue(
            all(fact["minimumTotal"] == 0 and fact["claims"] == [] for fact in malformed_facts)
        )
        gem_claim = next(
            claim for claim in observed_fact["claims"] if claim["source"] == "observed_gem_occupancy"
        )
        self.assertEqual(gem_claim["scope"], "exact_variant")

    def test_unknown_season_and_unknown_bonus_fail_closed(self):
        authority = self.authority()
        parsed = authority.parse_simc_socket_bonus_minimums(
            "\n".join(
                [
                    "bonus_id={ 523 }, socket={ 1 }",
                    "bonus_id={ 8781 }, socket={ 2 }",
                    "bonus_id={ bogus }, socket={ 3 }",
                    "bonus_id={ 8782 }, socket={ bogus }",
                    "bonus_id={ 8783 }, socket={ -1 }",
                    "bonus_id={ 8784 }junk, socket={ 1 }",
                    "bonus_id={ 8785 }, socket={ 2 }junk",
                    "bonus_id={ 8786 }, socket=3}",
                    "bonus_id=9300 effect=socket minimum_total=1",
                    "bonus_id=9400 effect=item_level minimum_total=99",
                    "bonus_id=9500 effect=no socket minimum_total=1",
                    "bonus_id=9600 effect=remove socket minimum_total=1",
                    "bonus_id=9700 effect=socket=2",
                    "bonus_id=9701 effect=socket=0",
                    "bonus_id=9702 effect=socket=-1",
                    "bonus_id=9703 effect=socket=bogus",
                    "bonus_id=9704 effect=socket=2 minimum_total=3",
                    "bonus_id=9705 effect=socket=1 socket_count=2",
                    "bonus_id=9706 effect=socket minimum_total=4",
                    "bonus_id=9707 effect=socket socket_count=5",
                    "bonus_id=9708 effect=socket minimum_total=2",
                    "bonus_id=9708 effect=socket socket_count=3",
                    "bonus_id=9709: effect=socket=2",
                    "bonus_id=9710-effect=socket=2",
                    "unstructured socket text",
                ]
            )
        )
        self.assertEqual(
            parsed,
            {
                "523": 1,
                "8781": 2,
                "9300": 1,
                "9700": 2,
                "9704": 3,
                "9705": 2,
                "9706": 4,
                "9707": 5,
                "9708": 3,
                "9709": 2,
                "9710": 2,
            },
        )

        unknown_season_fact = authority.derive_item_socket_fact(
            {
                "itemId": "future-head",
                "slot": "head",
                "isPvp": False,
                "payload": {"preview_item": {"sockets": []}},
            },
            season_revision="midnight-season-2",
        )
        unknown_bonus_fact = authority.derive_variant_socket_fact(
            {"itemId": "plain-chest", "slot": "chest", "payload": {}},
            {
                "variantId": "plain-chest-unknown-bonus",
                "itemId": "plain-chest",
                "variantKey": "unknown-bonus",
                "slot": "chest",
                "simcOptions": {"bonus_id": "9999"},
            },
            season_revision="midnight-season-1",
            socket_bonus_minimums=parsed,
        )
        conflicting_pvp_fact = authority.derive_item_socket_fact(
            {
                "itemId": "conflicting-pvp-head",
                "slot": "head",
                "isPvp": False,
                "payload": {
                    "isPvp": True,
                    "preview_item": {"sockets": []},
                },
            },
            season_revision="midnight-season-1",
        )

        self.assertEqual(unknown_season_fact["minimumTotal"], 0)
        self.assertEqual(unknown_bonus_fact["minimumTotal"], 0)
        self.assertEqual(unknown_bonus_fact["claims"], [])
        self.assertEqual(conflicting_pvp_fact["minimumTotal"], 0)
        self.assertEqual(conflicting_pvp_fact["claims"], [])

    def test_materializer_does_not_mutate_snapshot(self):
        authority = self.authority()
        snapshot = {
            "items": [
                {
                    "itemId": "non-mutating-ring",
                    "slot": "finger1",
                    "baseCapabilities": {"canEnchant": True},
                    "payload": {"preview_item": {"sockets": []}},
                }
            ],
            "variants": [
                {
                    "variantId": "non-mutating-ring-variant",
                    "itemId": "non-mutating-ring",
                    "variantKey": "observed",
                    "slot": "finger1",
                    "capabilityOverrides": {"canEmbellish": False},
                    "simcOptions": {"gem_id": "240983"},
                }
            ],
            "sources": [],
            "options": [],
        }
        original = copy.deepcopy(snapshot)

        materialized = authority.materialize_gear_socket_facts(
            snapshot,
            season_revision="midnight-season-1",
        )

        self.assertEqual(snapshot, original)
        self.assertIsNot(materialized, snapshot)
        self.assertEqual(materialized["items"][0]["baseCapabilities"]["socketCount"], 1)
        self.assertTrue(materialized["items"][0]["baseCapabilities"]["canEnchant"])
        self.assertEqual(materialized["variants"][0]["capabilityOverrides"]["socketCount"], 1)
        self.assertFalse(materialized["variants"][0]["capabilityOverrides"]["canEmbellish"])

    def test_mage_fixture_materializes_1_2_1_1_2_1(self):
        authority = self.authority()
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        materialized = authority.materialize_gear_socket_facts(
            fixture["snapshot"],
            season_revision=fixture["seasonRevision"],
            socket_bonus_minimums=fixture["socketBonusMinimums"],
        )
        variants = materialized["variants"]
        variant_keys = [variant.get("variantKey") for variant in variants]
        self.assertTrue(all(variant_keys))
        self.assertEqual(len(set(variant_keys)), len(variant_keys))
        variants_by_key = {variant["variantKey"]: variant for variant in variants}
        items = materialized["items"]
        items_by_id = {item["itemId"]: item for item in items}
        self.assertEqual(len(items_by_id), len(items))
        ordered_instances = fixture["expectedInstances"]
        expected_item_ids = {instance["itemId"] for instance in ordered_instances}
        for instance in ordered_instances:
            with self.subTest(instance=instance):
                variant = variants_by_key[instance["variantKey"]]
                self.assertEqual(variant["itemId"], instance["itemId"])
                self.assertEqual(authority._normalized_slot(variant.get("slot")), instance["slot"])
                item = items_by_id.get(instance["itemId"])
                self.assertIsNotNone(item)
                self.assertEqual(item["itemId"], instance["itemId"])
                self.assertEqual(authority._normalized_slot(item.get("slot")), instance["slot"])
        capacities = [
            variants_by_key[instance["variantKey"]]["capabilityOverrides"]["socketCount"]
            for instance in ordered_instances
        ]

        self.assertEqual(
            [instance["slot"] for instance in ordered_instances],
            ["head", "neck", "wrist", "waist", "finger1", "finger2"],
        )
        self.assertEqual(capacities, [1, 2, 1, 1, 2, 1])
        self.assertEqual(sum(capacities), 8)
        for instance in ordered_instances:
            if instance["slot"] not in {"head", "wrist", "waist"}:
                continue
            claim_sources = {
                claim["source"]
                for claim in variants_by_key[instance["variantKey"]]["socketEvidence"]["claims"]
            }
            self.assertIn("midnight_s1_radiant_jewelbinder", claim_sources)
        different_ring_variant = variants_by_key[fixture["differentRingVariantKey"]]
        different_ring_item_id = different_ring_variant["itemId"]
        self.assertNotIn(different_ring_item_id, expected_item_ids)
        self.assertIn(
            authority._normalized_slot(different_ring_variant.get("slot")),
            {"finger", "finger1", "finger2"},
        )
        different_ring_item = items_by_id.get(different_ring_item_id)
        self.assertIsNotNone(different_ring_item)
        self.assertEqual(different_ring_item["itemId"], different_ring_item_id)
        self.assertEqual(
            authority._normalized_slot(different_ring_item.get("slot")),
            authority._normalized_slot(different_ring_variant.get("slot")),
        )
        self.assertEqual(
            [claim["source"] for claim in different_ring_variant["socketEvidence"]["claims"]],
            ["midnight_s1_jewelry_floor"],
        )
        self.assertEqual(
            different_ring_variant["capabilityOverrides"]["socketCount"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
