import tempfile
import unittest
from pathlib import Path

from tests.s2_crafted_closure_fixture import write_crafted_capture


class S2CraftedClosureTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.capture_root = write_crafted_capture(Path(self.directory.name) / "capture")

    def test_recipe_probe_closes_output_and_quality_but_not_option_semantics(self):
        from server.s2_crafted_closure import build_crafted_closure_report

        report = build_crafted_closure_report(
            self.capture_root,
            recipe_id="52446",
        )

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["recipeOutput"], {
            "status": "verified",
            "recipeId": "52446",
            "spellId": "1229890",
            "craftingDataId": "2826",
            "itemId": "244767",
        })
        self.assertEqual(report["craftingQuality"]["status"], "verified")
        self.assertEqual(report["craftingQuality"]["qualityTiers"], [1, 2, 3, 4, 5])
        self.assertEqual(
            report["slots"]["amplify_secondary_stat"]["status"],
            "UNVERIFIED",
        )
        self.assertEqual(
            report["slots"]["add_embellishment"]["status"],
            "UNVERIFIED",
        )
        self.assertIn(
            "SECONDARY_OPTION_SEMANTICS_UNVERIFIED",
            report["blockerCodes"],
        )
        self.assertIn(
            "EMBELLISHMENT_EFFECT_UNVERIFIED",
            report["blockerCodes"],
        )
        self.assertEqual(report["simcReadiness"]["status"], "blocked")
        self.assertIn(
            "SIMC_RUNTIME_IDENTITY_UNAVAILABLE",
            report["simcReadiness"]["blockerCodes"],
        )

    def test_report_never_promotes_candidate_ids_to_stat_or_effect_identities(self):
        from server.s2_crafted_closure import build_crafted_closure_report

        report = build_crafted_closure_report(
            self.capture_root,
            recipe_id="52446",
        )

        for slot in report["slots"].values():
            self.assertEqual(slot["semanticOptions"], [])
            self.assertNotIn("crafted_stats", str(slot))
            self.assertNotIn("effectId", slot)
        self.assertFalse(report["simcReadiness"]["probes"])
        self.assertFalse(report["activeManifestChanged"])
        self.assertFalse(report["productionWritten"])

    def test_simc_probe_keeps_zero_exit_separate_from_runtime_and_source_readiness(self):
        from server.s2_crafted_closure import build_crafted_closure_report

        probe = {
            "schemaRevision": "s2-crafted-simc-probe-v1",
            "clientBuild": "12.1.0.69299",
            "runtimeIdentity": {
                "build": "12.1.0.69299",
                "commit": "f" * 40,
                "binarySha256": "a" * 64,
            },
            "sourceCompatibilityVerified": False,
            "probes": [
                {
                    "option": "32/36",
                    "returncode": 0,
                    "encodedItem": (
                        "quel_dorei_softsteppers,id=244767,"
                        "ilevel=285,crafted_stats=32/36"
                    ),
                    "itemLevel": 285,
                    "stats": {"intellect": 90, "stamina": 1664},
                    "stderr": "Trivial item name warning",
                }
            ],
        }

        report = build_crafted_closure_report(
            self.capture_root,
            recipe_id="52446",
            simc_probe=probe,
        )

        self.assertEqual(report["simcReadiness"]["status"], "blocked")
        self.assertEqual(
            report["simcReadiness"]["runtimeRevision"],
            "f" * 40,
        )
        self.assertIn(
            "SIMC_CLIENT_BUILD_MISMATCH",
            report["simcReadiness"]["blockerCodes"],
        )
        self.assertIn(
            "SIMC_SOURCE_COMPATIBILITY_UNVERIFIED",
            report["simcReadiness"]["blockerCodes"],
        )
        self.assertIn(
            "SIMC_ITEM_RESOLUTION_WARNING",
            report["simcReadiness"]["blockerCodes"],
        )


if __name__ == "__main__":
    unittest.main()
