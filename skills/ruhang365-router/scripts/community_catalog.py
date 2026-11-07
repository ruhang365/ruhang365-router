#!/usr/bin/env python3
"""Load and match the versioned Ruhan365 Community catalog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalog" / "catalog.json"
GROUPS = {
    "scenario": "scenarios",
    "workflow": "workflows",
    "resource": "resources",
    "prompt": "prompts",
}
PROFILE_FIELDS = ("identity", "goal", "experience", "constraints", "deliverable")
SUPPORTED_SCHEMA_VERSIONS = {"1.0.0", "1.1.0"}
PROVIDER_ID_PATTERN = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?/[a-z0-9](?:[a-z0-9_.-]{0,98}[a-z0-9])?"
)
APPROVED_SPDX_IDENTIFIERS = {
    "AGPL-3.0-only",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC0-1.0",
    "CC-BY-4.0",
    "CC-BY-NC-4.0",
    "GPL-3.0-only",
    "MIT",
    "MPL-2.0",
}
PUBLIC_ITEM_FIELDS = (
    "id",
    "type",
    "slug",
    "version",
    "title",
    "summary",
    "status",
    "governance",
    "applicability",
    "completion_criteria",
    "tags",
    "match_terms",
    "schema_version",
)
APPLICABILITY_FIELDS = (
    "identities",
    "goals",
    "experience_levels",
    "constraints",
    "excluded_constraints",
    "deliverables",
)


def _canonical_digest(items: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        items,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _schema_version_key(value: Any, field: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or value not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(f"unsupported {field}")
    return tuple(int(part) for part in value.split("."))


def _require_string(item: dict[str, Any], field: str, *, minimum: int = 1) -> str:
    value = item.get(field)
    if not isinstance(value, str) or len(value.strip()) < minimum:
        raise ValueError(f"invalid Community catalog item {field}")
    return value


def _require_string_list(item: dict[str, Any], field: str, *, minimum: int = 0) -> list[str]:
    value = item.get(field)
    if not isinstance(value, list) or len(value) < minimum or any(
        not isinstance(entry, str) or not entry.strip() for entry in value
    ):
        raise ValueError(f"invalid Community catalog item {field}")
    return value


def _require_public_https_url(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid Community catalog item {field}")
    parsed = urllib.parse.urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise ValueError(f"invalid Community catalog item {field}")
    return value


def _validate_workflow_node(node: Any) -> None:
    if not isinstance(node, dict):
        raise ValueError("invalid Community catalog item workflow node")
    for field in ("id", "title", "action"):
        _require_string(node, field)
    for field in ("resource_ids", "prompt_ids"):
        _require_string_list(node, field)
    _require_string_list(node, "completion_criteria", minimum=1)


def _validate_public_item_structure(item: dict[str, Any]) -> None:
    for field in PUBLIC_ITEM_FIELDS:
        if field not in item:
            raise ValueError(f"invalid Community catalog item {field}")
    for field in ("id", "slug", "version", "title", "summary"):
        _require_string(item, field)
    if item["type"] not in GROUPS:
        raise ValueError("invalid Community catalog item type")
    if item["status"] not in {"current", "needs_review", "archived"}:
        raise ValueError("invalid Community catalog item status")
    governance = item["governance"]
    if not isinstance(governance, dict):
        raise ValueError("invalid Community catalog item governance")
    source = governance.get("source")
    rights = governance.get("rights")
    if not isinstance(source, dict):
        raise ValueError("invalid Community catalog item governance source")
    _require_public_https_url(source.get("url"), "governance source URL")
    if not isinstance(rights, dict) or rights.get("status") not in {"full", "reference_only"}:
        raise ValueError("invalid Community catalog item governance rights")
    if not isinstance(governance.get("stale"), bool):
        raise ValueError("invalid Community catalog item governance stale")
    applicability = item["applicability"]
    if not isinstance(applicability, dict):
        raise ValueError("invalid Community catalog item applicability")
    for field in APPLICABILITY_FIELDS:
        _require_string_list(applicability, field, minimum=1 if field in {"identities", "goals", "experience_levels", "deliverables"} else 0)
    _require_string_list(item, "completion_criteria", minimum=1)
    _require_string_list(item, "tags")
    _require_string_list(item, "match_terms")

    if item["type"] == "scenario":
        _require_string(item, "deliverable")
        _require_string(item, "next_intent")
        _require_string_list(item, "workflow_ids", minimum=1)
    elif item["type"] == "workflow":
        _require_string(item, "goal")
        estimated_minutes = item.get("estimated_minutes")
        if not isinstance(estimated_minutes, int) or isinstance(estimated_minutes, bool) or estimated_minutes <= 0:
            raise ValueError("invalid Community catalog item estimated_minutes")
        _require_string_list(item, "scenario_ids", minimum=1)
        nodes = item.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            raise ValueError("invalid Community catalog item nodes")
        for node in nodes:
            _validate_workflow_node(node)
    elif item["type"] == "resource":
        if item.get("resource_kind") not in {"skill", "tool", "knowledge", "template", "service"}:
            raise ValueError("invalid Community catalog item resource_kind")
        _require_string(item, "purpose")
        _require_string_list(item, "capabilities", minimum=1)
        _require_string(item, "resource_version")
        _require_public_https_url(item.get("source_url"), "source_url")
        repository_url = item.get("repository_url")
        if repository_url is not None:
            _require_public_https_url(repository_url, "repository_url")
    elif item["type"] == "prompt":
        _require_string(item, "purpose")
        _require_string(item, "template", minimum=8)
        _require_string_list(item, "variables")
        _require_string_list(item, "resource_ids")


def _validate_v1_1_skill_resource(item: dict[str, Any]) -> None:
    if item.get("schema_version") != "1.1.0" or item.get("type") != "resource" or item.get("resource_kind") != "skill":
        return
    provider = item.get("provider")
    if not isinstance(provider, dict):
        raise ValueError("invalid 1.1 resource provider")
    provider_id = provider.get("id")
    if not isinstance(provider_id, str) or not PROVIDER_ID_PATTERN.fullmatch(provider_id):
        raise ValueError("invalid 1.1 resource provider id")
    if not isinstance(provider.get("name"), str) or not provider["name"].strip():
        raise ValueError("invalid 1.1 resource provider name")
    provider_url = provider.get("url")
    parsed_provider_url = urllib.parse.urlparse(provider_url) if isinstance(provider_url, str) else None
    if (
        not parsed_provider_url
        or parsed_provider_url.scheme != "https"
        or not parsed_provider_url.netloc
        or parsed_provider_url.username
        or parsed_provider_url.password
    ):
        raise ValueError("invalid 1.1 resource provider URL")
    governance = item.get("governance")
    if not isinstance(governance, dict):
        raise ValueError("invalid 1.1 resource governance")
    rights = governance.get("rights")
    license_data = governance.get("license")
    if not isinstance(rights, dict) or rights.get("status") not in {"full", "reference_only"}:
        raise ValueError("invalid 1.1 resource rights")
    if not isinstance(license_data, dict):
        raise ValueError("invalid 1.1 resource license")
    upstream_license = item.get("upstream_license")
    if not isinstance(upstream_license, str) or upstream_license not in APPROVED_SPDX_IDENTIFIERS:
        raise ValueError("invalid 1.1 resource upstream license")
    if upstream_license != license_data.get("spdx"):
        raise ValueError("invalid 1.1 resource upstream license mismatch")
    commercial_use = item.get("commercial_use")
    integration_mode = item.get("integration_mode")
    if commercial_use not in {"allowed", "restricted", "unknown"}:
        raise ValueError("invalid 1.1 resource commercial use")
    if integration_mode not in {"reference_only", "invoke_if_installed", "embedded"}:
        raise ValueError("invalid 1.1 resource integration mode")
    if integration_mode == "reference_only" and rights["status"] != "reference_only":
        raise ValueError("invalid 1.1 resource reference rights")
    if integration_mode in {"invoke_if_installed", "embedded"} and (
        commercial_use != "allowed" or rights["status"] != "full"
    ):
        raise ValueError("invalid 1.1 resource invocation rights")


def validate_catalog(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Community catalog must be a JSON object")
    schema_version = payload.get("schemaVersion")
    top_level_schema_key = _schema_version_key(schema_version, "Community catalog schemaVersion")
    if not isinstance(payload.get("catalogVersion"), str):
        raise ValueError("Community catalogVersion is missing")
    items = payload.get("items")
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError("Community catalog items are invalid")
    digest = payload.get("contentDigest")
    if not isinstance(digest, str) or digest != _canonical_digest(items):
        raise ValueError("Community catalog contentDigest mismatch")
    for item in items:
        _validate_public_item_structure(item)
        item_schema_version = item.get("schema_version")
        item_schema_key = _schema_version_key(item_schema_version, "Community catalog item schema_version")
        if item_schema_key > top_level_schema_key:
            raise ValueError("Community catalog item schema_version exceeds catalog schemaVersion")
        if item_schema_version == "1.1.0":
            _validate_v1_1_skill_resource(item)
    return payload


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    catalog_path = Path(path) if path else DEFAULT_CATALOG_PATH
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Community catalog not found: {catalog_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Community catalog is invalid JSON: {catalog_path}") from error
    return validate_catalog(payload)


def resolve_catalog(
    base_url: str,
    *,
    snapshot_path: str | Path | None = None,
    timeout: float = 12.0,
    offline: bool = False,
    opener: Any = urllib.request.urlopen,
) -> dict[str, Any]:
    snapshot = load_catalog(snapshot_path)
    if offline:
        return {"catalog": snapshot, "source": "offline_snapshot", "warning": None}

    catalog_url = f"{base_url.rstrip('/')}/api/community/catalog"
    request = urllib.request.Request(
        catalog_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ruhang365-router/0.3 catalog-read-only",
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            online = validate_catalog(json.loads(response.read()))
        return {"catalog": online, "source": "online", "warning": None}
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
    ) as error:
        if isinstance(error, urllib.error.HTTPError):
            error.close()
        return {
            "catalog": snapshot,
            "source": "offline_fallback",
            "warning": f"Community Catalog API unavailable or invalid; using stable snapshot ({type(error).__name__}).",
        }


def _normalize_text(value: Any) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def _tokens(value: Any) -> set[str]:
    text = _normalize_text(value)
    if not text:
        return set()
    tokens = set(re.findall(r"[a-z0-9][a-z0-9.+-]*|[\u4e00-\u9fff]+", text))
    for sequence in re.findall(r"[\u4e00-\u9fff]+", text):
        for size in (2, 3):
            tokens.update(
                sequence[index : index + size]
                for index in range(len(sequence) - size + 1)
            )
    return {token for token in tokens if len(token) > 1}


def _matches_value(profile_value: str, candidates: list[str]) -> bool:
    normalized = _normalize_text(profile_value)
    if not normalized:
        return False
    normalized_candidates = {_normalize_text(item) for item in candidates}
    if normalized in normalized_candidates:
        return True
    profile_tokens = _tokens(normalized)
    candidate_tokens = set().union(*(_tokens(item) for item in candidates)) if candidates else set()
    return bool(profile_tokens & candidate_tokens)


def _profile(profile: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile, dict):
        raise ValueError("matching profile must be an object")
    normalized = {
        "identity": _normalize_text(profile.get("identity")),
        "goal": _normalize_text(profile.get("goal")),
        "experience": _normalize_text(profile.get("experience")),
        "deliverable": _normalize_text(profile.get("deliverable")),
    }
    constraints = profile.get("constraints", [])
    if not isinstance(constraints, list) or any(not isinstance(item, str) for item in constraints):
        raise ValueError("matching profile constraints must be a string array")
    normalized["constraints"] = sorted(
        {_normalize_text(item) for item in constraints if _normalize_text(item)}
    )
    return normalized


def _score_item(item: dict[str, Any], profile: dict[str, Any]) -> tuple[int, list[str]] | None:
    governance = item.get("governance")
    if (
        item.get("status") != "current"
        or not isinstance(governance, dict)
        or governance.get("stale") is not False
    ):
        return None
    applicability = item.get("applicability")
    if not isinstance(applicability, dict):
        return None
    excluded = {_normalize_text(value) for value in applicability.get("excluded_constraints", [])}
    if excluded & set(profile["constraints"]):
        return None

    score = 0
    reasons: list[str] = []
    dimensions = (
        ("identity", "identities", 40),
        ("goal", "goals", 30),
        ("experience", "experience_levels", 15),
        ("deliverable", "deliverables", 35),
    )
    for profile_field, asset_field, weight in dimensions:
        candidates = applicability.get(asset_field, [])
        if isinstance(candidates, list) and _matches_value(profile[profile_field], candidates):
            score += weight
            reasons.append(profile_field)

    supported_constraints = {
        _normalize_text(value) for value in applicability.get("constraints", [])
    }
    constraint_matches = supported_constraints & set(profile["constraints"])
    if constraint_matches:
        score += min(20, len(constraint_matches) * 10)
        reasons.append("constraints")

    profile_terms = _tokens(" ".join(str(profile[field]) for field in PROFILE_FIELDS))
    searchable = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("summary", "")),
            " ".join(item.get("tags", [])),
            " ".join(item.get("match_terms", [])),
        ]
    )
    term_matches = profile_terms & _tokens(searchable)
    if term_matches:
        score += min(20, len(term_matches) * 2)
        reasons.append("terms")

    if score == 0:
        return None
    recommendation_weight = item.get("recommendation_weight", 0)
    if isinstance(recommendation_weight, int) and not isinstance(recommendation_weight, bool):
        score += max(0, min(20, recommendation_weight))
    return score, reasons


def _project_match(item: dict[str, Any], score: int, reasons: list[str]) -> dict[str, Any]:
    governance = item.get("governance", {})
    source = governance.get("source", {}) if isinstance(governance, dict) else {}
    rights = governance.get("rights", {}) if isinstance(governance, dict) else {}
    projected: dict[str, Any] = {
        "id": item["id"],
        "type": item["type"],
        "slug": item["slug"],
        "version": item["version"],
        "title": item["title"],
        "summary": item["summary"],
        "status": item["status"],
        "score": score,
        "matchReasons": reasons,
        "completionCriteria": item["completion_criteria"],
        "sourceUrl": source.get("url"),
        "rightsStatus": rights.get("status"),
        "applicableIdentities": item["applicability"]["identities"],
    }
    if item["type"] == "scenario":
        projected.update(
            {
                "deliverable": item["deliverable"],
                "nextIntent": item["next_intent"],
                "workflowIds": item["workflow_ids"],
                "recommendationWeight": item.get("recommendation_weight", 0),
            }
        )
    elif item["type"] == "workflow":
        projected.update(
            {
                "goal": item["goal"],
                "estimatedMinutes": item["estimated_minutes"],
                "scenarioIds": item["scenario_ids"],
            }
        )
    elif item["type"] == "resource":
        integration_mode = item.get("integration_mode")
        if not isinstance(integration_mode, str):
            integration_mode = "reference_only" if rights.get("status") == "reference_only" else "invoke_if_installed"
        projected.update(
            {
                "resourceKind": item["resource_kind"],
                "purpose": item["purpose"],
                "capabilities": item["capabilities"],
                "repositoryUrl": item.get("repository_url"),
                "resourceVersion": item["resource_version"],
                "resourceSchemaVersion": item.get("schema_version", "1.0.0"),
                "provider": item.get("provider"),
                "upstreamLicense": item.get("upstream_license"),
                "commercialUse": item.get("commercial_use", "unknown"),
                "integrationMode": integration_mode,
            }
        )
    elif item["type"] == "prompt":
        projected.update(
            {
                "purpose": item["purpose"],
                "template": item["template"],
                "variables": item["variables"],
                "resourceIds": item["resource_ids"],
            }
        )
    return projected


def match_catalog(
    catalog: dict[str, Any],
    profile: dict[str, Any],
    *,
    limit_per_type: int = 3,
) -> dict[str, Any]:
    if not 1 <= limit_per_type <= 10:
        raise ValueError("limit_per_type must be between 1 and 10")
    normalized_profile = _profile(profile)
    groups: dict[str, list[dict[str, Any]]] = {group: [] for group in GROUPS.values()}
    items = catalog.get("items", [])
    if not isinstance(items, list):
        raise ValueError("Community catalog items are invalid")
    for item in items:
        if not isinstance(item, dict) or item.get("type") not in GROUPS:
            continue
        scored = _score_item(item, normalized_profile)
        if scored is None:
            continue
        score, reasons = scored
        groups[GROUPS[item["type"]]].append(_project_match(item, score, reasons))
    for matches in groups.values():
        matches.sort(key=lambda match: (-match["score"], match["id"], match["version"]))
        del matches[limit_per_type:]
    return {
        "catalogVersion": catalog.get("catalogVersion"),
        "contentDigest": catalog.get("contentDigest"),
        "profile": normalized_profile,
        **groups,
    }
