import tempfile
import unittest
from pathlib import Path

from init_langfuse import initialize


class InitializationTest(unittest.TestCase):
    def test_private_idempotent_credentials_preserve_existing_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.langfuse"
            path.write_text("# keep this comment\nCUSTOM=unchanged\nLANGFUSE_INIT_USER_EMAIL=reviewer@example.org\n")
            first = initialize(path)
            content = path.read_text()
            second = initialize(path)
            self.assertEqual(first, second)
            self.assertEqual(content, path.read_text())
            self.assertEqual(first["CUSTOM"], "unchanged")
            self.assertEqual(first["LANGFUSE_INIT_USER_EMAIL"], "reviewer@example.org")
            self.assertTrue(first["LANGFUSE_PUBLIC_KEY"].startswith("pk-lf-"))
            self.assertTrue(first["LANGFUSE_SECRET_KEY"].startswith("sk-lf-"))
            self.assertEqual(len(first["LANGFUSE_ENCRYPTION_KEY"]), 64)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn("# keep this comment", content)


if __name__ == "__main__":
    unittest.main()
