#!/usr/bin/env python3
"""Validate the v2 source package without calling live public APIs."""

from __future__ import annotations

import argparse
import hashlib
import json
import py_compile
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT_REQUIRED = [
    "README.md",
    "PRD.md",
    "SKILL.md",
    "MCP_TOOL_SPEC.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "mcp/tool-definitions.json",
    "src/kr_apartment_market/server.py",
    "src/real_estate/LICENSE",
    "licenses/real-estate-mcp-MIT.txt",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    failures: list[str] = []

    def check(condition: bool, label: str, detail: str = "") -> None:
        marker = "PASS" if condition else "FAIL"
        print(f"[{marker}] {label}" + (f": {detail}" if detail else ""))
        if not condition:
            failures.append(label)

    missing = [name for name in ROOT_REQUIRED if not (root / name).is_file()]
    check(not missing, "required-files", ", ".join(missing) if missing else "all present")

    try:
        pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        version = pyproject["project"]["version"]
        check(version == "2.0.0", "package-version", version)
    except Exception as exc:
        check(False, "package-version", str(exc))

    try:
        catalog = json.loads((root / "mcp/tool-definitions.json").read_text(encoding="utf-8"))
        catalog_names = [item["name"] for item in catalog["tools"]]
        check(len(catalog_names) == 17, "canonical-catalog-count", str(len(catalog_names)))
        check(len(catalog_names) == len(set(catalog_names)), "canonical-catalog-unique")
    except Exception as exc:
        catalog_names = []
        check(False, "canonical-catalog", str(exc))

    sys.path.insert(0, str(root / "src"))
    try:
        from kr_apartment_market.config import Settings
        from kr_apartment_market.server import create_mcp

        with tempfile.TemporaryDirectory() as temp:
            settings = Settings(
                data_go_kr_api_key="fixture",
                odcloud_api_key="",
                odcloud_service_key="",
                timezone="Asia/Seoul",
                http_timeout_seconds=5,
                retry_count=0,
                page_size=100,
                max_pages=5,
                max_months=12,
                watchlist_path=Path(temp) / "watchlist.json",
                enable_upstream_compat=True,
            )
            _, canonical = create_mcp(settings=settings, enable_upstream_compat=False)
            _, integrated = create_mcp(settings=settings, enable_upstream_compat=True)
        check(canonical == catalog_names, "catalog-runtime-name-match")
        check(len(integrated) == 33, "integrated-tool-count", str(len(integrated)))
    except Exception as exc:
        check(False, "runtime-registration", str(exc))

    source_files = sorted((root / "src").rglob("*.py"))
    compile_errors: list[str] = []
    for source in source_files:
        try:
            py_compile.compile(str(source), doraise=True)
        except py_compile.PyCompileError as exc:
            compile_errors.append(str(exc))
    check(not compile_errors, "python-compile", f"files={len(source_files)}")

    region_file = root / "src/kr_apartment_market/resources/region_codes.tsv"
    region_count = max(0, len(region_file.read_text(encoding="utf-8").splitlines()) - 1)
    check(region_count >= 200, "offline-region-table", f"rows={region_count}")

    third_party = (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    upstream_license = (root / "licenses/real-estate-mcp-MIT.txt").read_text(encoding="utf-8")
    check("tae0y/real-estate-mcp" in third_party, "third-party-attribution")
    check("Copyright (c) 2026 tae0y" in upstream_license, "upstream-license")

    tracked_files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in {"__pycache__", ".pytest_cache", ".git", "dist", "build"} for part in path.parts)
    ]
    manifest = {
        "manifestVersion": "2.0.0",
        "fileCount": len(tracked_files),
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in sorted(tracked_files)
            if path.name != "MANIFEST.json"
        ],
    }
    if args.write_manifest:
        (root / "MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"[PASS] manifest-written: files={len(manifest['files'])}")

    if failures:
        print(f"\n{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("\nAll static package checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
