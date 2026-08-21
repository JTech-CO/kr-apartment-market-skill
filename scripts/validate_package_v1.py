#!/usr/bin/env python3
"""Static package validator for KR Apartment Market AI Skill.

This validator checks the artifacts that can be validated without a running
PostgreSQL or MCP server:
- required files and SKILL front matter
- YAML/JSON parsing
- JSON Schema 2020-12 validity
- tool-name consistency across SKILL, MCP spec, and catalog
- reference-file existence
- selected access-policy invariants
- conservative SQL lexical and object-name checks

Exit code 0 means all checks passed. It does not replace PostgreSQL migration
execution or MCP protocol conformance tests against a deployed server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit("PyYAML is required: python -m pip install PyYAML") from exc

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit("jsonschema is required: python -m pip install jsonschema") from exc


REQUIRED_FILES = (
    "README.md",
    "PRD.md",
    "MCP_TOOL_SPEC.md",
    "SKILL.md",
    "agents/openai.yaml",
    "database/DATABASE_SCHEMA.md",
    "database/schema.sql",
    "database/seed.sql",
    "mcp/tool-definitions.json",
    "references/DATA_SOURCES.md",
    "references/METRIC_DEFINITIONS.md",
    "references/OUTPUT_CONTRACT.md",
    "references/SAFETY_AND_ACCESS_POLICY.md",
    "evals/golden-prompts.yaml",
)

EXPECTED_TOOLS = {
    "kr_apartment.resolve_location",
    "kr_apartment.search_complexes",
    "kr_apartment.get_complex_snapshot",
    "kr_apartment.get_transactions",
    "kr_apartment.compare_complexes",
    "kr_apartment.get_region_pulse",
    "kr_apartment.rank_complexes",
    "kr_apartment.get_signal_feed",
    "kr_apartment.get_data_freshness",
    "kr_apartment.get_source_link",
    "kr_apartment.get_watchlist",
    "kr_apartment.upsert_watchlist_item",
    "kr_apartment.delete_watchlist_item",
    "kr_apartment.get_watchlist_brief",
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_front_matter(markdown: str) -> dict[str, Any]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", markdown, re.DOTALL)
    if not match:
        raise ValueError("YAML front matter is missing or malformed")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("YAML front matter must be an object")
    return data


def tool_names_from_markdown(markdown: str) -> set[str]:
    return set(re.findall(r"`(kr_apartment\.[a-z0-9_]+)`", markdown))


def mask_sql(sql: str) -> str:
    """Mask comments and string bodies while preserving line/character positions."""
    out = list(sql)
    i = 0
    n = len(sql)
    state = "normal"
    dollar_tag = ""

    def blank(pos: int) -> None:
        if out[pos] != "\n":
            out[pos] = " "

    while i < n:
        if state == "normal":
            if sql.startswith("--", i):
                blank(i)
                if i + 1 < n:
                    blank(i + 1)
                i += 2
                state = "line_comment"
                continue
            if sql.startswith("/*", i):
                blank(i)
                if i + 1 < n:
                    blank(i + 1)
                i += 2
                state = "block_comment"
                continue
            if sql[i] == "'":
                blank(i)
                i += 1
                state = "single_quote"
                continue
            if sql[i] == '"':
                # Keep quoted identifiers intact enough for object extraction, but
                # mask their body to prevent punctuation affecting lexical checks.
                blank(i)
                i += 1
                state = "double_quote"
                continue
            if sql[i] == "$":
                match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", sql[i:])
                if match:
                    dollar_tag = match.group(0)
                    for j in range(i, i + len(dollar_tag)):
                        blank(j)
                    i += len(dollar_tag)
                    state = "dollar_quote"
                    continue
            i += 1
            continue

        if state == "line_comment":
            if sql[i] == "\n":
                state = "normal"
            else:
                blank(i)
            i += 1
            continue

        if state == "block_comment":
            if sql.startswith("*/", i):
                blank(i)
                if i + 1 < n:
                    blank(i + 1)
                i += 2
                state = "normal"
            else:
                blank(i)
                i += 1
            continue

        if state == "single_quote":
            if sql.startswith("''", i):
                blank(i)
                if i + 1 < n:
                    blank(i + 1)
                i += 2
            elif sql[i] == "'":
                blank(i)
                i += 1
                state = "normal"
            else:
                blank(i)
                i += 1
            continue

        if state == "double_quote":
            if sql.startswith('""', i):
                blank(i)
                if i + 1 < n:
                    blank(i + 1)
                i += 2
            elif sql[i] == '"':
                blank(i)
                i += 1
                state = "normal"
            else:
                blank(i)
                i += 1
            continue

        if state == "dollar_quote":
            if sql.startswith(dollar_tag, i):
                for j in range(i, i + len(dollar_tag)):
                    blank(j)
                i += len(dollar_tag)
                state = "normal"
                dollar_tag = ""
            else:
                blank(i)
                i += 1
            continue

    if state not in {"normal", "line_comment"}:
        raise ValueError(f"unterminated SQL lexical state: {state}")
    return "".join(out)


def balanced_parentheses(masked_sql: str) -> tuple[bool, str]:
    stack: list[tuple[int, int]] = []
    line = 1
    col = 0
    for ch in masked_sql:
        if ch == "\n":
            line += 1
            col = 0
            continue
        col += 1
        if ch == "(":
            stack.append((line, col))
        elif ch == ")":
            if not stack:
                return False, f"unmatched ')' at {line}:{col}"
            stack.pop()
    if stack:
        first = stack[-1]
        return False, f"unmatched '(' at {first[0]}:{first[1]}"
    return True, "parentheses balanced"


def extract_created_objects(masked_sql: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r"(?im)^\s*CREATE\s+(?:OR\s+REPLACE\s+)?"
        r"(SCHEMA|TABLE|VIEW|MATERIALIZED\s+VIEW|INDEX|FUNCTION|TRIGGER|POLICY)"
        r"\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_\.]*|[A-Za-z_][A-Za-z0-9_]*)"
    )
    return [(m.group(1).upper().replace("  ", " "), m.group(2)) for m in pattern.finditer(masked_sql)]


def extract_table_columns(masked_sql: str) -> dict[str, set[str]]:
    """Extract table and column names from this package's CREATE TABLE statements."""
    table_pattern = re.compile(
        r"(?im)^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)\s*\("
    )
    tables: dict[str, set[str]] = {}
    for match in table_pattern.finditer(masked_sql):
        table_name = match.group(1)
        start = match.end() - 1
        depth = 0
        end: int | None = None
        for pos in range(start, len(masked_sql)):
            char = masked_sql[pos]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    end = pos
                    break
        if end is None:
            raise ValueError(f"unterminated CREATE TABLE body: {table_name}")

        body = masked_sql[start + 1 : end]
        parts: list[str] = []
        depth = 0
        last = 0
        for pos, char in enumerate(body):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                parts.append(body[last:pos])
                last = pos + 1
        parts.append(body[last:])

        columns: set[str] = set()
        for part in parts:
            stripped = part.strip()
            if not stripped or re.match(
                r"(?i)^(CONSTRAINT|PRIMARY|UNIQUE|CHECK|FOREIGN|EXCLUDE)\b", stripped
            ):
                continue
            column_match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s+", stripped)
            if column_match:
                columns.add(column_match.group(1))
        tables[table_name] = columns
    return tables


def foreign_key_target_errors(masked_sql: str, tables: dict[str, set[str]]) -> list[str]:
    errors: list[str] = []
    reference_pattern = re.compile(
        r"(?i)REFERENCES\s+"
        r"([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)"
        r"\s*\(([^)]+)\)"
    )
    for match in reference_pattern.finditer(masked_sql):
        target_table = match.group(1)
        target_columns = [item.strip() for item in match.group(2).split(",")]
        if target_table not in tables:
            errors.append(f"missing referenced table {target_table}")
            continue
        for column in target_columns:
            if column not in tables[target_table]:
                errors.append(f"missing referenced column {target_table}.{column}")
    return errors


def check_duplicate_objects(objects: Iterable[tuple[str, str]]) -> list[str]:
    # Trigger and policy names are relation-scoped in PostgreSQL, so only check
    # globally unique object kinds here. The package currently uses unique names
    # for all, but avoiding false positives keeps this validator reusable.
    globally_unique_kinds = {"SCHEMA", "TABLE", "VIEW", "MATERIALIZED VIEW", "INDEX", "FUNCTION"}
    counted = Counter(item for item in objects if item[0] in globally_unique_kinds)
    return [f"{kind} {name}" for (kind, name), count in counted.items() if count > 1]


def check_no_unresolved_placeholders(root: Path) -> tuple[bool, str]:
    allowed = {
        "agents/openai.yaml": ["REPLACE_WITH_DEPLOYED_HOST.example"],
        "mcp/tool-definitions.json": ["REPLACE_WITH_DEPLOYED_HOST.example"],
        "MCP_TOOL_SPEC.md": ["api.example.com"],
        "VALIDATION.md": ["placeholder", "REPLACE_WITH_DEPLOYED_HOST.example"],
    }
    pattern = re.compile(r"TODO|TBD|FIXME|REPLACE_WITH|PLACEHOLDER|example\.com", re.IGNORECASE)
    unexpected: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".yaml", ".yml", ".json", ".sql", ".py"}:
            continue
        rel = path.relative_to(root).as_posix()
        if rel == "scripts/validate_package.py":
            continue
        for line_no, line in enumerate(read_text(path).splitlines(), 1):
            if pattern.search(line):
                if any(token in line for token in allowed.get(rel, [])):
                    continue
                unexpected.append(f"{rel}:{line_no}")
    if unexpected:
        return False, "unexpected placeholders: " + ", ".join(unexpected)
    return True, "only documented deployment endpoint placeholders remain"


def validate(root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    missing = [path for path in REQUIRED_FILES if not (root / path).is_file()]
    results.append(CheckResult("required-files", not missing, "all present" if not missing else ", ".join(missing)))

    try:
        skill_text = read_text(root / "SKILL.md")
        front = extract_front_matter(skill_text)
        valid = front.get("name") == "kr-apartment-market" and isinstance(front.get("description"), str) and len(front["description"].strip()) >= 40
        detail = f"name={front.get('name')!r}, description_length={len(str(front.get('description', '')))}"
        results.append(CheckResult("skill-front-matter", valid, detail))
    except Exception as exc:  # noqa: BLE001 - report all validation errors
        skill_text = ""
        results.append(CheckResult("skill-front-matter", False, str(exc)))

    try:
        agent = yaml.safe_load(read_text(root / "agents/openai.yaml"))
        deps = agent.get("dependencies", {}).get("tools", []) if isinstance(agent, dict) else []
        has_mcp = any(item.get("type") == "mcp" and item.get("value") == "kr-apartment-market" for item in deps if isinstance(item, dict))
        endpoint = next((item.get("url") for item in deps if isinstance(item, dict) and item.get("type") == "mcp"), None)
        results.append(CheckResult("agent-yaml", bool(has_mcp and endpoint), f"mcp_dependency={has_mcp}, endpoint={endpoint!r}"))
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult("agent-yaml", False, str(exc)))

    try:
        evals = yaml.safe_load(read_text(root / "evals/golden-prompts.yaml"))
        cases = evals.get("cases", []) if isinstance(evals, dict) else []
        case_ids = [case.get("id") for case in cases if isinstance(case, dict)]
        unique = len(case_ids) == len(set(case_ids)) and None not in case_ids
        results.append(CheckResult("eval-yaml", bool(cases and unique), f"cases={len(cases)}, unique_ids={unique}"))
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult("eval-yaml", False, str(exc)))

    try:
        catalog = json.loads(read_text(root / "mcp/tool-definitions.json"))
        tools = catalog.get("tools", [])
        names = [tool.get("name") for tool in tools]
        schema_count = 0
        schema_errors: list[str] = []
        for tool in tools:
            for key in ("inputSchema", "outputSchema"):
                schema = tool.get(key)
                try:
                    Draft202012Validator.check_schema(schema)
                    schema_count += 1
                except Exception as exc:  # noqa: BLE001
                    schema_errors.append(f"{tool.get('name')}:{key}: {exc}")
        catalog_ok = (
            catalog.get("mcpProtocolVersion") == "2026-07-28"
            and len(names) == len(set(names))
            and set(names) == EXPECTED_TOOLS
            and not schema_errors
        )
        detail = f"tools={len(names)}, schemas={schema_count}, protocol={catalog.get('mcpProtocolVersion')}"
        if schema_errors:
            detail += "; " + " | ".join(schema_errors[:3])
        results.append(CheckResult("mcp-catalog", catalog_ok, detail))
    except Exception as exc:  # noqa: BLE001
        catalog = {}
        results.append(CheckResult("mcp-catalog", False, str(exc)))

    skill_tools = tool_names_from_markdown(skill_text)
    mcp_spec_tools = tool_names_from_markdown(read_text(root / "MCP_TOOL_SPEC.md"))
    catalog_tools = {tool.get("name") for tool in catalog.get("tools", []) if isinstance(tool, dict)}
    consistent = skill_tools == EXPECTED_TOOLS and mcp_spec_tools == EXPECTED_TOOLS and catalog_tools == EXPECTED_TOOLS
    results.append(
        CheckResult(
            "tool-name-consistency",
            consistent,
            f"skill={len(skill_tools)}, spec={len(mcp_spec_tools)}, catalog={len(catalog_tools)}",
        )
    )

    reference_mentions = set(re.findall(r"references/([A-Z0-9_]+\.md)", skill_text))
    missing_refs = [name for name in reference_mentions if not (root / "references" / name).is_file()]
    results.append(CheckResult("skill-reference-files", not missing_refs, f"referenced={len(reference_mentions)}" if not missing_refs else ", ".join(missing_refs)))

    try:
        schema_sql = read_text(root / "database/schema.sql")
        masked = mask_sql(schema_sql)
        parens_ok, parens_detail = balanced_parentheses(masked)
        objects = extract_created_objects(masked)
        duplicates = check_duplicate_objects(objects)
        transaction_wrapper = bool(re.search(r"(?im)^\s*BEGIN\s*;", masked)) and bool(re.search(r"(?im)^\s*COMMIT\s*;", masked))
        sql_ok = parens_ok and not duplicates and transaction_wrapper
        detail = f"objects={len(objects)}, {parens_detail}, transaction_wrapper={transaction_wrapper}"
        if duplicates:
            detail += ", duplicates=" + ", ".join(duplicates)
        results.append(CheckResult("sql-static", sql_ok, detail))

        tables = extract_table_columns(masked)
        fk_errors = foreign_key_target_errors(masked, tables)
        results.append(
            CheckResult(
                "sql-reference-targets",
                bool(tables and not fk_errors),
                f"tables={len(tables)}, foreign_key_target_errors={len(fk_errors)}"
                if not fk_errors
                else " | ".join(fk_errors[:5]),
            )
        )
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult("sql-static", False, str(exc)))
        results.append(CheckResult("sql-reference-targets", False, str(exc)))

    try:
        seed_sql = read_text(root / "database/seed.sql")
        apt2_safe = (
            "apt2me" in seed_sql.lower()
            and "LINK_OUT_ONLY" in seed_sql
            and re.search(r"apt2me.*?false.*?false.*?false", seed_sql, re.IGNORECASE | re.DOTALL) is not None
        )
        active_view_safe = "WHERE record_status = 'VALID'" in schema_sql
        force_rls_count = len(re.findall(r"(?im)^ALTER TABLE app\.[a-z_]+ FORCE ROW LEVEL SECURITY;", schema_sql))
        area_scope_integrity = all(
            token in schema_sql
            for token in (
                "area_type_complex_identity_uq",
                "transaction_area_type_complex_fk",
                "analysis_snapshot_area_type_complex_fk",
                "signal_area_type_complex_fk",
                "watchlist_item_area_type_complex_fk",
            )
        )
        typed_metric_null_contract = "num_nonnulls(value_numeric, value_text, value_boolean, value_date) = 1" in schema_sql
        invariants_ok = bool(
            apt2_safe
            and active_view_safe
            and force_rls_count == 5
            and area_scope_integrity
            and typed_metric_null_contract
        )
        results.append(
            CheckResult(
                "access-policy-invariants",
                invariants_ok,
                f"apt2_link_only={apt2_safe}, active_view_excludes_non_active={active_view_safe}, "
                f"force_rls_tables={force_rls_count}, area_scope_integrity={area_scope_integrity}, "
                f"typed_metric_null_contract={typed_metric_null_contract}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult("access-policy-invariants", False, str(exc)))

    placeholder_ok, placeholder_detail = check_no_unresolved_placeholders(root)
    results.append(CheckResult("placeholder-scan", placeholder_ok, placeholder_detail))

    return results


def write_manifest(root: Path, destination: Path) -> None:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.resolve() == destination.resolve():
            continue
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        files.append(
            {
                "path": rel,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest = {
        "package": "kr-apartment-market-skill",
        "manifestVersion": "1.0",
        "files": files,
    }
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write-manifest", action="store_true", help="write MANIFEST.json after successful validation")
    args = parser.parse_args()

    root = args.root.resolve()
    results = validate(root)
    width = max(len(result.name) for result in results)
    for result in results:
        marker = "PASS" if result.ok else "FAIL"
        print(f"[{marker}] {result.name:<{width}}  {result.detail}")

    failed = [result for result in results if not result.ok]
    if failed:
        print(f"\n{len(failed)} check(s) failed.", file=sys.stderr)
        return 1

    if args.write_manifest:
        destination = root / "MANIFEST.json"
        write_manifest(root, destination)
        print(f"\nManifest written: {destination}")

    print(f"\nAll {len(results)} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
