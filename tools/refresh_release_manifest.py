#!/usr/bin/env python3
"""Refresh release checksums from a reviewed, explicit path allowlist.

No directory-wide discovery is performed. Every release refresh must name an
allowlist file; row-level data and local absolute paths are rejected.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "RELEASE_MANIFEST.json"
TEXT_EXTENSIONS = {".py", ".json", ".md", ".csv", ".txt", ".gitignore", ".yaml", ".yml", ".toml"}
FORBIDDEN_SUFFIXES = {".csv.gz", ".parquet", ".feather", ".xlsx", ".xls", ".sqlite", ".db"}
FORBIDDEN_NAMES = ("foia_", "strict_train", "strict_test", "locked_test", "predictions_local")


def canonical_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_EXTENSIONS or path.name == ".gitignore":
        data = data.replace(b"\r\n", b"\n")
    return data


def read_allowlist(path: Path) -> list[Path]:
    resolved_list = path.resolve()
    try:
        resolved_list.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("Allowlist must be inside the repository") from exc
    entries = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts or "\\" in value:
            raise ValueError(f"Unsafe path at allowlist line {line_number}: {value}")
        target = (ROOT / candidate).resolve()
        try:
            target.relative_to(ROOT)
        except ValueError as exc:
            raise ValueError(f"Path escapes repository at line {line_number}: {value}") from exc
        lowered = value.lower()
        if any(lowered.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
            raise ValueError(f"Row-level or source-data format is not releaseable: {value}")
        if any(Path(value).name.lower().startswith(prefix) for prefix in FORBIDDEN_NAMES):
            raise ValueError(f"Potential raw/loan-level file is not releaseable: {value}")
        if not target.is_file():
            raise ValueError(f"Allowlist path is missing or not a file: {value}")
        entries.append(target)
    if not entries:
        raise ValueError("Allowlist contains no files")
    if len(entries) != len(set(entries)):
        raise ValueError("Allowlist contains duplicate paths")
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allowlist-file", type=Path, required=True,
                        help="Repository-relative or absolute path to an in-repository reviewed path list")
    args = parser.parse_args()
    allowlist = args.allowlist_file if args.allowlist_file.is_absolute() else ROOT / args.allowlist_file
    paths = read_allowlist(allowlist)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["files"] = []
    for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix()):
        raw = canonical_bytes(path)
        manifest["files"].append({
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    manifest["review_status"] = "sba_task6_publication_candidate_reviewed_aggregate_only"
    manifest["manifest_updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["checksum_policy"] = "LF-canonicalized text; raw bytes for binary assets"
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Refreshed release manifest from explicit allowlist: {len(paths)} files.")


if __name__ == "__main__":
    main()
