from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "server" / "requirements.txt"


class AppDependencyManifestTest(unittest.TestCase):
    def test_product_dependencies_are_exact_and_do_not_add_a_broker(self):
        self.assertTrue(LOCK.is_file(), "product dependency lock is missing")
        lines = [
            line.strip()
            for line in LOCK.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(
            lines,
            [
                "fastapi==0.141.1",
                "httpx==0.28.1",
                "psycopg[binary]==3.3.4",
                "pydantic==2.13.5",
                "uvicorn==0.52.4",
                "Pillow==12.3.0",
            ],
        )
        lowered = "\n".join(lines).lower()
        for forbidden in ("celery", "redis", "kafka", "rabbitmq"):
            self.assertNotIn(forbidden, lowered)
