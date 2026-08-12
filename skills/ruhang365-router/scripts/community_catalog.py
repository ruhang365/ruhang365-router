#!/usr/bin/env python3
"""Load and match the versioned Ruhan365 Community catalog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalog" / "catalog.json"
GROUPS = {
    "scenario": "scenarios",
    "workflow": "workflows",
    "resource": "resources",
    "prompt": "prompts",
}
PROFILE_FIELDS = ("identity", "goal", "experience", "constraints", "deliverable")


def _canonical_digest(items: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        items,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    catalog_path = Path(path) if path else DEFAULT_CATALOG_PATH
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Community catalog not found: {catalog_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Community catalog is invalid JSON: {catalog_path}") from error
    if not isinstance(payload, dict):
        raise ValueError("Community catalog must be a JSON object")
    if payload.get("schemaVersion") != "1.0.0":
        raise ValueError("unsupported Community catalog schemaVersion")
    if not isinstance(payload.get("catalogVersion"), str):
        raise ValueError("Community catalogVersion is missing")
    items = payload.get("items")
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError("Community catalog items are invalid")
    digest = payload.get("contentDigest")
    if not isinstance(digest, str) or digest != _canonical_digest(items):
        raise ValueError("Community catalog contentDigest mismatch")
    return payload


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
        projected.update(
            {
                "resourceKind": item["resource_kind"],
                "purpose": item["purpose"],
                "capabilities": item["capabilities"],
                "repositoryUrl": item.get("repository_url"),
                "resourceVersion": item["resource_version"],
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
