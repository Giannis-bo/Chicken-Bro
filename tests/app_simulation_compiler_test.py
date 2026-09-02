import json
import unittest
from pathlib import Path

from server.app.simulation.compiler import SimcCompileError, SimcProfileCompiler
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.simulation.sources import RaiderIOCharacterAdapter, parse_character_source_url


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "character_sources"


class FakeGateway:
    def fetch_json(self, url, *, headers=None):
        return json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text())


class SimulationCompilerTest(unittest.TestCase):
    def setUp(self):
        candidate = RaiderIOCharacterAdapter(FakeGateway()).resolve(
            parse_character_source_url("https://raider.io/characters/us/area-52/Stormsample")
        )
        capabilities = SimcRuntimeCapabilities(
            runtime_revision="simc:current:abc",
            compiler_revision="chickenbro-simc-compiler-v1",
            supported_specs=frozenset({("shaman", "elemental")}),
        )
        report = SimcReadinessValidator().validate(candidate, capabilities)
        self.snapshot = candidate.to_source_snapshot(
            user_id="00000000-0000-4000-8000-000000000001",
            snapshot_id="00000000-0000-4000-8000-000000000002",
            readiness_report=report,
        )
        self.capabilities = capabilities

    def test_compiler_outputs_bounded_profile_with_hash_and_provenance(self):
        compiled = SimcProfileCompiler(capabilities=self.capabilities).compile(
            self.snapshot,
            {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 100},
        )

        self.assertIn('shaman="Stormsample"', compiled.profile)
        self.assertIn("level=90", compiled.profile)
        self.assertIn("head=,id=1001", compiled.profile)
        self.assertEqual(len(compiled.profile_sha256), 64)
        self.assertEqual(compiled.runtime_revision, "simc:current:abc")
        self.assertEqual(compiled.provenance["sourceUrl"], self.snapshot.source_url)

    def test_compiler_rejects_non_ready_snapshot_and_unsafe_scenario(self):
        blocked = self.snapshot.__class__(
            **{**self.snapshot.__dict__, "readiness": "INCOMPLETE_FOR_SIMC"}
        )
        compiler = SimcProfileCompiler(capabilities=self.capabilities)

        with self.assertRaises(SimcCompileError) as blocked_error:
            compiler.compile(blocked, {"fightStyle": "Patchwerk"})
        self.assertEqual(blocked_error.exception.code, "SNAPSHOT_NOT_READY")

        with self.assertRaises(SimcCompileError) as scenario_error:
            compiler.compile(self.snapshot, {"fightStyle": "Patchwerk\njson=1"})
        self.assertEqual(scenario_error.exception.code, "SCENARIO_INVALID")

    def test_compiler_omits_an_unequipped_offhand_from_a_ready_snapshot(self):
        snapshot_payload = dict(self.snapshot.snapshot)
        gear = dict(snapshot_payload["gear"])
        gear.pop("off_hand")
        snapshot_payload["gear"] = gear
        snapshot = self.snapshot.__class__(
            **{**self.snapshot.__dict__, "snapshot": snapshot_payload}
        )

        compiled = SimcProfileCompiler(capabilities=self.capabilities).compile(
            snapshot,
            {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 100},
        )

        self.assertNotIn("off_hand=", compiled.profile)

    def test_compiler_uses_prototype_max_level_for_an_older_snapshot_without_level(self):
        snapshot_payload = dict(self.snapshot.snapshot)
        character = dict(snapshot_payload["character"])
        character["level"] = None
        snapshot_payload["character"] = character
        snapshot = self.snapshot.__class__(**{**self.snapshot.__dict__, "snapshot": snapshot_payload})

        compiled = SimcProfileCompiler(capabilities=self.capabilities).compile(
            snapshot,
            {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 100},
        )

        self.assertIn("level=90", compiled.profile)

    def test_compiler_normalizes_a_display_realm_name_for_simc(self):
        snapshot_payload = dict(self.snapshot.snapshot)
        character = dict(snapshot_payload["character"])
        character["realm"] = "Silver Hand"
        snapshot_payload["character"] = character
        snapshot = self.snapshot.__class__(**{**self.snapshot.__dict__, "snapshot": snapshot_payload})

        compiled = SimcProfileCompiler(capabilities=self.capabilities).compile(
            snapshot,
            {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 100},
        )

        self.assertIn("server=silver-hand", compiled.profile)


if __name__ == "__main__":
    unittest.main()
