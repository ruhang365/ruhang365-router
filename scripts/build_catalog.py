#!/usr/bin/env python3
"""Validate reviewed Community content and build a deterministic catalog."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTENT_ROOT = REPO_ROOT / "content"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "community-item.schema.json"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "skills"
    / "ruhang365-router"
    / "catalog"
    / "catalog.json"
)
SCHEMA_VERSION = "1.0.0"
SOURCE_REPOSITORY = "https://github.com/ruhang365/ruhang365-router"
TYPE_DIRECTORIES = {
    "scenarios": "scenario",
    "workflows": "workflow",
    "resources": "resource",
    "prompts": "prompt",
}
TYPE_ORDER = {asset_type: index for index, asset_type in enumerate(TYPE_DIRECTORIES.values())}
STRING_LIST_FIELDS = (
    "identities",
    "goals",
    "experience_levels",
    "constraints",
    "excluded_constraints",
    "deliverables",
)
INTERNAL_OR_SECRET_PATTERNS = (
    ("internal path", re.compile(r"(?:file://|/Users/|/home/|[A-Za-z]:\\\\Users\\\\|localhost|127\\.0\\.0\\.1)", re.I)),
    ("secret material", re.compile(r"(?:BEGIN (?:RSA |OPENSSH )?PRIVATE KEY|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{16,})")),
)
FORBIDDEN_PRIVATE_FIELDS = {
    "api_key",
    "asset_id",
    "authorization",
    "cookie",
    "email",
    "feedback_id",
    "member_id",
    "owner_user_id",
    "password",
    "profile_id",
    "result_id",
    "run_id",
    "session_id",
    "token",
    "user_id",
}


class CatalogValidationError(ValueError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-root", type=Path, default=DEFAULT_CONTENT_ROOT)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--catalog-version", default="1.0.0")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CatalogValidationError(f"missing file: {path}") from error
    except json.JSONDecodeError as error:
        raise CatalogValidationError(
            f"invalid JSON in {path}: line {error.lineno}, column {error.colno}"
        ) from error
    if not isinstance(payload, dict):
        raise CatalogValidationError(f"schema object required in {path}")
    return payload


def require_string(value: Any, field: str, *, minimum: int = 1) -> str:
    if not isinstance(value, str) or len(value.strip()) < minimum:
        raise CatalogValidationError(f"invalid {field}: non-empty string required")
    return value.strip()


def require_string_list(value: Any, field: str, *, minimum: int = 0) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum:
        raise CatalogValidationError(f"invalid {field}: string array required")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise CatalogValidationError(f"invalid {field}: every item must be a string")
    if len(value) != len(set(value)):
        raise CatalogValidationError(f"duplicate value in {field}")
    return value


def validate_url(value: Any, field: str) -> str:
    url = require_string(value, field)
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise CatalogValidationError(f"invalid {field}: public https URL required")
    return url


def validate_date(value: Any, field: str) -> date:
    text = require_string(value, field)
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise CatalogValidationError(f"invalid {field}: YYYY-MM-DD required") from error


def validate_schema_fields(asset: dict[str, Any], schema: dict[str, Any], path: Path) -> None:
    required = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required, list) or not isinstance(properties, dict):
        raise CatalogValidationError("invalid schema contract: required/properties missing")
    for field in required:
        if field not in asset:
            raise CatalogValidationError(f"missing required field {field} in {path}")
    type_map = {"string": str, "array": list, "object": dict, "integer": int, "boolean": bool}
    for field, rules in properties.items():
        if field not in asset or not isinstance(rules, dict):
            continue
        value = asset[field]
        expected_type = rules.get("type")
        if expected_type in type_map and not isinstance(value, type_map[expected_type]):
            raise CatalogValidationError(f"invalid {field} type in {path}")
        if "const" in rules and value != rules["const"]:
            raise CatalogValidationError(f"invalid {field} in {path}: expected {rules['const']}")
        if "enum" in rules and value not in rules["enum"]:
            raise CatalogValidationError(f"invalid {field} in {path}: unsupported value")
        if isinstance(value, str) and "minLength" in rules and len(value.strip()) < rules["minLength"]:
            raise CatalogValidationError(f"invalid {field} in {path}: too short")
        if isinstance(value, str) and "pattern" in rules and not re.fullmatch(rules["pattern"], value):
            raise CatalogValidationError(f"invalid {field} in {path}: pattern mismatch")
        if isinstance(value, list) and "minItems" in rules and len(value) < rules["minItems"]:
            raise CatalogValidationError(f"invalid {field} in {path}: too few items")


def validate_governance(asset: dict[str, Any], path: Path) -> None:
    governance = asset.get("governance")
    if not isinstance(governance, dict):
        raise CatalogValidationError(f"missing governance object in {path}")
    for field in ("source", "license", "rights", "maintainers", "review", "updated_at", "stale_after", "stale"):
        if field not in governance:
            raise CatalogValidationError(f"missing governance {field} in {path}")

    source = governance["source"]
    if not isinstance(source, dict):
        raise CatalogValidationError(f"invalid governance source in {path}")
    if source.get("kind") not in {"owned", "permitted", "open_license", "reference_only"}:
        raise CatalogValidationError(f"invalid governance source kind in {path}")
    validate_url(source.get("url"), "governance source URL")

    license_data = governance["license"]
    if not isinstance(license_data, dict):
        raise CatalogValidationError(f"missing governance license in {path}")
    require_string(license_data.get("spdx"), "governance license SPDX")
    require_string(license_data.get("attribution"), "governance license attribution")
    rights = governance["rights"]
    if not isinstance(rights, dict) or rights.get("status") not in {"full", "reference_only"}:
        raise CatalogValidationError(f"invalid governance rights in {path}")
    require_string_list(governance["maintainers"], "governance maintainers", minimum=1)

    review = governance["review"]
    if not isinstance(review, dict) or review.get("status") != "approved":
        raise CatalogValidationError(f"invalid review status in {path}: approved required")
    reviewed_at = validate_date(review.get("reviewed_at"), "reviewed_at")
    updated_at = validate_date(governance["updated_at"], "updated_at")
    stale_after = validate_date(governance["stale_after"], "stale_after")
    if reviewed_at < updated_at:
        raise CatalogValidationError(f"invalid reviewed_at in {path}: precedes updated_at")
    if stale_after < updated_at:
        raise CatalogValidationError(f"invalid stale_after in {path}: precedes updated_at")
    if not isinstance(governance["stale"], bool):
        raise CatalogValidationError(f"invalid stale flag in {path}")


def validate_applicability(asset: dict[str, Any], path: Path) -> None:
    applicability = asset.get("applicability")
    if not isinstance(applicability, dict):
        raise CatalogValidationError(f"missing applicability object in {path}")
    for field in STRING_LIST_FIELDS:
        if field not in applicability:
            raise CatalogValidationError(f"missing applicability {field} in {path}")
        minimum = 1 if field in {"identities", "goals", "experience_levels", "deliverables"} else 0
        require_string_list(applicability[field], f"applicability {field}", minimum=minimum)


def validate_node(node: Any, path: Path) -> None:
    if not isinstance(node, dict):
        raise CatalogValidationError(f"invalid workflow node in {path}")
    for field in ("id", "title", "action"):
        require_string(node.get(field), f"workflow node {field}")
    for field in ("resource_ids", "prompt_ids"):
        require_string_list(node.get(field), f"workflow node {field}")
    require_string_list(node.get("completion_criteria"), "workflow node completion_criteria", minimum=1)


def validate_type_fields(asset: dict[str, Any], path: Path) -> None:
    asset_type = asset["type"]
    expected_id = f"r365.{asset_type}.{asset['slug']}"
    if asset["id"] != expected_id:
        raise CatalogValidationError(f"invalid id in {path}: expected {expected_id}")

    if asset_type == "scenario":
        require_string(asset.get("deliverable"), "scenario deliverable")
        require_string(asset.get("next_intent"), "scenario next_intent")
        require_string_list(asset.get("workflow_ids"), "scenario workflow_ids", minimum=1)
        recommendation_weight = asset.get("recommendation_weight", 0)
        if (
            not isinstance(recommendation_weight, int)
            or isinstance(recommendation_weight, bool)
            or not 0 <= recommendation_weight <= 20
        ):
            raise CatalogValidationError(f"invalid scenario recommendation_weight in {path}")
    elif asset_type == "workflow":
        require_string(asset.get("goal"), "workflow goal")
        minutes = asset.get("estimated_minutes")
        if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes <= 0:
            raise CatalogValidationError(f"invalid workflow estimated_minutes in {path}")
        require_string_list(asset.get("scenario_ids"), "workflow scenario_ids", minimum=1)
        nodes = asset.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            raise CatalogValidationError(f"invalid workflow nodes in {path}")
        for node in nodes:
            validate_node(node, path)
        node_ids = [node["id"] for node in nodes]
        if len(node_ids) != len(set(node_ids)):
            raise CatalogValidationError(f"duplicate workflow node id in {path}")
    elif asset_type == "resource":
        if asset.get("resource_kind") not in {"skill", "tool", "knowledge", "template", "service"}:
            raise CatalogValidationError(f"invalid resource_kind in {path}")
        require_string(asset.get("purpose"), "resource purpose")
        require_string_list(asset.get("capabilities"), "resource capabilities", minimum=1)
        validate_url(asset.get("source_url"), "resource source_url")
        repository_url = asset.get("repository_url")
        if repository_url is not None:
            validate_url(repository_url, "resource repository_url")
        require_string(asset.get("resource_version"), "resource resource_version")
    elif asset_type == "prompt":
        require_string(asset.get("purpose"), "prompt purpose")
        template = require_string(asset.get("template"), "prompt template", minimum=8)
        variables = require_string_list(asset.get("variables"), "prompt variables")
        for variable in variables:
            if f"{{{{{variable}}}}}" not in template:
                raise CatalogValidationError(f"missing prompt variable placeholder {variable} in {path}")
        require_string_list(asset.get("resource_ids"), "prompt resource_ids")


def validate_no_internal_or_secret_data(asset: dict[str, Any], path: Path) -> None:
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested_value in value.items():
                if key.casefold() in FORBIDDEN_PRIVATE_FIELDS:
                    raise CatalogValidationError(f"sensitive field {key} detected in {path}")
                visit(nested_value)
        elif isinstance(value, list):
            for nested_value in value:
                visit(nested_value)

    visit(asset)
    serialized = json.dumps(asset, ensure_ascii=False)
    for label, pattern in INTERNAL_OR_SECRET_PATTERNS:
        if pattern.search(serialized):
            raise CatalogValidationError(f"{label} detected in {path}")


def discover_assets(content_root: Path, schema: dict[str, Any]) -> list[dict[str, Any]]:
    if not content_root.is_dir():
        raise CatalogValidationError(f"missing content root: {content_root}")
    assets: list[dict[str, Any]] = []
    for directory_name, expected_type in TYPE_DIRECTORIES.items():
        directory = content_root / directory_name
        if not directory.is_dir():
            raise CatalogValidationError(f"missing content directory: {directory}")
        for path in sorted(directory.glob("*.json")):
            asset = load_json(path)
            validate_schema_fields(asset, schema, path)
            if asset.get("type") != expected_type:
                raise CatalogValidationError(f"invalid type for directory {directory_name}: {path}")
            if asset.get("slug") != path.stem:
                raise CatalogValidationError(f"invalid slug for filename {path.name}")
            validate_no_internal_or_secret_data(asset, path)
            validate_governance(asset, path)
            validate_applicability(asset, path)
            require_string_list(asset.get("completion_criteria"), "completion_criteria", minimum=1)
            require_string_list(asset.get("tags"), "tags")
            require_string_list(asset.get("match_terms"), "match_terms")
            validate_type_fields(asset, path)
            catalog_item = dict(asset)
            catalog_item["contentPath"] = path.relative_to(content_root.parent).as_posix()
            assets.append(catalog_item)
    if not assets:
        raise CatalogValidationError("no Community content found")
    return assets


def validate_references(assets: list[dict[str, Any]]) -> None:
    by_id: dict[str, dict[str, Any]] = {}
    for asset in assets:
        asset_id = asset["id"]
        if asset_id in by_id:
            raise CatalogValidationError(f"duplicate asset id: {asset_id}")
        by_id[asset_id] = asset

    references: list[tuple[str, str, str]] = []
    for asset in assets:
        if asset["type"] == "scenario":
            references.extend((asset["id"], target, "workflow") for target in asset["workflow_ids"])
        elif asset["type"] == "workflow":
            references.extend((asset["id"], target, "scenario") for target in asset["scenario_ids"])
            for node in asset["nodes"]:
                references.extend((asset["id"], target, "resource") for target in node["resource_ids"])
                references.extend((asset["id"], target, "prompt") for target in node["prompt_ids"])
        elif asset["type"] == "prompt":
            references.extend((asset["id"], target, "resource") for target in asset["resource_ids"])

    for source_id, target_id, expected_type in references:
        target = by_id.get(target_id)
        if target is None:
            raise CatalogValidationError(f"dangling reference from {source_id} to {target_id}")
        if target["type"] != expected_type:
            raise CatalogValidationError(
                f"invalid reference type from {source_id} to {target_id}: expected {expected_type}"
            )


def build_catalog(
    content_root: Path,
    schema_path: Path,
    catalog_version: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", catalog_version):
        raise CatalogValidationError("invalid catalog version: semantic version required")
    schema = load_json(schema_path)
    assets = discover_assets(content_root, schema)
    validate_references(assets)
    assets.sort(key=lambda item: (TYPE_ORDER[item["type"]], item["id"], item["version"]))
    canonical_items = json.dumps(
        assets,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "catalogVersion": catalog_version,
        "contentDigest": hashlib.sha256(canonical_items).hexdigest(),
        "sourceRepository": SOURCE_REPOSITORY,
        "items": assets,
    }


def serialize_catalog(catalog: dict[str, Any]) -> str:
    return json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    args = parse_args()
    try:
        catalog = build_catalog(args.content_root, args.schema, args.catalog_version)
        serialized = serialize_catalog(catalog)
        if args.check:
            if not args.output.is_file():
                raise CatalogValidationError(f"catalog output missing: {args.output}")
            if args.output.read_text(encoding="utf-8") != serialized:
                raise CatalogValidationError(
                    "catalog output is stale; run scripts/build_catalog.py --write"
                )
        elif args.write:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized, encoding="utf-8")
        else:
            sys.stdout.write(serialized)
    except CatalogValidationError as error:
        print(f"catalog validation failed: {error}", file=sys.stderr)
        return 1
    print(
        f"catalog valid: {len(catalog['items'])} items, digest {catalog['contentDigest']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
