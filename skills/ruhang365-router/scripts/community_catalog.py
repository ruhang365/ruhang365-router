#!/usr/bin/env python3
"""Load and match the versioned Ruhan365 Community catalog."""

from __future__ import annotations

import hashlib
import gzip
import io
import json
from pathlib import Path
import re
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from guidance import validate_guidance, current_item


DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalog" / "catalog.json"
FULL_CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalog" / "community-full-1.1.0.json"
GROUPS = {
    "scenario": "scenarios",
    "workflow": "workflows",
    "resource": "resources",
    "prompt": "prompts",
}
PROFILE_FIELDS = ("identity", "goal", "experience", "constraints", "deliverable")
MAX_CATALOG_BYTES = 32 * 1024 * 1024


def _read_catalog_response(response: Any) -> Any:
    raw = response.read(MAX_CATALOG_BYTES + 1)
    if len(raw) > MAX_CATALOG_BYTES:
        raise ValueError("Community catalog response is too large")
    headers = getattr(response, "headers", {})
    if headers.get("Content-Encoding", "").lower() == "gzip":
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            raw = stream.read(MAX_CATALOG_BYTES + 1)
        if len(raw) > MAX_CATALOG_BYTES:
            raise ValueError("Community catalog decompressed response is too large")
    return json.loads(raw)


def _canonical_digest(items: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        items,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_catalog(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Community catalog must be a JSON object")
    if payload.get("schemaVersion") not in {"1.0.0", "1.1.0"}:
        raise ValueError("unsupported Community catalog schemaVersion")
    if not isinstance(payload.get("catalogVersion"), str):
        raise ValueError("Community catalogVersion is missing")
    items = payload.get("items")
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError("Community catalog items are invalid")
    digest = payload.get("contentDigest")
    if not isinstance(digest, str) or digest != _canonical_digest(items):
        raise ValueError("Community catalog contentDigest mismatch")
    for item in items:
        if "guidance" in item:
            if payload["schemaVersion"] != "1.1.0":
                raise ValueError("guidance requires Community schemaVersion 1.1.0")
            validate_guidance(item["guidance"])
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
            "Accept-Encoding": "gzip",
            "User-Agent": "ruhang365-router/0.3 catalog-read-only",
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            online = validate_catalog(_read_catalog_response(response))
        return {"catalog": online, "source": "online", "warning": None}
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        EOFError,
        ValueError,
    ) as error:
        if isinstance(error, urllib.error.HTTPError):
            error.close()
        return {
            "catalog": snapshot,
            "source": "offline_fallback",
            "warning": f"Community Catalog API unavailable or invalid; using stable snapshot ({type(error).__name__}).",
        }


def fetch_asset_detail(base_url: str, item: dict[str, Any], *, timeout: float = 12.0, opener: Any = urllib.request.urlopen) -> dict[str, Any]:
    """Read one public detail by stable id; no query, profile, or credentials are sent."""
    detail_ref = item.get("detail_ref")
    if not isinstance(detail_ref, str) or not detail_ref.startswith("/"):
        raise ValueError("catalog item has no safe public detail_ref")
    url = urllib.parse.urljoin(f"{base_url.rstrip('/')}/", detail_ref.lstrip('/'))
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "ruhang365-router/0.4 detail-read-only"})
    with opener(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    if (
        not isinstance(payload, dict)
        or payload.get("id") != item.get("id")
        or payload.get("version") != item.get("version")
        or (payload.get("contentHash") is not None and payload.get("contentHash") != item.get("content_hash"))
    ):
        raise ValueError("community detail identity/version mismatch")
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
    experience = _normalize_text(profile.get("experience", profile.get("level")))
    normalized = {
        "identity": _normalize_text(profile.get("identity")),
        "goal": _normalize_text(profile.get("goal")),
        "experience": experience,
        "level": _normalize_text(profile.get("level", experience)),
        "deliverable": _normalize_text(profile.get("deliverable")),
        "query": _normalize_text(profile.get("query")),
    }
    constraints = profile.get("constraints", [])
    if not isinstance(constraints, list) or any(not isinstance(item, str) for item in constraints):
        raise ValueError("matching profile constraints must be a string array")
    normalized["constraints"] = sorted(
        {_normalize_text(item) for item in constraints if _normalize_text(item)}
    )
    return normalized


def _score_item(item: dict[str, Any], profile: dict[str, Any]) -> tuple[int, list[str]] | None:
    if not current_item(item):
        return None
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
        ("level", "experience_levels", 15),
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

    # Experience and constraints refine relevance; they cannot establish it.
    profile_terms = _tokens(" ".join(profile[field] for field in ("identity", "goal", "deliverable", "query")))
    searchable = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("summary", "")),
            " ".join(item.get("tags", [])),
            " ".join(item.get("tags", [])),
            " ".join(item.get("match_terms", [])),
        ]
    )
    term_matches = profile_terms & _tokens(searchable)
    if term_matches:
        score += min(20, len(term_matches) * 2)
        reasons.append("terms")

    if not set(reasons) & {"identity", "goal", "deliverable", "terms"}:
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
        "access": item.get("access", "public"),
        "sourceKind": item.get("source_kind"),
        "sourceId": item.get("source_id"),
        "contentKind": item.get("content_kind"),
        "detailRef": item.get("detail_ref"),
        "contentHash": item.get("content_hash"),
    }
    if "guidance" in item:
        projected["guidance"] = item["guidance"]
    if item["type"] == "scenario":
        projected.update(
            {
                "deliverable": item.get("deliverable"),
                "nextIntent": item.get("next_intent"),
                "workflowIds": item.get("workflow_ids", []),
                "recommendationWeight": item.get("recommendation_weight", 0),
            }
        )
    elif item["type"] == "workflow":
        projected.update(
            {
                "goal": item.get("goal", item.get("summary", "")),
                "estimatedMinutes": item.get("estimated_minutes"),
                "scenarioIds": item.get("scenario_ids", []),
            }
        )
    elif item["type"] == "resource":
        projected.update(
            {
                "resourceKind": item.get("resource_kind", item.get("content_kind", "resource")),
                "purpose": item.get("purpose", item.get("summary", "")),
                "capabilities": item.get("capabilities", []),
                "repositoryUrl": item.get("repository_url"),
                "resourceVersion": item.get("resource_version", item.get("version")),
            }
        )
    elif item["type"] == "prompt":
        projected.update(
            {
                "purpose": item.get("purpose", item.get("summary", "")),
                "template": item.get("template"),
                "variables": item.get("variables", {}),
                "resourceIds": item.get("resource_ids", []),
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
