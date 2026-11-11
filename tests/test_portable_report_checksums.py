import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_portable_report_checksums as checks


class TestPortableReportChecksums(unittest.TestCase):
    def _fixture(self, directory: Path, original_bytes: bytes):
        report = directory / "report.csv"
        report.write_bytes(original_bytes)
        raw_hash = hashlib.sha256(original_bytes).hexdigest()
        source_path = directory / "source_manifest.json"
        source_path.write_text(json.dumps({"report_sha256": {"report.csv": raw_hash}}), encoding="utf-8")
        index_path = directory / "portable_checksums.json"
        record = {
            "report_path": "report.csv",
            "source_run_manifest": "source_manifest.json",
            "source_manifest_key": "report_sha256",
            "source_manifest_report_key": "report.csv",
            "source_run_raw_byte_sha256": raw_hash,
            "portable_lf_sha256": hashlib.sha256(checks.normalized_text_bytes(original_bytes)).hexdigest(),
        }
        index_path.write_text(json.dumps({
            "schema_version": 1,
            "normalization": "CRLF bytes replaced by LF bytes; all other bytes unchanged",
            "reports": [record],
        }), encoding="utf-8")
        return report, index_path

    def test_crlf_and_lf_equivalent_reports_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report, index = self._fixture(root, b"a,b\r\n1,2\r\n")
            expected_raw = hashlib.sha256(report.read_bytes()).hexdigest()
            report.write_bytes(b"a,b\n1,2\n")
            with patch.object(checks, "ROOT", root):
                result = checks.verify_index(index)
            self.assertEqual(result["reports_verified"], 1)
            self.assertEqual(result["raw_byte_hashes_matching_current_files"], 0)
            self.assertEqual(expected_raw, json.loads(index.read_text())["reports"][0]["source_run_raw_byte_sha256"])

    def test_changed_report_content_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report, index = self._fixture(root, b"a,b\r\n1,2\r\n")
            report.write_bytes(b"a,b\n1,3\n")
            with patch.object(checks, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "Portable report checksum mismatch"):
                    checks.verify_index(index)


if __name__ == "__main__":
    unittest.main()
