import unittest

from server.simulation_snapshot_compat import (
    snapshot_from_compatibility_profile,
    snapshot_from_v2_compatibility_profile,
)
from server.gear_resolved_loadout import build_resolved_loadout_v2
from tests.gear_resolved_loadout_test import resolver_snapshot, v2_bundle, v2_resolver_snapshot
from tests.simulation_snapshot_store_test import loadout
from tests.simulation_snapshot_test import v2_snapshot_fixture


PROFILE = """mage="test"
spec=arcane
level=90
race=troll
role=spell
position=back
talents=CYQAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
head=item_1001,id=1001,ilevel=266,bonus_id=9001/9002
main_hand=item_1002,id=1002,ilevel=272,bonus_id=9010,enchant_id=7443
optimal_raid=0
override.arcane_intellect=1
iterations=1000
fight_style=Patchwerk
desired_targets=1
max_time=300
vary_combat_length=0.2
calculate_scale_factors=0"""

FROZEN_V2_LOADOUT_KEY = (
    "resolved-loadout-v2:sha256:"
    "f63aa16e245614cac8aa9ac836090673a6f3a11961b95768c532dc65e7a9ca3f"
)
FROZEN_V2_LOADOUT_ROW_HASH = (
    "sha256:daf38bba00a93dfe0c6a01ddb8123bcb5c418396b06915f7ac1df6a50169765e"
)
FROZEN_V2_SNAPSHOT_KEY = (
    "simulation-snapshot-v2:sha256:"
    "c687f0169e99856e18cffb44cad37a42bf6b207ebb25d31d4765cea4d1787497"
)
FROZEN_V2_SNAPSHOT_ROW_HASH = (
    "sha256:e5adfd9677648118a905ffe4cb7aef649d5a0691d7e6e33158701c2b9881b060"
)


class SimulationSnapshotCompatibilityTest(unittest.TestCase):
    def test_v1_and_v2_frozen_identity_remain_unchanged_after_v3_is_added(self):
        v1 = snapshot_from_compatibility_profile(
            loadout(),
            PROFILE,
            scenario_key="single",
            compiler_revision="simc-profile-compiler-v1",
            simc_runtime_revision="simc-runtime-v1",
        )
        _resolver, _bundles, v2_loadout, v2_snapshot = v2_snapshot_fixture()

        self.assertEqual(v1["schemaRevision"], "simulation-snapshot-v1")
        self.assertEqual(v1["canonicalSimcInput"], PROFILE + "\n")
        self.assertEqual(v2_loadout["resolvedLoadoutKey"], FROZEN_V2_LOADOUT_KEY)
        self.assertEqual(v2_loadout["rowHash"], FROZEN_V2_LOADOUT_ROW_HASH)
        self.assertEqual(v2_snapshot["simulationSnapshotKey"], FROZEN_V2_SNAPSHOT_KEY)
        self.assertEqual(v2_snapshot["rowHash"], FROZEN_V2_SNAPSHOT_ROW_HASH)

    def test_verified_backend_profile_round_trips_to_exact_snapshot_bytes(self):
        result = snapshot_from_compatibility_profile(
            loadout(),
            PROFILE,
            scenario_key="single",
            compiler_revision="simc-profile-compiler-v1",
            simc_runtime_revision="simc-runtime-v1",
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["canonicalSimcInput"], PROFILE + "\n")

    def test_profile_drift_or_frontend_line_fails_closed(self):
        drift = snapshot_from_compatibility_profile(
            loadout(),
            PROFILE.replace("bonus_id=9001/9002", "bonus_id=9999"),
            scenario_key="single",
            compiler_revision="simc-profile-compiler-v1",
            simc_runtime_revision="simc-runtime-v1",
        )
        injected = snapshot_from_compatibility_profile(
            loadout(),
            PROFILE + "\nunknown_frontend_fact=1",
            scenario_key="single",
            compiler_revision="simc-profile-compiler-v1",
            simc_runtime_revision="simc-runtime-v1",
        )

        self.assertEqual(drift["status"], "blocked")
        self.assertIn(
            "SIMULATION_COMPILER_COMPATIBILITY_MISMATCH",
            drift["problemCodes"],
        )
        self.assertEqual(injected["status"], "blocked")
        self.assertIn(
            "SIMULATION_COMPATIBILITY_PROFILE_INVALID",
            injected["problemCodes"],
        )

    def test_v2_compatibility_rejects_legacy_profile_drift(self):
        """Would fail if the v2 bridge bypassed the v2 canonical compiler."""
        source = v2_resolver_snapshot()
        source["resolvedSlots"] = {"head": {"slot": "head", "itemId": "1001", "legality": {"status": "verified"}}}
        source["profileReadiness"] = {"status": "verified", "simcReady": True, "requiredSlots": ["head"], "readySlots": ["head"], "simcRuntimeRevision": "simc-runtime-v2"}
        bundle = v2_bundle("head", "1001", [])
        key = bundle.envelope.content_key
        loadout = build_resolved_loadout_v2(
            resolver_snapshot=source,
            exact_authority_by_slot=[{"slot": "head", "exactAuthorityEnvelopeKey": key}],
            authority_bundles={key: bundle},
            gear_rule_revision="gear-rule-matrix-v1",
            resolver_revision="resolver-v2",
            simc_runtime_revision="simc-runtime-v2",
        )
        profile = PROFILE.replace("main_hand=item_1002,id=1002,ilevel=272,bonus_id=9010,enchant_id=7443\n", "")
        result = snapshot_from_v2_compatibility_profile(
            loadout, profile, scenario_key="single", compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2", resolver_snapshot=source, authority_bundles={key: bundle}
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("SIMULATION_COMPILER_COMPATIBILITY_MISMATCH", result["problemCodes"])

    def test_v2_compatibility_failure_stays_v2_schema(self):
        """Would fail if a v2 bridge error used the legacy snapshot schema."""
        result = snapshot_from_v2_compatibility_profile(
            {}, "not a profile", scenario_key="single", compiler_revision="simc-profile-compiler-v2", simc_runtime_revision="simc-runtime-v2"
        )
        self.assertEqual(result["schemaRevision"], "simulation-snapshot-v2")


if __name__ == "__main__":
    unittest.main()
