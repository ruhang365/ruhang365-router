#!/usr/bin/env python3
"""Load and match the versioned Ruhan365 Community catalog."""

from __future__ import annotations

import hashlib
import gzip
import io
import json
import math
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
MATCH_STOP_TERMS = {"一个", "怎么", "什么", "比较", "了解", "现有", "已有", "当前", "这里",
                    "帮助", "需要", "可以", "以及", "相关", "我们"}
# Question wording carries no topic. Removing it (instead of only dropping the
# whole word) also stops boundary n-grams such as "是什" from matching.
QUESTION_PHRASES = ("什么是", "是什么", "为什么", "怎么样", "怎么办", "怎么", "如何", "请问", "帮我", "我想", "想要",
                    "推荐几个", "推荐一些", "推荐一下", "有没有", "有什么", "能直接用", "直接用", "适合吗",
                    "从哪里开始", "从哪开始", "一下")
# Free-text relevance: share of the query's informative weight an item covers.
# Long natural-language questions cover less, so the bar is relative to the
# best match of the same type, with an absolute floor.
MIN_QUERY_COVERAGE = 0.15
RELATIVE_QUERY_COVERAGE = 0.4
QUERY_TERM_WEIGHT = 60
BODY_TERM_FACTOR = 0.7
# Without word segmentation, n-grams spanning a function character ("几个",
# "我是", "的提示") look rare and would outweigh real topics, so query grams
# may not start or end with one. Characters that open or close common topic
# words (就业, 成就, 思想, 供给, 转让, 首都, 酒吧, 再就业) are left out.
QUERY_NO_START = set("的了吗呢吧啊么们是我你他她它想哪几从把被让给很都也还又做")
QUERY_NO_END = set("的了吗呢啊么们是我你他她它哪几从把被很也还又再做个")
QUERY_INNER_PARTICLES = set("的了")
# In a large catalog, a Chinese n-gram seen in only one entry is more often a
# cross-word fragment than a topic word. Small catalogs and candidate subsets
# are exempt, since a real word may appear only once there.
MIN_GRAM_FREQUENCY = 2
GRAM_FREQUENCY_MIN_CATALOG = 500
# (weight, {term: weight}, source word or Chinese run, character index or -1)
QueryPosition = tuple[float, dict[str, float], str, int]


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


def fetch_catalog(url: str, *, snapshot: dict[str, Any] | None = None,
                  timeout: float = 12.0, opener: Any = urllib.request.urlopen,
                  user_agent: str = "ruhang365-router/0.3 catalog-read-only") -> tuple[dict[str, Any], bool]:
    """Public conditional GET. A 304 is usable only with a validated snapshot."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ValueError("unsafe public catalog URL")
    headers = {"Accept": "application/json", "Accept-Encoding": "gzip", "User-Agent": user_agent}
    if snapshot is not None:
        validate_catalog(snapshot)
        tag = hashlib.sha256(f"{snapshot['catalogVersion']}:{snapshot['contentDigest']}".encode("utf-8")).hexdigest()
        headers["If-None-Match"] = f'"{tag}"'

    def confirmed_snapshot(response_headers: Any) -> tuple[dict[str, Any], bool]:
        if snapshot is None:
            raise ValueError("304 without validated snapshot")
        etag = (response_headers or {}).get("ETag")
        if etag is not None:
            # If-None-Match uses weak comparison, but a different release is
            # never evidence that this snapshot has been confirmed online.
            etag = etag.strip()
            if etag.startswith("W/"):
                etag = etag[2:]
            if etag != headers["If-None-Match"]:
                raise ValueError("304 catalog ETag mismatch")
        return snapshot, True

    request = urllib.request.Request(url, headers=headers)
    try:
        with opener(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status == 304:
                return confirmed_snapshot(getattr(response, "headers", {}))
            if status != 200:
                raise ValueError("unexpected catalog response status")
            return validate_catalog(_read_catalog_response(response)), False
    except urllib.error.HTTPError as error:
        error.close()
        if error.code == 304:
            return confirmed_snapshot(error.headers)
        raise


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
    try:
        online, _ = fetch_catalog(catalog_url, snapshot=snapshot, timeout=timeout, opener=opener)
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


def _strip_question_phrases(text: str) -> str:
    for phrase in QUESTION_PHRASES:
        text = text.replace(phrase, " ")
    return text


def _tokens(value: Any) -> set[str]:
    text = _strip_question_phrases(_normalize_text(value))
    if not text.strip():
        return set()
    tokens = set(re.findall(r"[a-z0-9][a-z0-9.+-]*|[\u4e00-\u9fff]+", text))
    for sequence in re.findall(r"[\u4e00-\u9fff]+", text):
        for size in (2, 3):
            tokens.update(
                sequence[index : index + size]
                for index in range(len(sequence) - size + 1)
            )
    return {token for token in tokens if len(token) > 1 and token not in MATCH_STOP_TERMS}


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


def _score_item(item: dict[str, Any], profile: dict[str, Any],
                coverage_match: tuple[float, list[str], float], min_coverage: float) -> tuple[int, list[str], list[str]] | None:
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
    coverage, matched_terms, precision = coverage_match
    if coverage and coverage >= min_coverage:
        # A title mostly made of the query is a closer match than a passing mention.
        score += round(QUERY_TERM_WEIGHT * coverage + 10 * precision)
        reasons.append("terms")
    else:
        matched_terms = []

    if not set(reasons) & {"identity", "goal", "deliverable", "terms"}:
        return None
    recommendation_weight = item.get("recommendation_weight", 0)
    if isinstance(recommendation_weight, int) and not isinstance(recommendation_weight, bool):
        weight = max(0, min(20, recommendation_weight))
        # Editorial weight orders relevant items; it cannot lift a weak text match.
        if not set(reasons) & {"identity", "goal", "deliverable"}:
            weight = round(weight * coverage)
        score += weight
    return score, reasons, matched_terms


def _index_entry(item: dict[str, Any]) -> tuple[set[str], set[str]]:
    title = _tokens(item.get("title", ""))
    body = _tokens(" ".join([
        str(item.get("summary", "")),
        " ".join(item.get("tags", [])),
        " ".join(item.get("match_terms", [])),
    ]))
    return title, title | body


def _query_model(text: str, document_frequency: dict[str, int], total: int) -> list[QueryPosition]:
    """Weighted query positions: each ASCII word or Chinese character is one position.

    A Chinese character is covered by any indexed 2/3-gram (or the whole run)
    containing it, so overlapping n-grams are not counted twice; a word's weight
    is spread over its characters, so a Chinese word counts as much as an ASCII word. Rare terms weigh
    more than common ones; positions absent from the catalog are ignored.
    """
    def idf(term: str) -> float | None:
        frequency = document_frequency.get(term, 0)
        return math.log(1 + total / frequency) if frequency else None

    min_frequency = MIN_GRAM_FREQUENCY if total >= GRAM_FREQUENCY_MIN_CATALOG else 1
    positions: list[QueryPosition] = []
    stripped = _strip_question_phrases(_normalize_text(text))
    for match in re.finditer(r"[a-z0-9][a-z0-9.+-]*|[\u4e00-\u9fff]+", stripped):
        token = match.group()
        if not "\u4e00" <= token[0] <= "\u9fff":
            weight = idf(token) if len(token) > 1 and token not in MATCH_STOP_TERMS else None
            if weight:
                positions.append((weight, {token: weight}, token, -1))
            continue
        grams: list[tuple[int, int, str]] = [(0, len(token), token)] if len(token) > 1 else []
        for size in (2, 3):
            grams.extend((start, start + size, token[start:start + size])
                         for start in range(len(token) - size + 1))
        for index in range(len(token)):
            options = {}
            for start, end, gram in grams:
                if (start <= index < end and gram not in MATCH_STOP_TERMS
                        and gram[0] not in QUERY_NO_START and gram[-1] not in QUERY_NO_END
                        and not QUERY_INNER_PARTICLES & set(gram[1:-1])
                        and document_frequency.get(gram, 0) >= min_frequency):
                    weight = idf(gram)
                    if weight:
                        # Spread a word's weight over its characters: one word counts once.
                        options[gram] = weight / len(gram)
            if options:
                positions.append((max(options.values()), options, token, index))
    return positions


def _query_coverage(query_model: list[QueryPosition], index_entry: tuple[set[str], set[str]],
                    title_text: str = "") -> tuple[float, list[str], float]:
    """Return (coverage, readable matched query phrases, share of the title they fill)."""
    total = sum(position[0] for position in query_model)
    if not total:
        return 0.0, [], 0.0
    title, searchable = index_entry
    covered = 0.0
    hit: dict[str, set[int]] = {}
    for _, options, source, index in query_model:
        best = 0.0
        for term, weight in options.items():
            value = weight if term in title else weight * BODY_TERM_FACTOR if term in searchable else 0.0
            best = max(best, value)
        if best:
            covered += best
            hit.setdefault(source, set()).add(index)
    phrases = []
    for source, indexes in hit.items():
        if -1 in indexes:
            phrases.append(source)
            continue
        run = ""
        for index in range(len(source) + 1):
            if index in indexes:
                run += source[index]
            elif run:
                if len(run) > 1:
                    phrases.append(run)
                run = ""
    compact_title = re.sub(r"\s+", "", _normalize_text(title_text))
    in_title = sum(len(phrase) for phrase in phrases if phrase in compact_title)
    precision = min(1.0, in_title / len(compact_title)) if compact_title else 0.0
    return covered / total, sorted(set(phrases)), precision


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
        "rights": governance.get("rights", {}),
        "license": governance.get("license", {}),
        "entryUrl": item.get("source_url") or source.get("url"),
    }
    if "guidance" in item and public_content_allowed(item):
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
                "nodes": public_structured(item).get("nodes", []),
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
                "template": public_structured(item).get("template"),
                "variables": public_structured(item).get("variables", []),
                "resourceIds": item.get("resource_ids", []),
            }
        )
    return projected


def public_content_allowed(item: dict[str, Any]) -> bool:
    return (current_item(item) and item.get("access", "public") == "public"
            and item.get("governance", {}).get("rights", {}).get("status") == "full")


def public_structured(item: dict[str, Any], content: dict[str, Any] | None = None) -> dict[str, Any]:
    """Whitelist complete public structures without exposing internal extensions."""
    if not public_content_allowed(item):
        return {}
    content = item if content is None else content
    result = {key: content[key] for key in ("goal", "estimated_minutes", "scenario_ids", "workflow_ids",
              "purpose", "template", "variables", "resource_ids", "deliverable", "next_intent") if key in content}
    if "nodes" in content:
        result["nodes"] = [{key: node[key] for key in ("id", "title", "action", "prompt_ids", "resource_ids",
                           "completion_criteria") if key in node}
                           for node in content["nodes"] if isinstance(node, dict)]
    if "guidance" in content:
        validate_guidance(content["guidance"])
        result["guidance"] = content["guidance"]
    return result


def catalog_read_projection(catalog: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    """Public offline detail and one-hop navigation; never download related content."""
    source = item.get("governance", {}).get("source", {})
    result = {"id": item["id"], "title": item["title"], "summary": item["summary"],
              "version": item.get("version"), "contentHash": item.get("content_hash"),
              "access": item.get("access", "public"), "rights": item.get("governance", {}).get("rights", {}),
              "sourceUrl": source.get("url"), "entryUrl": item.get("source_url") or source.get("url"),
              "structured": public_structured(item), "related": []}
    if not public_content_allowed(item):
        return result
    refs = list(item.get("scenario_ids", [])) + list(item.get("workflow_ids", [])) + list(item.get("resource_ids", []))
    for node in result["structured"].get("nodes", []):
        refs.extend(node.get("prompt_ids", []))
        refs.extend(node.get("resource_ids", []))
    by_id = {entry["id"]: entry for entry in catalog["items"] if current_item(entry)}
    for ref in dict.fromkeys(refs):
        entry = by_id.get(ref)
        if entry:
            projected = _project_match(entry, 0, ["linked_id"])
            result["related"].append(projected)
    return result


def match_catalog(
    catalog: dict[str, Any],
    profile: dict[str, Any],
    *,
    limit_per_type: int = 3,
    exclude_guidance: bool = False,
) -> dict[str, Any]:
    if not 1 <= limit_per_type <= 10:
        raise ValueError("limit_per_type must be between 1 and 10")
    normalized_profile = _profile(profile)
    groups: dict[str, list[dict[str, Any]]] = {group: [] for group in GROUPS.values()}
    items = catalog.get("items", [])
    if not isinstance(items, list):
        raise ValueError("Community catalog items are invalid")
    indexed = [(item, _index_entry(item)) for item in items
               if isinstance(item, dict) and item.get("type") in GROUPS]
    document_frequency: dict[str, int] = {}
    for _, (_, searchable) in indexed:
        for term in searchable:
            document_frequency[term] = document_frequency.get(term, 0) + 1
    query_text = " ".join(normalized_profile[field] for field in ("identity", "goal", "deliverable", "query"))
    query_model = _query_model(query_text, document_frequency, len(indexed))
    coverages = [_query_coverage(query_model, index_entry, str(item.get("title", "")))
                 for item, index_entry in indexed]
    # Each group is shown on its own, so the relative bar is set per group.
    best: dict[str, float] = {}
    for (item, _), match in zip(indexed, coverages):
        best[item["type"]] = max(best.get(item["type"], 0.0), match[0])
    for (item, _), coverage_match in zip(indexed, coverages):
        if exclude_guidance and "guidance" in item:
            continue
        min_coverage = max(MIN_QUERY_COVERAGE, RELATIVE_QUERY_COVERAGE * best[item["type"]])
        scored = _score_item(item, normalized_profile, coverage_match, min_coverage)
        if scored is None:
            continue
        score, reasons, matched_terms = scored
        projected = _project_match(item, score, reasons)
        projected["matchedTerms"] = matched_terms
        groups[GROUPS[item["type"]]].append(projected)
    for group, matches in groups.items():
        matches.sort(key=lambda match: (-match["score"], ".db-" in match["id"], match["id"], match["version"]))
        # Knowledge-base mirrors repeat originals; show one entry per title.
        seen: set[str] = set()
        unique = []
        for match in matches:
            key = re.sub(r"\s+", "", _normalize_text(match["title"]))
            if key not in seen:
                seen.add(key)
                unique.append(match)
        groups[group] = unique[:limit_per_type]
    return {
        "catalogVersion": catalog.get("catalogVersion"),
        "contentDigest": catalog.get("contentDigest"),
        "profile": normalized_profile,
        **groups,
    }
