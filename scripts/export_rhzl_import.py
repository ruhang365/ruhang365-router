#!/usr/bin/env python3
"""Export a deterministic, read-only RHZL runtime-index import contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = REPO_ROOT / "skills" / "ruhang365-router" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from community_catalog import DEFAULT_CATALOG_PATH, load_catalog  # noqa: E402


SOURCE_KEY = "github:ruhang365/ruhang365-router"
RESOURCE_CONTENT_TYPES = {
    "knowledge": "knowledge_card",
    "template": "task",
    "tool": "tool",
    "service": "use_case",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH)
    return parser.parse_args()


def source_url(item: dict[str, Any]) -> str:
    return item["governance"]["source"]["url"]


def difficulty(item: dict[str, Any]) -> str:
    levels = item["applicability"]["experience_levels"]
    if levels == ["advanced"]:
        return "hard"
    if "beginner" in levels:
        return "easy"
    return "medium"


def knowledge_row(item: dict[str, Any], content_type: str) -> dict[str, Any]:
    public_body = item.get("template") if content_type == "prompt" else None
    estimated_minutes = item.get("estimated_minutes")
    deliverable = item.get("deliverable") or item.get("purpose") or item.get("goal")
    return {
        "source_key": SOURCE_KEY,
        "source_uid": f"{SOURCE_KEY}:{item['id']}@{item['version']}",
        "content_type": content_type,
        "title": item["title"],
        "description": item["summary"],
        "content": public_body or item["summary"],
        "source_url": source_url(item),
        "source_repo": "ruhang365/ruhang365-router",
        "source_kind": "github",
        "ingestion_mode": "bulk_source",
        "source_license_status": "open_license",
        "content_visibility": "full_public",
        "public_summary": item["summary"],
        "public_body": public_body,
        "internal_body": None,
        "target_level": item["applicability"]["experience_levels"],
        "target_role": item["applicability"]["identities"],
        "target_goals": item["applicability"]["goals"],
        "target_identities": item["applicability"]["identities"],
        "target_levels": item["applicability"]["experience_levels"],
        "scenes": item.get("scenario_ids", []),
        "difficulty": difficulty(item),
        "estimated_minutes": estimated_minutes,
        "deliverable": deliverable,
        "action_label": "开始使用",
        "risk_note": None,
        "review_status": "approved",
        "status": "published",
        "tags": item["tags"],
        "metadata": {
            "community_id": item["id"],
            "community_type": item["type"],
            "community_version": item["version"],
            "completion_criteria": item["completion_criteria"],
            "content_path": item.get("contentPath"),
        },
    }


def scenario_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": item["slug"],
        "title": item["title"],
        "subtitle": item["deliverable"],
        "description": item["summary"],
        "type": "flowchart",
        "recipe_data": {
            "community_id": item["id"],
            "community_version": item["version"],
            "workflow_ids": item["workflow_ids"],
            "completion_criteria": item["completion_criteria"],
            "source_url": source_url(item),
        },
        "status": "published",
    }


def skill_row(item: dict[str, Any]) -> dict[str, Any]:
    capabilities = item["capabilities"]
    category = "video" if any("video" in value for value in capabilities) else "content"
    return {
        "slug": item["slug"],
        "title": item["title"],
        "subtitle": item["summary"],
        "description": item["purpose"],
        "category": category,
        "skill_type": "agent_skill",
        "pricing_mode": "free",
        "price": 0,
        "original_price": None,
        "status": "published",
        "creator_ref": "official:ruhang365",
        "creator_type": "official",
        "creator_name": "入行365",
        "creator_avatar": None,
        "cover_image": None,
        "content": {
            "community_id": item["id"],
            "community_version": item["version"],
            "repository_url": item.get("repository_url"),
            "source_url": item["source_url"],
            "completion_criteria": item["completion_criteria"],
        },
        "usage_guide": item["purpose"],
        "tags": item["tags"],
        "industries": [],
        "target_level": difficulty(item),
        "target_dimensions": [],
        "version": item["resource_version"],
        "usage_count": 0,
        "favorite_count": 0,
        "review_count": 0,
        "average_rating": 0,
        "is_featured": False,
        "sort_order": 0,
    }


def export_contract(catalog: dict[str, Any]) -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []
    knowledge_base: list[dict[str, Any]] = []
    skills: list[dict[str, Any]] = []
    for item in catalog["items"]:
        governance = item.get("governance")
        if (
            item.get("status") != "current"
            or not isinstance(governance, dict)
            or governance.get("stale") is not False
        ):
            continue
        if item["type"] == "scenario":
            scenarios.append(scenario_row(item))
        elif item["type"] == "workflow":
            knowledge_base.append(knowledge_row(item, "workflow"))
        elif item["type"] == "prompt":
            knowledge_base.append(knowledge_row(item, "prompt"))
        elif item["type"] == "resource" and item["resource_kind"] == "skill":
            skills.append(skill_row(item))
        elif item["type"] == "resource":
            knowledge_base.append(
                knowledge_row(item, RESOURCE_CONTENT_TYPES[item["resource_kind"]])
            )
    scenarios.sort(key=lambda row: row["slug"])
    knowledge_base.sort(key=lambda row: row["source_uid"])
    skills.sort(key=lambda row: row["slug"])
    return {
        "contractVersion": "1.0.0",
        "catalogVersion": catalog["catalogVersion"],
        "contentDigest": catalog["contentDigest"],
        "source": {
            "source_key": SOURCE_KEY,
            "name": "Ruhang365 Public Community Catalog",
            "source_type": "github_repo",
            "url": "https://github.com/ruhang365/ruhang365-router",
            "repo": "ruhang365/ruhang365-router",
            "parser": "ruhang365_community_catalog_v1",
            "sync_frequency": "release",
            "license_status": "open_license",
            "content_visibility": "full_public",
            "metadata": {
                "catalog_version": catalog["catalogVersion"],
                "content_digest": catalog["contentDigest"],
                "direction": "community_to_rhzl_only",
            },
        },
        "indexes": {
            "scenarios": scenarios,
            "knowledge_base": knowledge_base,
            "skills": skills,
        },
        "execution": {
            "mode": "read_only_contract_export",
            "writePerformed": False,
            "requiresRuntimeCreatorResolution": True,
        },
    }


def main() -> int:
    args = parse_args()
    try:
        catalog = load_catalog(args.catalog)
        payload = export_contract(catalog)
    except (OSError, ValueError, KeyError) as error:
        print(f"RHZL import export failed: {error}", file=sys.stderr)
        return 1
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
