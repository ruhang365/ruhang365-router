#!/usr/bin/env python3
"""Route an AI task through public, read-only Ruhan365 community APIs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "https://rhzl.ruhang365.cn"
INTENTS = ("auto", "discover", "writing", "visual", "tool", "knowledge")
CAPABILITIES = {
    "discover": ("knowledge", "skills"),
    "writing": ("knowledge", "skills"),
    "visual": ("knowledge", "skills", "prompts"),
    "tool": ("knowledge", "skills"),
    "knowledge": ("knowledge",),
}
SPECIALISTS = {
    "writing": (
        {
            "skill": "ai-writing-humanizer",
            "repository": "https://github.com/ruhang365/ruhang365-ai-writing-humanizer-skill",
            "reason": "Preserve facts and author voice while removing templated Chinese AI writing patterns.",
        },
    ),
    "visual": (
        {
            "skill": "ruhang365-visual-prompt-router",
            "repository": "https://github.com/fzy2012/ruhang365-visual-prompt-skill",
            "reason": "Retrieve rights-aware visual references and prepare a task-specific image prompt.",
        },
    ),
}

KNOWLEDGE_FIELDS = (
    "id",
    "title",
    "description",
    "content_type",
    "source_url",
    "action_label",
    "tags",
    "target_goals",
    "target_identities",
    "difficulty",
    "estimated_minutes",
    "risk_note",
)
SKILL_FIELDS = (
    "id",
    "slug",
    "title",
    "subtitle",
    "description",
    "skill_type",
    "version",
    "tags",
    "usage_count",
    "average_rating",
    "pricing_mode",
)
PROMPT_FIELDS = (
    "id",
    "collection",
    "title",
    "category",
    "tags",
    "recommended",
    "rights",
    "summary",
    "prompt",
    "score",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True, help="Short task-oriented query.")
    parser.add_argument("--intent", choices=INTENTS, default="auto")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("RUHANG365_API_BASE_URL", DEFAULT_BASE_URL),
        help="Override the API base URL for local or Preview testing.",
    )
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip remote retrieval and return the local route only.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    query = args.query.strip()
    if not 2 <= len(query) <= 240:
        raise ValueError("query must contain 2 to 240 characters")
    if not 1 <= args.limit <= 5:
        raise ValueError("limit must be between 1 and 5")
    if not 0 < args.timeout <= 60:
        raise ValueError("timeout must be greater than 0 and at most 60 seconds")

    parsed = urllib.parse.urlparse(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be an http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("base URL must not embed credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("base URL must not include a query or fragment")


def infer_intent(query: str) -> str:
    normalized = query.casefold()
    keyword_groups = (
        ("discover", ("不知道", "能做什么", "应用场景", "找方向", "what can ai", "use case")),
        ("visual", ("封面", "海报", "信息图", "图片", "生图", "改图", "视觉", "image", "poster", "cover")),
        ("writing", ("文章", "写作", "改写", "文案", "脚本", "公众号", "小红书", "知乎", "newsletter")),
        ("tool", ("工具", "软件", "选型", "工作流", "哪个好", "tool", "workflow")),
        ("knowledge", ("资料", "知识", "教程", "学习", "解释", "guide", "learn")),
    )
    for intent, keywords in keyword_groups:
        if any(keyword in normalized for keyword in keywords):
            return intent
    return "discover"


def build_url(base_url: str, path: str, params: dict[str, str]) -> str:
    base = base_url.rstrip("/")
    return f"{base}{path}?{urllib.parse.urlencode(params)}"


def build_requests(base_url: str, query: str, intent: str, limit: int) -> dict[str, str]:
    requests = {
        "knowledge": build_url(
            base_url,
            "/api/knowledge/search",
            {"q": query, "limit": str(limit)},
        ),
        "skills": build_url(
            base_url,
            "/api/skills/recommend",
            {"goal": query, "limit": str(limit)},
        ),
        "prompts": build_url(
            base_url,
            "/api/v1/prompt-library/search",
            {"q": query, "assetType": "image_prompt", "limit": str(limit)},
        ),
    }
    return {name: requests[name] for name in CAPABILITIES[intent]}


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ruhang365-router/0.1 community-read-only",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("service returned a non-object response")
    return payload


def project_fields(item: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    return {field: item[field] for field in fields if field in item}


def project_knowledge(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("knowledge service returned an invalid contract")
    return [project_fields(item, KNOWLEDGE_FIELDS) for item in items[:limit] if isinstance(item, dict)]


def project_skills(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    items = payload.get("skills", payload.get("data"))
    if not isinstance(items, list):
        raise ValueError("skill service returned an invalid contract")
    return [project_fields(item, SKILL_FIELDS) for item in items[:limit] if isinstance(item, dict)]


def project_prompts(payload: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    items = payload.get("results")
    if not isinstance(items, list):
        raise ValueError("prompt service returned an invalid contract")

    projected: list[dict[str, Any]] = []
    for raw_item in items[:limit]:
        if not isinstance(raw_item, dict):
            continue
        item = project_fields(raw_item, PROMPT_FIELDS)
        rights = item.get("rights")
        if not isinstance(rights, dict) or rights.get("status") != "full":
            item.pop("prompt", None)
        projected.append(item)
    return projected


PROJECTORS = {
    "knowledge": project_knowledge,
    "skills": project_skills,
    "prompts": project_prompts,
}


def error_status(error: urllib.error.HTTPError) -> str:
    if error.code in {401, 403}:
        return "access_denied"
    if error.code == 404:
        return "not_found"
    if error.code == 429:
        return "rate_limited"
    return "unavailable"


def retrieve_source(name: str, url: str, timeout: float, limit: int) -> dict[str, Any]:
    try:
        payload = fetch_json(url, timeout)
        items = PROJECTORS[name](payload, limit)
        return {"status": "ok", "items": items}
    except urllib.error.HTTPError as error:
        return {"status": error_status(error), "items": []}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return {"status": "unavailable", "items": []}


def route_task(args: argparse.Namespace) -> dict[str, Any]:
    query = args.query.strip()
    intent = infer_intent(query) if args.intent == "auto" else args.intent
    capabilities = list(CAPABILITIES[intent])
    specialists = [dict(item) for item in SPECIALISTS.get(intent, ())]
    sources: dict[str, Any] = {}

    if args.offline:
        sources = {name: {"status": "offline", "items": []} for name in capabilities}
    else:
        urls = build_requests(args.base_url, query, intent, args.limit)
        sources = {
            name: retrieve_source(name, url, args.timeout, args.limit)
            for name, url in urls.items()
        }

    warnings = [
        f"{name} retrieval is {source['status']}; use the local route only."
        for name, source in sources.items()
        if source["status"] != "ok"
    ]

    return {
        "schemaVersion": "0.1",
        "query": query,
        "route": {
            "intent": intent,
            "capabilities": capabilities,
            "specialists": specialists,
        },
        "sources": sources,
        "warnings": warnings,
        "execution": {
            "mode": "community",
            "remoteModelCalled": False,
            "writePerformed": False,
            "credentialsAccepted": False,
        },
    }


def print_markdown(result: dict[str, Any]) -> None:
    route = result["route"]
    print(f"# 入行365路由结果：{result['query']}")
    print(f"\n- 意图：`{route['intent']}`")
    print(f"- 能力：{', '.join(route['capabilities'])}")

    if route["specialists"]:
        print("\n## 建议专项 Skill")
        for item in route["specialists"]:
            print(f"- `{item['skill']}`：{item['reason']} ({item['repository']})")

    labels = {"knowledge": "公开资料", "skills": "Skill 推荐", "prompts": "视觉 Prompt"}
    for source_name, source in result["sources"].items():
        print(f"\n## {labels[source_name]}（{source['status']}）")
        if not source["items"]:
            print("\n没有可用结果。")
            continue
        for index, item in enumerate(source["items"], start=1):
            title = item.get("title") or item.get("slug") or item.get("id") or "Untitled"
            print(f"\n### {index}. {title}")
            description = item.get("description") or item.get("summary")
            if description:
                print(description)
            if item.get("source_url"):
                print(f"\n来源：{item['source_url']}")
            rights = item.get("rights")
            if isinstance(rights, dict):
                print(f"\n授权：{rights.get('status', '-')} / {rights.get('license', '-')}")
                if rights.get("sourceUrl"):
                    print(f"\n来源：{rights['sourceUrl']}")
            if item.get("prompt"):
                print("\n```text")
                print(item["prompt"])
                print("```")

    if result["warnings"]:
        print("\n## 降级说明")
        for warning in result["warnings"]:
            print(f"- {warning}")


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
        result = route_task(args)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.format == "markdown":
        print_markdown(result)
    else:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
