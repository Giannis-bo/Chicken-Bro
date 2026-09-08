import json
import unittest
from dataclasses import replace
from pathlib import Path

from server.app.simulation.compiler import SimcCompileError, SimcProfileCompiler, normalize_scenario, scenario_hash
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

    def test_reconstructed_talents_reject_different_or_unknown_runtime_catalog(self):
        snapshot = replace(self.snapshot, provenance={**self.snapshot.provenance,
            "wclTalentReconstruction": {"catalogRuntimeRevision": "f" * 40}})
        for runtime in ("simc:managed:" + "a" * 40 + ":" + "b" * 64, "simc:unknown"):
            caps = replace(self.capabilities, runtime_revision=runtime)
            report = SimcReadinessValidator().validate(snapshot, caps)
            self.assertIn("TALENTS_INVALID", report.blockers)
            with self.assertRaises(SimcCompileError) as error:
                SimcProfileCompiler(capabilities=caps).compile(snapshot, {})
            self.assertEqual(error.exception.code, "TALENTS_INVALID")
        caps = replace(self.capabilities, runtime_revision="simc:managed:" + "f" * 40 + ":" + "b" * 64)
        self.assertNotIn("TALENTS_INVALID", SimcReadinessValidator().validate(snapshot, caps).blockers)
        compiled = SimcProfileCompiler(capabilities=caps).compile(snapshot, {})
        self.assertEqual(compiled.provenance["wclTalentReconstruction"], snapshot.provenance["wclTalentReconstruction"])

    def test_compiler_outputs_bounded_profile_with_hash_and_provenance(self):
        compiled = SimcProfileCompiler(capabilities=self.capabilities).compile(
            self.snapshot,
            {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 100},
        )

        self.assertIn('shaman="Stormsample"', compiled.profile)
        self.assertIn("level=80", compiled.profile)
        self.assertIn("head=,id=1001", compiled.profile)
        self.assertEqual(len(compiled.profile_sha256), 64)
        self.assertEqual(compiled.runtime_revision, "simc:current:abc")
        self.assertEqual(compiled.provenance["sourceUrl"], self.snapshot.source_url)

    def test_legacy_scenario_and_profile_hashes_are_unchanged(self):
        compiled = SimcProfileCompiler(capabilities=self.capabilities).compile(self.snapshot, {})
        self.assertEqual(compiled.scenario, {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 300})
        self.assertEqual(compiled.scenario_hash, "10f5bee236346ae6a5d7e1ec9023570b6548140387846bcdff75f5be87c57b61")
        self.assertEqual(compiled.profile_sha256, "6ed223804c0377d0350be01e7cc1289c77af3bd8371854c591c36e0719b0a157")

    def test_fixed_duration_and_gems_compile_without_mutating_snapshot(self):
        compiler = SimcProfileCompiler(capabilities=replace(
            self.capabilities, compiler_revision="chickenbro-simc-compiler-v2"
        ))
        before = json.dumps(self.snapshot.snapshot, sort_keys=True)
        scenario = {"maxTime": 120, "desiredTargets": 5, "gemOverrides": {"neck": [9999]}}
        compiled = compiler.compile(self.snapshot, scenario)
        self.assertIn("max_time=120\nfixed_time=1\nvary_combat_length=0\n", compiled.profile)
        self.assertIn("neck=,id=1002,bonus_id=1,gem_id=9999\n", compiled.profile)
        self.assertNotIn("gem_id=2001", compiled.profile)
        self.assertEqual(before, json.dumps(self.snapshot.snapshot, sort_keys=True))
        self.assertNotEqual(compiled.scenario_hash, scenario_hash({**scenario, "maxTime": 300}))
        self.assertNotEqual(compiled.scenario_hash, scenario_hash({**scenario, "gemOverrides": {"neck": [9998]}}))
        scenario["gemOverrides"]["neck"][0] = 8888
        self.assertEqual(compiled.scenario["gemOverrides"], {"neck": [9999]})

    def test_new_scenario_fields_require_compiler_v2(self):
        with self.assertRaises(SimcCompileError) as error:
            SimcProfileCompiler(capabilities=self.capabilities).compile(self.snapshot, {"maxTime": 300})
        self.assertEqual(error.exception.code, "COMPILER_UNAVAILABLE")

    def test_new_scenario_fields_are_strict_and_bounded(self):
        invalid = [{"maxTime": value} for value in (None, True, "300", 300.0, 29, 601)]
        invalid += [{"gemOverrides": value} for value in (
            None, [], {"ring1": [1]}, {"neck": []}, {"neck": [True]},
            {"neck": ["1"]}, {"neck": [0]}, {"neck": [-1]}, {"neck": [1.0]},
            {"neck": [1] * 33}, {"neck": ["1\noutput=/tmp/out"]},
        )]
        for scenario in invalid:
            with self.subTest(scenario=scenario):
                with self.assertRaises(SimcCompileError) as error:
                    normalize_scenario(scenario)
                self.assertEqual(error.exception.code, "SCENARIO_INVALID")
        self.assertEqual(normalize_scenario({"maxTime": 30})["maxTime"], 30)
        self.assertEqual(normalize_scenario({"maxTime": 600})["maxTime"], 600)

    def test_gem_overrides_cannot_add_or_remove_sockets_or_target_unequipped_slots(self):
        compiler = SimcProfileCompiler(capabilities=replace(
            self.capabilities, compiler_revision="chickenbro-simc-compiler-v2"
        ))
        for overrides in ({"head": [9999]}, {"neck": [9999, 9998]}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(SimcCompileError) as error:
                    compiler.compile(self.snapshot, {"gemOverrides": overrides})
                self.assertEqual(error.exception.code, "GEM_OVERRIDE_SOCKET_MISMATCH")
        payload = {
            **self.snapshot.snapshot,
            "gear": dict(self.snapshot.snapshot["gear"]),
            "gearState": {"unequippedSlots": ["off_hand"]},
        }
        payload["gear"].pop("off_hand")
        with self.assertRaises(SimcCompileError) as error:
            compiler.compile(replace(self.snapshot, snapshot=payload), {"gemOverrides": {"off_hand": [9999]}})
        self.assertEqual(error.exception.code, "GEM_OVERRIDE_SOCKET_MISMATCH")

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

    def test_compiler_rejects_generated_profile_even_if_readiness_is_forged(self):
        snapshot_payload = dict(self.snapshot.snapshot)
        snapshot_payload["profileSource"] = "generated"
        snapshot = self.snapshot.__class__(**{**self.snapshot.__dict__, "snapshot": snapshot_payload})

        with self.assertRaises(SimcCompileError) as error:
            SimcProfileCompiler(capabilities=self.capabilities).compile(
                snapshot,
                {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 100},
            )

        self.assertEqual(error.exception.code, "PROFILE_NOT_REAL_SOURCE")

    def test_compiler_omits_an_unequipped_offhand_from_a_ready_snapshot(self):
        snapshot_payload = dict(self.snapshot.snapshot)
        gear = dict(snapshot_payload["gear"])
        gear.pop("off_hand")
        snapshot_payload["gear"] = gear
        snapshot_payload["gearState"] = {"unequippedSlots": ["off_hand"]}
        snapshot = self.snapshot.__class__(
            **{**self.snapshot.__dict__, "snapshot": snapshot_payload}
        )

        compiled = SimcProfileCompiler(capabilities=self.capabilities).compile(
            snapshot,
            {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 100},
        )

        self.assertNotIn("off_hand=", compiled.profile)

    def test_compiler_rejects_a_ready_snapshot_without_source_level(self):
        snapshot_payload = dict(self.snapshot.snapshot)
        character = dict(snapshot_payload["character"])
        character["level"] = None
        snapshot_payload["character"] = character
        snapshot = self.snapshot.__class__(**{**self.snapshot.__dict__, "snapshot": snapshot_payload})

        with self.assertRaises(SimcCompileError) as error:
            SimcProfileCompiler(capabilities=self.capabilities).compile(
                snapshot,
                {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 100},
            )

        self.assertEqual(error.exception.code, "MISSING_LEVEL")

    def test_compiler_rejects_a_ready_snapshot_without_source_race(self):
        snapshot_payload = dict(self.snapshot.snapshot)
        character = dict(snapshot_payload["character"])
        character.pop("raceKey")
        snapshot_payload["character"] = character
        snapshot = self.snapshot.__class__(**{**self.snapshot.__dict__, "snapshot": snapshot_payload})

        with self.assertRaises(SimcCompileError) as error:
            SimcProfileCompiler(capabilities=self.capabilities).compile(
                snapshot,
                {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 100},
            )

        self.assertEqual(error.exception.code, "MISSING_RACE")

    def test_compiler_rejects_a_partial_talent_loadout_instead_of_guessing_rank(self):
        snapshot_payload = dict(self.snapshot.snapshot)
        snapshot_payload["talents"] = {
            "loadout": [
                {"id": 10001, "rank": 1},
                {"id": 10002},
            ]
        }
        snapshot = self.snapshot.__class__(**{**self.snapshot.__dict__, "snapshot": snapshot_payload})

        with self.assertRaises(SimcCompileError) as error:
            SimcProfileCompiler(capabilities=self.capabilities).compile(
                snapshot,
                {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 100},
            )

        self.assertEqual(error.exception.code, "TALENTS_INVALID")

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
