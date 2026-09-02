import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from server.app.simulation.domain import SourceProvider, SourceReadiness
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.simulation.sources import RaiderIOCharacterAdapter, parse_character_source_url


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "character_sources"


class FakeGateway:
    def __init__(self, payload):
        self.payload = payload

    def fetch_json(self, url, *, headers=None):
        return self.payload


def candidate_from_fixture():
    payload = json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text())
    return RaiderIOCharacterAdapter(FakeGateway(payload)).resolve(
        parse_character_source_url("https://raider.io/characters/us/area-52/Stormsample")
    )


class SimulationReadinessTest(unittest.TestCase):
    def setUp(self):
        self.capabilities = SimcRuntimeCapabilities(
            runtime_revision="simc:current:abc",
            compiler_revision="chickenbro-simc-compiler-v1",
            supported_specs=frozenset({("shaman", "elemental")}),
        )

    def test_real_source_with_required_semantics_is_ready(self):
        report = SimcReadinessValidator().validate(candidate_from_fixture(), self.capabilities)

        self.assertEqual(report.readiness, SourceReadiness.READY_FOR_SIMC)
        self.assertEqual(report.blockers, ())

    def test_source_without_an_offhand_is_ready_when_provider_reports_no_offhand(self):
        candidate = candidate_from_fixture()
        snapshot = dict(candidate.snapshot)
        gear = dict(snapshot["gear"])
        gear.pop("off_hand")
        snapshot["gear"] = gear
        changed = candidate.__class__(**{**candidate.__dict__, "snapshot": snapshot})

        report = SimcReadinessValidator().validate(changed, self.capabilities)

        self.assertEqual(report.readiness, SourceReadiness.READY_FOR_SIMC)
        self.assertNotIn("GEAR_OFF_HAND_MISSING", report.blockers)

    def test_missing_character_level_uses_the_prototype_max_level_policy(self):
        candidate = candidate_from_fixture()
        snapshot = dict(candidate.snapshot)
        character = dict(snapshot["character"])
        character["level"] = None
        snapshot["character"] = character
        changed = candidate.__class__(**{**candidate.__dict__, "snapshot": snapshot})

        report = SimcReadinessValidator().validate(changed, self.capabilities)

        self.assertEqual(report.readiness, SourceReadiness.READY_FOR_SIMC)
        self.assertNotIn("CHARACTER_LEVEL_MISSING", report.blockers)

    def test_missing_required_gear_and_runtime_support_is_incomplete(self):
        candidate = candidate_from_fixture()
        snapshot = dict(candidate.snapshot)
        gear = dict(snapshot["gear"])
        gear.pop("trinket2")
        snapshot["gear"] = gear
        changed = candidate.__class__(
            **{**candidate.__dict__, "snapshot": snapshot}
        )
        report = SimcReadinessValidator().validate(
            changed,
            SimcRuntimeCapabilities(
                runtime_revision="",
                compiler_revision="",
                supported_specs=frozenset(),
            ),
        )

        self.assertEqual(report.readiness, SourceReadiness.INCOMPLETE_FOR_SIMC)
        self.assertIn("GEAR_TRINKET2_MISSING", report.blockers)
        self.assertIn("RUNTIME_UNAVAILABLE", report.blockers)

    def test_generated_or_preview_profile_can_never_be_ready(self):
        candidate = candidate_from_fixture()
        snapshot = dict(candidate.snapshot)
        snapshot["profileSource"] = "generated"
        changed = candidate.__class__(**{**candidate.__dict__, "snapshot": snapshot})

        report = SimcReadinessValidator().validate(changed, self.capabilities)

        self.assertEqual(report.readiness, SourceReadiness.INCOMPLETE_FOR_SIMC)
        self.assertIn("PROFILE_NOT_REAL_SOURCE", report.blockers)


if __name__ == "__main__":
    unittest.main()
