import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "server" / "gear_exact_authority_store.py"


class GearExactAuthorityStoreImportBoundaryTest(unittest.TestCase):
    def test_store_imports_only_typed_reload_and_sealed_typing_from_domain(self):
        tree = ast.parse(STORE.read_text(encoding="utf-8"))
        allowed = {
            "server.gear_canonical_kernel": {"SealedCanonicalDocument"},
            "server.gear_exact_item_instance": {
                "reload_exact_item", "reload_exact_static_facts",
            },
            "server.gear_exact_authority": {
                "reload_exact_progression", "reload_exact_authority_envelope",
            },
            "server.simc_item_effect_support": {
                "reload_effect_record", "reload_effect_aggregate",
            },
        }
        forbidden_tokens = {
            "gear_catalog", "canonical_json_bytes", "seal_canonical_document",
            "verified_payload_copy", "_validate_", "_rehydrate_",
        }
        observed = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in allowed:
                names = {alias.name for alias in node.names}
                observed.setdefault(node.module, set()).update(names)
                self.assertLessEqual(names, allowed[node.module])
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                rendered = ast.unparse(node)
                for token in forbidden_tokens:
                    self.assertNotIn(token, rendered)
        self.assertEqual(observed, allowed)

    def test_registry_universe_remains_five_targets_nine_exemptions(self):
        import json

        registry = json.loads((
            ROOT / "tests" / "fixtures" / "gear_canonical_owner_registry.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(len(registry["targets"]), 5)
        self.assertEqual(
            sum(len(target["exemptions"]) for target in registry["targets"]),
            9,
        )
        self.assertEqual(registry["proofClaim"], "source_change_control_only")


if __name__ == "__main__":
    unittest.main()
