#!/usr/bin/env python3
"""Verify portable hashes for text reports while preserving source-run hashes.

Original raw-byte SHA-256 values remain in their scientific run manifests. The
curated checksum index records those values as provenance alongside a portable
SHA-256 computed after CRLF-to-LF normalization. Verification never refreshes
the expected hashes, so content changes fail instead of being accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "results" / "portable_report_checksums.json"
TEXT_SUFFIXES = {".csv", ".json", ".md", ".txt"}


def normalized_text_bytes(data: bytes) -> bytes:
    """Normalize Windows CRLF only; preserve every other byte exactly."""
    return data.replace(b"\r\n", b"\n")


def portable_sha256(path: Path) -> str:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        raise ValueError(f"Portable report checksum is only for text files: {path}")
    return hashlib.sha256(normalized_text_bytes(path.read_bytes())).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_file(relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Unsafe repository-relative path: {relative}")
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"Path escapes repository: {relative}") from exc
    if not resolved.is_file():
        raise ValueError(f"Required checksum file is missing: {relative}")
    return resolved


def verify_index(index_path: Path = INDEX) -> dict[str, Any]:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("schema_version") != 1:
        raise ValueError("Unsupported portable checksum index schema")
    if index.get("normalization") != "CRLF bytes replaced by LF bytes; all other bytes unchanged":
        raise ValueError("Unexpected portable checksum normalization policy")
    records = index.get("reports")
    if not isinstance(records, list) or not records:
        raise ValueError("Portable checksum index has no report records")

    seen: set[str] = set()
    raw_matches = 0
    for record in records:
        report_rel = record["report_path"]
        if report_rel in seen:
            raise ValueError(f"Duplicate portable checksum entry: {report_rel}")
        seen.add(report_rel)
        report = _repo_file(report_rel)
        source_manifest = _repo_file(record["source_run_manifest"])
        source = json.loads(source_manifest.read_text(encoding="utf-8"))
        source_key = record["source_manifest_key"]
        source_hashes = source[source_key]
        expected_raw = source_hashes[record["source_manifest_report_key"]]
        if expected_raw != record["source_run_raw_byte_sha256"]:
            raise ValueError(f"Source-run raw hash provenance mismatch: {report_rel}")

        actual_portable = portable_sha256(report)
        if actual_portable != record["portable_lf_sha256"]:
            raise ValueError(f"Portable report checksum mismatch: {report_rel}")
        if raw_sha256(report) == expected_raw:
            raw_matches += 1

    return {"reports_verified": len(records), "raw_byte_hashes_matching_current_files": raw_matches}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=INDEX,
                        help="Portable checksum index (defaults to results/portable_report_checksums.json)")
    args = parser.parse_args()
    index_path = args.index if args.index.is_absolute() else ROOT / args.index
    result = verify_index(index_path)
    print("Portable report checksum verification: PASS")
    print(f"Reports verified: {result['reports_verified']}")
    print("Raw-byte hashes matching current files: "
          f"{result['raw_byte_hashes_matching_current_files']} (may be lower after Git line-ending conversion)")


if __name__ == "__main__":
    main()
