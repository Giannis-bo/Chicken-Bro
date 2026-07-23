import copy
import unittest

from server.observed_build_projection import (
    build_dependency_vector,
    build_projection,
)
from server.observed_build_registry import build_observed_snapshot, slot_key
from server.observed_build_template_set import (
    build_template_set,
    promotion_decision,
    validate_template_set,
)
from server.websim_payload import expected_hero_tree_triplets


class ObservedBuildTemplateSetTest(unittest.TestCase):
    def slots(self):
        values = []
        for triplet in expected_hero_tree_triplets():
            class_key, spec_key, hero_key = triplet.split(":")
            values.append(
                {
                    "classKey": class_key,
                    "specKey": spec_key,
                    "heroKey": hero_key,
                    "scenarioKey": "mythic_plus",
                }
            )
        self.assertEqual(len(values), 80)
        return values

    def slot_a(self):
        return self.slots()[0]

    def dependencies(self, **overrides):
        values = {
            "season_revision": "season-tww-3",
            "talent_catalog_revision": "talent-catalog-v7",
            "gear_release_id": "gear-release:sha256:" + "1" * 64,
            "gear_rule_revision": "gear-rules-v5",
            "resolver_contract_revision": "gear-resolver-v1",
            "serializer_revision": "simc-serializer-v3",
            "simc_runtime_revision": "simc-runtime-abc",
            "selection_schema_revision": "selection-intent-v1",
            "projection_schema_revision": "observed-build-projection-v2",
        }
        values.update(overrides)
        return build_dependency_vector(**values)

    def projection(self, slot, player, *, status="verified", dependencies=None):
        observed = build_observed_snapshot(
            slot=slot,
            source={
                "sourceKey": "raiderio",
                "sourceIdentity": f"raiderio:cn|realm|{player}",
                "profileUrl": f"https://raider.io/characters/cn/realm/{player}",
                "region": "cn",
                "realm": "realm",
                "character": player,
            },
            ranking_evidence={"rank": 1, "score": 3800},
            talent_observation={"rawImportCode": player, "selectedNodes": [{"id": player, "rank": 1}]},
            gear_observation={"gearBySlot": {"head": {"itemId": f"item-{player}"}}},
            source_revision="raiderio-profile-v1",
        )
        if status == "verified":
            return build_projection(
                snapshot=observed,
                dependency_vector=dependencies or self.dependencies(),
                talent_projection={"status": "verified", "talentState": {"selectedNodes": []}},
                gear_projection={
                    "status": "verified",
                    "selectionIntent": {"slots": {"head": {"itemId": f"item-{player}"}}},
                },
                profile_readiness={"status": "verified", "simcReady": True},
            )
        return build_projection(
            snapshot=observed,
            dependency_vector=dependencies or self.dependencies(),
            talent_projection={"status": "verified"},
            gear_projection={"status": "blocked"},
            profile_readiness={"status": "blocked", "simcReady": False},
            problems=[{"code": "gear_mapping_failed", "stage": "gear"}],
        )

    def verified_candidates(self, *, player_prefix="a", dependencies=None):
        return {
            slot_key(slot): self.projection(
                slot,
                f"{player_prefix}-{index}",
                dependencies=dependencies,
            )
            for index, slot in enumerate(self.slots())
        }

    def active_with_a(self):
        return build_template_set(
            expected_slots=self.slots(),
            candidates_by_slot=self.verified_candidates(player_prefix="a"),
            active_set=None,
            dependency_vector=self.dependencies(),
            source_run_id="run-a",
        )

    @staticmethod
    def entry(template_set, slot):
        key = slot_key(slot)
        return next(item for item in template_set["entries"] if item["slotKey"] == key)

    def test_rank_one_b_replaces_a_when_b_is_verified(self):
        active = self.active_with_a()
        target = self.slot_a()
        candidate = build_template_set(
            expected_slots=self.slots(),
            candidates_by_slot={
                slot_key(target): self.projection(target, "player-b"),
            },
            active_set=active,
            dependency_vector=self.dependencies(),
            source_run_id="run-b",
        )

        target_entry = self.entry(candidate, target)
        self.assertEqual(target_entry["projectionId"], self.projection(target, "player-b")["projectionId"])
        self.assertEqual(target_entry["status"], "verified")
        self.assertNotEqual(candidate["templateSetId"], active["templateSetId"])
        self.assertEqual(promotion_decision(active_set=active, candidate_set=candidate)["action"], "auto_promote")

    def test_verified_entry_carries_projection_source_identity(self):
        active = self.active_with_a()
        target = self.slot_a()
        projection = self.verified_candidates(player_prefix="a")[slot_key(target)]

        self.assertEqual(
            self.entry(active, target)["sourceIdentity"],
            projection["sourceIdentity"],
        )

    def test_blocked_b_keeps_same_slot_a_as_stale_lkg(self):
        active = self.active_with_a()
        target = self.slot_a()
        active_entry = self.entry(active, target)
        candidate = build_template_set(
            expected_slots=self.slots(),
            candidates_by_slot={
                slot_key(target): self.projection(target, "player-b", status="blocked"),
            },
            active_set=active,
            dependency_vector=self.dependencies(),
            source_run_id="run-b",
        )

        target_entry = self.entry(candidate, target)
        self.assertEqual(target_entry["snapshotId"], active_entry["snapshotId"])
        self.assertEqual(target_entry["projectionId"], active_entry["projectionId"])
        self.assertEqual(target_entry["status"], "stale_lkg")
        self.assertEqual(target_entry["problem"]["code"], "gear_mapping_failed")
        self.assertEqual(candidate["counts"]["verified"], 79)
        self.assertEqual(candidate["counts"]["stale_lkg"], 1)

    def test_stale_lkg_keeps_the_previous_source_identity(self):
        active = self.active_with_a()
        target = self.slot_a()
        active_entry = self.entry(active, target)
        candidate = build_template_set(
            expected_slots=self.slots(),
            candidates_by_slot={
                slot_key(target): self.projection(target, "player-b", status="blocked"),
            },
            active_set=active,
            dependency_vector=self.dependencies(),
            source_run_id="run-b",
        )

        self.assertEqual(
            self.entry(candidate, target)["sourceIdentity"],
            active_entry["sourceIdentity"],
        )

    def test_no_lkg_marks_one_pending_and_keeps_other_seventy_nine_entries(self):
        target = self.slot_a()
        candidates = self.verified_candidates(player_prefix="first")
        candidates.pop(slot_key(target))
        candidate = build_template_set(
            expected_slots=self.slots(),
            candidates_by_slot=candidates,
            active_set=None,
            dependency_vector=self.dependencies(),
            source_run_id="run-1",
        )

        target_entry = self.entry(candidate, target)
        self.assertEqual(len(candidate["entries"]), 80)
        self.assertEqual(target_entry["status"], "pending_collection")
        self.assertEqual(target_entry["snapshotId"], "")
        self.assertEqual(target_entry["projectionId"], "")
        self.assertEqual(candidate["counts"]["verified"], 79)
        self.assertEqual(candidate["counts"]["pending_collection"], 1)

    def test_initial_activation_rejects_pending_slot(self):
        target = self.slot_a()
        candidates = self.verified_candidates(player_prefix="first")
        candidates.pop(slot_key(target))
        candidate = build_template_set(
            expected_slots=self.slots(),
            candidates_by_slot=candidates,
            active_set=None,
            dependency_vector=self.dependencies(),
            source_run_id="run-first",
        )

        decision = promotion_decision(active_set=None, candidate_set=candidate)

        self.assertEqual(decision["action"], "blocked")
        self.assertEqual(decision["reason"], "initial_coverage_incomplete")
        self.assertEqual(decision["problems"][0]["count"], 1)

    def test_same_spec_hero_slots_require_distinct_players(self):
        slots = self.slots()
        first = slots[0]
        second = next(
            slot
            for slot in slots[1:]
            if slot["classKey"] == first["classKey"]
            and slot["specKey"] == first["specKey"]
        )
        candidates = self.verified_candidates(player_prefix="unique")
        candidates[slot_key(first)] = self.projection(first, "duplicate-player")
        candidates[slot_key(second)] = self.projection(second, "duplicate-player")

        with self.assertRaisesRegex(ValueError, "SPEC_PLAYER_DUPLICATE"):
            build_template_set(
                expected_slots=slots,
                candidates_by_slot=candidates,
                active_set=None,
                dependency_vector=self.dependencies(),
                source_run_id="run-duplicate",
            )

    def test_missing_new_candidate_reuses_active_entry_without_marking_stale(self):
        active = self.active_with_a()
        candidate = build_template_set(
            expected_slots=self.slots(),
            candidates_by_slot={},
            active_set=active,
            dependency_vector=self.dependencies(),
            source_run_id="run-unchanged",
        )

        self.assertEqual(candidate["templateSetId"], active["templateSetId"])
        self.assertEqual(candidate["counts"], active["counts"])
        self.assertEqual(
            promotion_decision(active_set=active, candidate_set=candidate)["action"],
            "no_op",
        )

    def test_cross_slot_lkg_is_rejected(self):
        active = self.active_with_a()
        target = self.slot_a()
        malformed = copy.deepcopy(active)
        malformed["entries"][0]["slot"] = copy.deepcopy(active["entries"][1]["slot"])

        with self.assertRaisesRegex(ValueError, "same-slot"):
            build_template_set(
                expected_slots=self.slots(),
                candidates_by_slot={
                    slot_key(target): self.projection(target, "player-b", status="blocked"),
                },
                active_set=malformed,
                dependency_vector=self.dependencies(),
                source_run_id="run-b",
            )

    def test_duplicate_expected_slot_is_rejected(self):
        expected = self.slots()
        expected[-1] = copy.deepcopy(expected[0])

        with self.assertRaisesRegex(ValueError, "unique"):
            build_template_set(
                expected_slots=expected,
                candidates_by_slot={},
                active_set=None,
                dependency_vector=self.dependencies(),
                source_run_id="run-1",
            )

    def test_dependency_drift_requires_controlled_cutover(self):
        active = self.active_with_a()
        changed_dependencies = self.dependencies(serializer_revision="simc-serializer-v4")
        candidate = build_template_set(
            expected_slots=self.slots(),
            candidates_by_slot=self.verified_candidates(
                player_prefix="b",
                dependencies=changed_dependencies,
            ),
            active_set=active,
            dependency_vector=changed_dependencies,
            source_run_id="run-b",
        )

        self.assertEqual(
            promotion_decision(active_set=active, candidate_set=candidate)["action"],
            "controlled_cutover",
        )

    def test_validation_detects_duplicate_or_missing_entry(self):
        valid = self.active_with_a()
        malformed = copy.deepcopy(valid)
        malformed["entries"][-1] = copy.deepcopy(malformed["entries"][0])

        issues = validate_template_set(malformed, self.slots())

        self.assertIn("TEMPLATE_SET_SLOT_DUPLICATE", {item["code"] for item in issues})
        self.assertIn("TEMPLATE_SET_SLOT_MISSING", {item["code"] for item in issues})

    def test_validation_rejects_incomplete_dependencies_and_empty_source_run(self):
        malformed = self.active_with_a()
        malformed["dependencyVector"].pop("serializerRevision")
        malformed["sourceRunId"] = ""

        issues = validate_template_set(malformed, self.slots())

        codes = {issue["code"] for issue in issues}
        self.assertIn("TEMPLATE_SET_DEPENDENCIES_INVALID", codes)
        self.assertIn("TEMPLATE_SET_SOURCE_RUN_INVALID", codes)


if __name__ == "__main__":
    unittest.main()
