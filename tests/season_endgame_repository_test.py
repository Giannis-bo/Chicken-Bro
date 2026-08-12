import unittest

from server.season_endgame_repository import build_endgame_binding


class SeasonEndgameRepositoryTest(unittest.TestCase):
    def _binding(self, **overrides):
        values = {
            "season_id": "midnight-season-2",
            "season_metadata": {
                "label": "至暗之夜 Season 2",
                "captureContext": {
                    "officialAnnouncementRefs": ["blizzard-s2"],
                },
            },
            "source_policy": {
                "scope": "end_game",
                "sourcePolicyRevision": "s2-policy-r1",
                "sources": [
                    {
                        "sourceKey": "raid:venomous-abyss",
                        "required": True,
                    },
                ],
            },
            "capture_manifest": {
                "captureRevision": "capture-s2-r1",
                "files": [{"path": "raw.json", "sha256": "a" * 64}],
            },
            "client_build": "12.1.0.69214",
            "simc_runtime_revision": "simc:12.1.0.69214:abc",
        }
        values.update(overrides)
        return build_endgame_binding(**values)

    def test_binding_is_deterministic_and_contains_complete_endgame_scope(self):
        first = self._binding()
        second = self._binding()

        self.assertEqual(first, second)
        self.assertTrue(
            first["seasonRevision"].startswith("season-midnight-season-2:")
        )
        self.assertEqual(first["scope"], "end_game")
        self.assertNotIn("availabilityStage", first)
        self.assertEqual(first["status"], "verified")

    def test_missing_capture_or_runtime_identity_blocks_without_s1_fallback(self):
        result = self._binding(
            source_policy={
                "scope": "end_game",
                "sourcePolicyRevision": "s2-policy-r1",
                "sources": [],
            },
            capture_manifest={},
            client_build="",
            simc_runtime_revision="",
        )

        self.assertIn(
            "S2_CAPTURE_IDENTITY_MISSING",
            {row["code"] for row in result["problems"]},
        )
        self.assertNotEqual(
            result.get("seasonRevision"),
            "season-17-f131dd36ddf1",
        )
        self.assertEqual(result["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
