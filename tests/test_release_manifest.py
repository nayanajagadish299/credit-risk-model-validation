import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import refresh_release_manifest as release


class TestReleaseAllowlist(unittest.TestCase):
    def test_reviewed_allowlist_is_explicit_and_excludes_row_level_outputs(self):
        paths = release.read_allowlist(ROOT / "tools" / "sba_release_allowlist.txt")
        relative = {p.relative_to(ROOT).as_posix() for p in paths}
        self.assertIn("docs/TASK6_FINAL_RESEARCH_FINDINGS.md", relative)
        self.assertIn("scripts/sba_task6d1_asof_sensitivity.py", relative)
        self.assertFalse(any("task6d2" in p.lower() for p in relative))
        self.assertFalse(any("predictions" in Path(p).name.lower() for p in relative))

    def test_rejects_parent_traversal(self):
        allowlist = ROOT / "tools" / "sba_release_allowlist.txt"
        with patch.object(Path, "read_text", return_value="../private.csv\n"):
            with self.assertRaisesRegex(ValueError, "Unsafe path"):
                release.read_allowlist(allowlist)


if __name__ == "__main__":
    unittest.main()
