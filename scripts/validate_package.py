#!/usr/bin/env python3
"""Static validation for KR Apartment Market AI Skill v3.0.0.

The validator deliberately avoids live public API calls. Runtime behavior is
covered by tests/runtime and scripts/validate_runtime.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import py_compile
import re
import sys
import tempfile
import tomllib
from pathlib import Path
from urllib.parse import urlparse

VERSION = "3.0.0"
CANONICAL_TOOL_COUNT = 32
INTEGRATED_TOOL_COUNT = 48
LISTING_SOURCE_COUNT = 11

ROOT_REQUIRED = [
    "README.md",
    "PRD.md",
    "SKILL.md",
    "MCP_TOOL_SPEC.md",
    "RELEASE_NOTES-v3.0.0.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    ".env.example",
    ".mcp.json",
    "index.html",
    "mcp/tool-definitions.json",
    "database/schema.sql",
    "database/migrations/003_home_finder.sql",
    "docs/HOME_FINDER_ARCHITECTURE.md",
    "docs/SCORING_MODEL.md",
    "docs/LISTING_SOURCE_POLICY.md",
    "docs/MIGRATION_v2_TO_v3.md",
    "evals/home-finder-prompts.yaml",
    "src/kr_apartment_market/server.py",
    "src/kr_apartment_market/home/models.py",
    "src/kr_apartment_market/home/scoring.py",
    "src/kr_apartment_market/home/recommender.py",
    "src/kr_apartment_market/home/listing_links.py",
    "src/kr_apartment_market/home/storage.py",
    "src/kr_apartment_market/resources/listing_sources.json",
    "src/real_estate/LICENSE",
    "licenses/real-estate-mcp-MIT.txt",
]

EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "dist",
    "build",
    ".venv",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tracked_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not any(part in EXCLUDED_PARTS for part in path.parts)
    )


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

    # Package metadata.
    try:
        pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        version = pyproject["project"]["version"]
        check(version == VERSION, "package-version", version)
        check(
            "home-finder" in pyproject["project"].get("keywords", []),
            "package-home-finder-keyword",
        )
        package_data = pyproject["tool"]["setuptools"]["package-data"]["kr_apartment_market"]
        check("resources/*.json" in package_data, "listing-registry-package-data")
    except Exception as exc:
        check(False, "package-metadata", str(exc))

    # Main documents.
    for rel in ["README.md", "PRD.md", "SKILL.md", "MCP_TOOL_SPEC.md"]:
        try:
            text = (root / rel).read_text(encoding="utf-8")
            check("v3.0.0" in text or "3.0.0" in text, f"document-version:{rel}")
        except Exception as exc:
            check(False, f"document-read:{rel}", str(exc))

    try:
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        check(skill.startswith("---\n"), "skill-front-matter")
        check("kr_home.recommend_complexes" in skill, "skill-home-finder-workflow")
        check("LINK_OUT_ONLY" in skill, "skill-listing-policy")
        check("match_score" in skill and "confidence_score" in skill, "skill-score-separation")
    except Exception as exc:
        check(False, "skill-contract", str(exc))

    # Machine catalog.
    try:
        catalog = json.loads((root / "mcp/tool-definitions.json").read_text(encoding="utf-8"))
        catalog_names = [item["name"] for item in catalog["tools"]]
        check(catalog.get("catalogVersion") == VERSION, "catalog-version", str(catalog.get("catalogVersion")))
        check(len(catalog_names) == CANONICAL_TOOL_COUNT, "canonical-catalog-count", str(len(catalog_names)))
        check(len(catalog_names) == len(set(catalog_names)), "canonical-catalog-unique")
        check(sum(name.startswith("kr_apartment.") for name in catalog_names) == 17, "market-tool-count")
        check(sum(name.startswith("kr_home.") for name in catalog_names) == 15, "home-tool-count")
        check(
            all("inputSchema" in item and "outputSchema" in item for item in catalog["tools"]),
            "catalog-schema-presence",
        )
    except Exception as exc:
        catalog_names = []
        check(False, "canonical-catalog", str(exc))

    # Runtime registration without invoking external APIs.
    sys.dont_write_bytecode = True
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
                home_finder_path=Path(temp) / "home_finder.json",
            )
            _, canonical = create_mcp(settings=settings, enable_upstream_compat=False)
            _, integrated = create_mcp(settings=settings, enable_upstream_compat=True)
        check(canonical == catalog_names, "catalog-runtime-name-match")
        check(len(canonical) == CANONICAL_TOOL_COUNT, "canonical-runtime-count", str(len(canonical)))
        check(len(integrated) == INTEGRATED_TOOL_COUNT, "integrated-tool-count", str(len(integrated)))
        check(len(integrated) == len(set(integrated)), "integrated-tool-unique")
    except Exception as exc:
        check(False, "runtime-registration", str(exc))

    # Python syntax.
    source_files = sorted((root / "src").rglob("*.py")) + sorted((root / "scripts").rglob("*.py"))
    compile_errors: list[str] = []
    with tempfile.TemporaryDirectory() as compile_temp:
        compile_root = Path(compile_temp)
        for index, source in enumerate(source_files):
            try:
                py_compile.compile(
                    str(source),
                    cfile=str(compile_root / f"{index}.pyc"),
                    doraise=True,
                )
            except py_compile.PyCompileError as exc:
                compile_errors.append(str(exc))
    check(not compile_errors, "python-compile", f"files={len(source_files)}")
    if compile_errors:
        for error in compile_errors[:5]:
            print(error)

    # Resources.
    try:
        region_file = root / "src/kr_apartment_market/resources/region_codes.tsv"
        region_count = max(0, len(region_file.read_text(encoding="utf-8").splitlines()) - 1)
        check(region_count >= 200, "offline-region-table", f"rows={region_count}")
    except Exception as exc:
        check(False, "offline-region-table", str(exc))

    try:
        registry = json.loads(
            (root / "src/kr_apartment_market/resources/listing_sources.json").read_text(encoding="utf-8")
        )
        sources = registry["sources"]
        ids = [item["id"] for item in sources]
        check(registry.get("registryVersion") == VERSION, "listing-registry-version")
        check(len(sources) == LISTING_SOURCE_COUNT, "listing-source-count", str(len(sources)))
        check(len(ids) == len(set(ids)), "listing-source-unique")
        check(
            {"naver", "daangn", "peterpan", "asil", "kb"}.issubset(ids),
            "default-listing-sources",
        )
        check(all(item.get("accessMode") == "LINK_OUT_ONLY" for item in sources), "listing-default-link-only")
        check(
            all(urlparse(item["homepage"]).scheme == "https" for item in sources),
            "listing-homepage-https",
        )
        check(all(item.get("domains") for item in sources), "listing-domain-allowlists")
    except Exception as exc:
        check(False, "listing-registry", str(exc))

    # Source policy implementation invariants.
    try:
        listing_code = (root / "src/kr_apartment_market/home/listing_links.py").read_text(encoding="utf-8")
        check('parsed.scheme != "https"' in listing_code, "listing-url-https-only")
        check("ipaddress.ip_address" in listing_code, "listing-url-private-ip-guard")
        check("does not scrape" in listing_code.lower(), "listing-no-scrape-module-contract")
        check('"listing_count": None' in listing_code, "listing-count-null-without-adapter")
        home_tool_code = (root / "src/kr_apartment_market/tools/home.py").read_text(encoding="utf-8")
        check("baseline_status" in home_tool_code and "NO_BASELINE" in home_tool_code, "saved-search-baseline-status")
    except Exception as exc:
        check(False, "listing-code-policy", str(exc))

    # Database invariants.
    try:
        schema = (root / "database/schema.sql").read_text(encoding="utf-8")
        migration = (root / "database/migrations/003_home_finder.sql").read_text(encoding="utf-8")
        combined = schema + "\n" + migration
        check("CREATE SCHEMA IF NOT EXISTS finder" in combined, "sql-finder-schema")
        check("CREATE SCHEMA IF NOT EXISTS listing" in combined, "sql-listing-schema")
        check("finder.search_profile" in combined, "sql-search-profile")
        check("finder.candidate_score_component" in combined, "sql-score-components")
        check("listing.source_access_policy" in combined, "sql-source-policy")
        check("allow_automated_collection" in combined, "sql-collection-policy")
        check("enforce_listing_observation_policy" in combined, "sql-observation-policy-trigger")
        check("FORCE ROW LEVEL SECURITY" in combined, "sql-force-rls")
    except Exception as exc:
        check(False, "sql-invariants", str(exc))

    # License attribution.
    try:
        third_party = (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        upstream_license = (root / "licenses/real-estate-mcp-MIT.txt").read_text(encoding="utf-8")
        check("tae0y/real-estate-mcp" in third_party, "third-party-attribution")
        check("Copyright (c) 2026 tae0y" in upstream_license, "upstream-license")
    except Exception as exc:
        check(False, "license-attribution", str(exc))

    # No committed secrets or local data.
    files = tracked_files(root)
    paths = [path.relative_to(root).as_posix() for path in files]
    check(".env" not in paths, "no-dotenv-secret-file")
    check(not any(path.startswith(".data/") for path in paths), "no-local-user-data")
    suspicious: list[str] = []
    secret_pattern = re.compile(r"(?i)(servicekey|api[_-]?key)\s*[=:]\s*['\"]?[A-Za-z0-9%+/=_-]{24,}")
    for path in files:
        if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".toml", ".sql", ".example"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if secret_pattern.search(text) and "your_api_key" not in text.lower():
            suspicious.append(path.relative_to(root).as_posix())
    check(not suspicious, "no-hardcoded-secrets", ", ".join(suspicious[:5]))

    # Landing page.
    try:
        html = (root / "index.html").read_text(encoding="utf-8")
        check("KR Apartment Market" in html and "AI Home Finder" in html, "landing-v3-branding")
        check("og:image" in html and "images/logo.png" in html, "landing-og-image")
        check("github.com/JTech-CO/kr-apartment-market-skill" in html, "landing-github-link")
    except Exception as exc:
        check(False, "landing-page", str(exc))

    # Evaluation suite.
    try:
        eval_text = (root / "evals/home-finder-prompts.yaml").read_text(encoding="utf-8")
        case_count = len(re.findall(r"^\s*- id: HOME-", eval_text, flags=re.MULTILINE))
        check(case_count >= 25, "home-eval-case-count", str(case_count))
        check("does_not_claim_listing_ingestion" in eval_text, "home-eval-listing-boundary")
    except Exception as exc:
        check(False, "home-evals", str(exc))

    # Reject generated caches in source package.
    bad_cache_paths = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if any(part in {"__pycache__", ".pytest_cache", ".ruff_cache"} for part in path.parts)
    ]
    check(not bad_cache_paths, "source-tree-clean", ", ".join(bad_cache_paths[:5]))

    manifest_files = [path for path in files if path.name != "MANIFEST.json"]
    manifest = {
        "manifestVersion": VERSION,
        "generatedBy": "scripts/validate_package.py",
        "fileCount": len(manifest_files),
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in manifest_files
        ],
    }
    if args.write_manifest:
        (root / "MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"[PASS] manifest-written: files={len(manifest_files)}")

    if failures:
        print(f"\n{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("\nAll v3 static package checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
