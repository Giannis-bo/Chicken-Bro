import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "server" / "app"
DOMAIN_FORBIDDEN = ("fastapi", "pydantic", "psycopg", "server.news_backend", "server.simulator_payload")
LEGACY_FORBIDDEN = ("server.news_backend", "server.simulator_payload", "server.websim_payload")


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


class AppArchitectureTest(unittest.TestCase):
    def test_domain_is_framework_and_adapter_free(self):
        for path in APP.glob("*/domain.py"):
            imports = imported_modules(path)
            for forbidden in DOMAIN_FORBIDDEN:
                self.assertFalse(any(name == forbidden or name.startswith(f"{forbidden}.") for name in imports), path)

    def test_new_app_never_imports_legacy_owners(self):
        for path in APP.rglob("*.py"):
            imports = imported_modules(path)
            for forbidden in LEGACY_FORBIDDEN:
                self.assertFalse(any(name == forbidden or name.startswith(f"{forbidden}.") for name in imports), path)
