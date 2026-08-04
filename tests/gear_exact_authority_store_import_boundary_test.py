import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "server" / "gear_exact_authority_store.py"


ALLOWED_FROM_IMPORTS = {
    "__future__": {"annotations"},
    "dataclasses": {"dataclass"},
    "typing": {"Any"},
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
ALLOWED_MODULE_IMPORTS = {"re"}
FORBIDDEN_DYNAMIC_IMPORT_CALLS = {"__import__", "compile", "eval", "exec"}


def import_boundary_violations(source):
    tree = ast.parse(source)
    violations = []
    observed_from = {}
    observed_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname is not None or alias.name not in ALLOWED_MODULE_IMPORTS:
                    violations.append(f"unauthorized module import: {alias.name}")
                else:
                    observed_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = {alias.name for alias in node.names}
            if (
                node.level != 0
                or module not in ALLOWED_FROM_IMPORTS
                or any(alias.asname is not None for alias in node.names)
                or not names <= ALLOWED_FROM_IMPORTS.get(module, set())
            ):
                violations.append(f"unauthorized from import: {module}")
            else:
                observed_from.setdefault(module, set()).update(names)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FORBIDDEN_DYNAMIC_IMPORT_CALLS
        ):
            violations.append(f"dynamic import bypass: {node.func.id}")
    if observed_from != ALLOWED_FROM_IMPORTS:
        violations.append("exact from-import contract mismatch")
    if observed_modules != ALLOWED_MODULE_IMPORTS:
        violations.append("exact module-import contract mismatch")
    return violations


class GearExactAuthorityStoreImportBoundaryTest(unittest.TestCase):
    def test_store_imports_only_typed_reload_and_sealed_typing_from_domain(self):
        self.assertEqual(
            import_boundary_violations(STORE.read_text(encoding="utf-8")),
            [],
        )

    def test_import_mutations_cannot_bypass_exact_module_symbol_allowlist(self):
        source = STORE.read_text(encoding="utf-8")
        mutations = (
            "import server.gear_exact_authority as authority",
            "from server import gear_exact_authority",
            "from server.gear_track_authority import resolve_exact_instance_progression",
            "from server.gear_exact_authority import _validate_progression_payload",
            "from server.gear_exact_authority import reload_exact_progression as hidden",
            "from server.gear_canonical_kernel import canonical_json_bytes",
            "from server.gear_catalog_store import GearCatalogStore",
            "from .gear_exact_authority import reload_exact_progression",
            "import json",
            "__import__('server.gear_exact_authority')",
            "exec('import server.gear_exact_authority')",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertTrue(import_boundary_violations(source + "\n" + mutation))

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
