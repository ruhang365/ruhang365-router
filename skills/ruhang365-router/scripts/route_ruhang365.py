#!/usr/bin/env python3
"""Route an AI task through public, read-only Ruhan365 community APIs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from community_catalog import (  # noqa: E402
    DEFAULT_CATALOG_PATH,
    FULL_CATALOG_PATH,
    load_catalog,
    match_catalog,
    resolve_catalog,
    fetch_asset_detail,
)
from guidance import evaluate_guidance, current_item


DEFAULT_BASE_URL = "https://rhzl.ruhang365.cn"
INTENTS = ("auto", "discover", "writing", "visual", "tool", "knowledge")
CAPABILITIES = {
    "discover": ("knowledge", "skills"),
    "writing": ("knowledge",),
    "visual": ("knowledge", "prompts"),
    "tool": ("knowledge", "skills"),
    "knowledge": ("knowledge",),
}
RELEVANCE_STOP_TERMS = {
    "ai",
    "一个",
    "不知道",
    "人工智能",
    "什么",
    "使用",
    "可以",
    "如何",
    "帮我",
    "怎么",
    "普通人",
    "自己的",
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
    parser.add_argument("--query", default="", help="Optional question or task; omit to start guided discovery.")
    parser.add_argument("--guide", choices=("welcome", "career-change", "work-growth", "cross-border"), help="Start or continue career guidance.")
    parser.add_argument("--answer", action="append", default=[], help="Local-only choice, question_id=option_value; repeat to continue.")
    parser.add_argument("--intent", choices=INTENTS, default="auto")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("RUHANG365_API_BASE_URL", DEFAULT_BASE_URL),
        help="Override the API base URL for local or Preview testing.",
    )
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--identity", help="Role or identity used for Community matching.")
    parser.add_argument("--goal", help="Structured goal used for Community matching.")
    parser.add_argument("--experience", help="Experience level used for Community matching.")
    parser.add_argument(
        "--constraint",
        action="append",
        default=[],
        help="Repeatable constraint used for Community matching.",
    )
    parser.add_argument("--deliverable", help="Desired deliverable used for Community matching.")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG_PATH,
        help="Versioned Community catalog JSON path.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip remote retrieval and return the local route only.",
    )
    parser.add_argument("--read", help="Read one matched Community asset by stable id (public detail only).")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    query = args.query.strip()
    if not 2 <= len(query) <= 240 and not (not query or getattr(args, "guide", None)):
        raise ValueError("query must contain 2 to 240 characters")
    if len(query) > 240:
        raise ValueError("query must contain at most 240 characters")
    read_id = getattr(args, "read", None)
    if read_id is not None and (not read_id.strip() or len(read_id) > 200 or not re.fullmatch(r"r365\.(?:scenario|workflow|resource|prompt)\.[A-Za-z0-9._-]+", read_id.strip())):
        raise ValueError("read must be a valid Community stable id")
    for answer in getattr(args, "answer", []):
        key, sep, value = answer.partition("=")
        if not sep or not key.strip() or not value.strip() or len(answer) > 240:
            raise ValueError("answer must be question_id=option_value")
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
    for field in ("identity", "goal", "experience", "deliverable"):
        value = getattr(args, field, None)
        if value is not None and (not isinstance(value, str) or not 1 <= len(value.strip()) <= 120):
            raise ValueError(f"{field} must contain 1 to 120 characters")
    constraints = getattr(args, "constraint", []) or []
    if not isinstance(constraints, list) or len(constraints) > 10:
        raise ValueError("constraint may be repeated at most 10 times")
    if any(not isinstance(value, str) or not 1 <= len(value.strip()) <= 80 for value in constraints):
        raise ValueError("each constraint must contain 1 to 80 characters")


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


def build_matching_profile(args: argparse.Namespace, query: str) -> dict[str, Any]:
    return {
        "identity": getattr(args, "identity", None) or "",
        "goal": getattr(args, "goal", None) or query,
        "experience": getattr(args, "experience", None) or "",
        "constraints": getattr(args, "constraint", []) or [],
        "deliverable": getattr(args, "deliverable", None) or "",
    }


def legacy_scenarios(matches: dict[str, Any]) -> dict[str, Any]:
    scenario_matches = matches["scenarios"]
    if not scenario_matches:
        return {
            "profile": "general",
            "recommendedScenarioId": None,
            "items": [],
            "catalogVersion": matches["catalogVersion"],
            "contentDigest": matches["contentDigest"],
        }
    recommended = scenario_matches[0]
    identities = recommended.get("applicableIdentities") or ["general"]
    return {
        "profile": identities[0],
        "recommendedScenarioId": recommended["slug"],
        "items": [
            {
                "id": item["slug"],
                "stableId": item["id"],
                "version": item["version"],
                "title": item["title"],
                "deliverable": item["deliverable"],
                "nextIntent": item["nextIntent"],
                "workflowIds": item["workflowIds"],
                "completionCriteria": item["completionCriteria"],
                "score": item["score"],
            }
            for item in scenario_matches
        ],
        "catalogVersion": matches["catalogVersion"],
        "contentDigest": matches["contentDigest"],
    }


def discovery_scenarios(
    query: str,
    catalog_path: str | Path | None = None,
) -> dict[str, Any]:
    catalog = load_catalog(catalog_path)
    matches = match_catalog(
        catalog,
        {
            "identity": "",
            "goal": query,
            "experience": "",
            "constraints": [],
            "deliverable": "",
        },
    )
    return legacy_scenarios(matches)


def specialist_matches(matches: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "skill": item["slug"],
            "version": item["resourceVersion"],
            "repository": item["repositoryUrl"],
            "reason": item["purpose"],
        }
        for item in matches["resources"]
        if item["resourceKind"] == "skill" and item.get("repositoryUrl")
    ]


def relevance_terms(query: str) -> set[str]:
    normalized = query.casefold()
    terms = {
        term
        for term in re.findall(r"[a-z0-9][a-z0-9.+-]{1,}|[\u4e00-\u9fff]+", normalized)
        if term not in RELEVANCE_STOP_TERMS
    }
    for chinese_sequence in re.findall(r"[\u4e00-\u9fff]+", normalized):
        for size in (2, 3):
            terms.update(
                chinese_sequence[index : index + size]
                for index in range(len(chinese_sequence) - size + 1)
            )
    return {term for term in terms if term not in RELEVANCE_STOP_TERMS}


def filter_relevant(items: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    terms = relevance_terms(query)
    if not terms:
        return []
    relevant = []
    for item in items:
        searchable = json.dumps(item, ensure_ascii=False).casefold()
        if any(term in searchable for term in terms):
            relevant.append(item)
    return relevant


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
            "User-Agent": "ruhang365-router/0.3 legacy-public-read-only",
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


def retrieve_source(
    name: str,
    url: str,
    timeout: float,
    limit: int,
    query: str,
) -> dict[str, Any]:
    try:
        payload = fetch_json(url, timeout)
        items = PROJECTORS[name](payload, limit)
        relevant_items = filter_relevant(items, query)
        status = "ok" if relevant_items else "no_relevant_results"
        return {"status": status, "items": relevant_items}
    except urllib.error.HTTPError as error:
        return {"status": error_status(error), "items": []}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return {"status": "unavailable", "items": []}


def route_task(args: argparse.Namespace) -> dict[str, Any]:
    query = args.query.strip()
    intent = infer_intent(query) if args.intent == "auto" else args.intent
    capabilities = list(CAPABILITIES[intent])
    resolution = resolve_catalog(
        args.base_url,
        snapshot_path=getattr(args, "catalog", None),
        timeout=args.timeout,
        offline=args.offline,
    )
    catalog = resolution["catalog"]
    community_matches = match_catalog(
        catalog,
        build_matching_profile(args, query),
        limit_per_type=args.limit,
    )
    community_matches["catalogSource"] = resolution["source"]
    specialists = specialist_matches(community_matches)
    scenarios = legacy_scenarios(community_matches) if intent == "discover" else None
    sources: dict[str, Any] = {}

    source_status = "offline" if args.offline else "catalog_local_match"
    sources = {name: {"status": source_status, "items": []} for name in capabilities}
    warnings = [resolution["warning"]] if resolution["warning"] else []
    detail = None
    read_id = getattr(args, "read", None)
    if read_id:
        target = next((item for item in catalog.get("items", []) if item.get("id") == read_id), None)
        if not target:
            warnings.append("指定的 Community 资料不在当前目录版本中。")
        elif args.offline:
            warnings.append("离线模式只提供目录摘要；联网后再次使用 --read 读取正文。")
        else:
            try:
                detail = fetch_asset_detail(args.base_url, target, timeout=args.timeout)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
                warnings.append(f"Community 资料正文暂时不可用（{type(error).__name__}）。")

    return {
        "schemaVersion": "0.3",
        "query": query,
        "route": {
            "intent": intent,
            "capabilities": capabilities,
            "specialists": specialists,
            "scenarios": scenarios,
            "communityMatches": community_matches,
            "detail": detail,
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


def route_guidance(args: argparse.Namespace) -> dict[str, Any]:
    audience = getattr(args, "guide", None) or "welcome"
    execution = {"mode": "community", "remoteModelCalled": False, "writePerformed": False, "credentialsAccepted": False}
    welcome = "我可以帮你看懂职业变化、梳理已有经验，找到适合自己的方向和学习资料；也可以结合你当前的工作，看看哪里值得改善。"
    if audience == "welcome":
        return {"schemaVersion": "0.4", "displayName": "入行365｜职业成长向导", "introduction": welcome,
            "guidance": {"status": "welcome", "question": {"id": "audience", "prompt": "你现在更接近哪种情况？", "options": [
                {"value": "career-change", "label": "想了解新方向"},
                {"value": "work-growth", "label": "想把当前工作做得更好"},
                {"value": "cross-border", "label": "想开始跨境电商"},
                {"value": "unknown", "label": "暂时说不清"}]}}, "resources": [], "warnings": [], "execution": execution}
    answers = dict(answer.split("=", 1) for answer in getattr(args, "answer", []))
    guidance_snapshot = args.catalog if args.catalog != DEFAULT_CATALOG_PATH else FULL_CATALOG_PATH
    resolution = resolve_catalog(args.base_url, snapshot_path=guidance_snapshot, timeout=args.timeout, offline=args.offline)
    catalog = resolution["catalog"]
    guidance = evaluate_guidance(catalog, audience, answers)
    references = {ref for rec in guidance["recommendations"] for ref in rec["resourceIds"]}
    resources = [{"id": item["id"], "title": item["title"], "summary": item["summary"],
                  "sourceUrl": item.get("governance", {}).get("source", {}).get("url"),
                  "guidance": item.get("guidance")}
                 for item in catalog["items"] if item["id"] in references and current_item(item)]
    warnings = [resolution["warning"]] if resolution["warning"] else []
    detail = None
    read_id = getattr(args, "read", None)
    if read_id:
        target = next((item for item in catalog["items"] if item.get("id") == read_id), None)
        if target and not args.offline:
            try:
                detail = fetch_asset_detail(args.base_url, target, timeout=args.timeout)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
                warnings.append(f"Community 资料正文暂时不可用（{type(error).__name__}）。")
        elif args.offline:
            warnings.append("离线模式只提供目录摘要；联网后再次使用 --read 读取正文。")
        else:
            warnings.append("指定的 Community 资料不在当前目录版本中。")
    return {"schemaVersion": "0.4", "displayName": "入行365｜职业成长向导", "introduction": welcome,
        "catalogVersion": catalog["catalogVersion"], "contentDigest": catalog["contentDigest"],
        "catalogSource": resolution["source"], "guidance": guidance, "resources": resources, "detail": detail,
        "warnings": warnings, "execution": execution}


def print_guidance_markdown(result: dict[str, Any]) -> None:
    print(f"# {result['displayName']}\n\n{result['introduction']}")
    guidance = result["guidance"]
    if guidance.get("question"):
        question = guidance["question"]
        print(f"\n{question['prompt']}")
        for option in question["options"]:
            print(f"- {option['label']} (`{option['value']}`)")
        print("\n可以选不确定、跳过，或用自己的话补充；此前答案也可以修改。")
    for recommendation in guidance.get("recommendations", []):
        print(f"\n## {recommendation['title']}\n\n{recommendation['reason']}")
        for caution in recommendation["cautions"]:
            print(f"- {caution}")
    for resource in result["resources"]:
        print(f"\n### {resource['title']}\n\n{resource['summary']}")
        data = resource.get("guidance") or {}
        if data.get("kind") == "career":
            direction = data["direction"]
            print(f"\n实际做什么：{direction['whatItDoes']}")
            for field, label in (("transferableExperience", "可迁移经验"), ("entryThreshold", "进入门槛"), ("learnNext", "接下来了解")):
                print(f"\n{label}：" + "；".join(direction[field]))
            for entry in direction["resources"]:
                href = entry['href']
                if href.startswith('/'):
                    href = 'https://rhzl.ruhang365.cn' + href
                print(f"- [{entry['label']}]({href})：{entry['note']}")
            for signal in direction["signals"]:
                print(f"- {signal['kind']}：{signal['statement']}（{signal.get('observedAt', '日期待补')}；{signal.get('region', '地区待补')}）")
                if signal.get("sourceUrl"):
                    print(f"  来源：{signal['sourceUrl']}")
            print(f"\n证据边界：{direction['evidenceNote']}")
        elif data.get("kind") == "platform":
            for field, label in (("fitFor", "适合先了解的情况"), ("requirements", "需要核对的条件"), ("cautions", "适用边界")):
                print(f"\n{label}：" + "；".join(data[field]))
            for source in data["sources"]:
                print(f"- [{source['label']}]({source['url']})（核验：{source['checkedAt']}）")
    detail = result.get("detail")
    if isinstance(detail, dict):
        print(f"\n## 资料正文：{detail.get('title', detail.get('id', ''))}")
        if detail.get("body"):
            print(f"\n{detail['body']}")
        else:
            print("\n正文受访问条件或授权限制，请从原始来源继续。")
    if guidance.get("coverageNote"):
        print(f"\n{guidance['coverageNote']}")
    for warning in result.get("warnings", []):
        print(f"\n{warning}")


def print_markdown(result: dict[str, Any]) -> None:
    route = result["route"]
    print(f"# 入行365路由结果：{result['query']}")
    print(f"\n- 意图：`{route['intent']}`")
    print(f"- 能力：{', '.join(route['capabilities'])}")

    if route["specialists"]:
        print("\n## 建议专项 Skill")
        for item in route["specialists"]:
            print(f"- `{item['skill']}`：{item['reason']} ({item['repository']})")

    scenarios = route.get("scenarios")
    if scenarios:
        print(f"\n## 场景候选（{scenarios['profile']}）")
        for item in scenarios["items"]:
            recommended = "，推荐先做" if item["id"] == scenarios["recommendedScenarioId"] else ""
            print(f"- {item['title']}：{item['deliverable']}（下一意图：{item['nextIntent']}{recommended}）")

    community_matches = route["communityMatches"]
    print(f"\n## Community Catalog 匹配（{community_matches['catalogVersion']}）")
    group_labels = {
        "scenarios": "Scenario",
        "workflows": "Workflow",
        "resources": "Resource",
        "prompts": "Prompt",
    }
    for group, label in group_labels.items():
        for item in community_matches[group]:
            reasons = ", ".join(item["matchReasons"]) or "catalog"
            print(
                f"- {label}：{item['title']} "
                f"(`{item['id']}` @ `{item['version']}`；匹配：{reasons})"
            )

    detail = route.get("detail")
    if isinstance(detail, dict):
        print(f"\n## 资料正文：{detail.get('title', detail.get('id', ''))}")
        print(detail.get("body") or "正文受访问条件或授权限制，请从原始来源继续。")

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
        result = route_guidance(args) if getattr(args, "guide", None) or not args.query else route_task(args)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.format == "markdown":
        if "guidance" in result:
            print_guidance_markdown(result)
        else:
            print_markdown(result)
    else:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
