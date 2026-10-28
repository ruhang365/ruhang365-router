"""Local guide conditions and explicit resource links, mirrored from the Web guide.

No user condition is sent to the catalog API. These are source-backed reading
notes, not a score of a person's suitability, ability, or employment prospects.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from community_catalog import GROUPS, _project_match, match_catalog, public_content_allowed, catalog_read_projection
from guidance import current_item


CONDITION_CHOICES = {
    "experience": ("", "new", "product", "operations", "technical", "business"),
    "coding": ("", "none", "basic", "ready"),
    "weeklyHours": ("", "2", "4", "8"),
    "budget": ("", "0", "1000", "more"),
    "supplyChain": ("", "yes", "no", "unknown"),
}
EXPERIENCE_TERMS = {
    "product": ["产品"], "operations": ["运营", "营销", "增长", "社群"],
    "technical": ["开发", "软件", "数据", "自动化"],
    "business": ["行业", "客户", "经营", "供应商"],
}


def parse_conditions(entries: list[str]) -> dict[str, str]:
    result = {"experience": "", "coding": "", "weeklyHours": "", "budget": ""}
    seen = set()
    for entry in entries:
        key, sep, value = entry.partition("=")
        if not sep or key not in CONDITION_CHOICES or value not in CONDITION_CHOICES[key]:
            raise ValueError("condition must use a supported Web guide key and option value")
        if key in seen:
            raise ValueError(f"condition {key} must be supplied only once; replace the previous value")
        seen.add(key)
        result[key] = value
    return result


def fits_experience(item: dict[str, Any], conditions: dict[str, str]) -> bool:
    guidance = item.get("guidance") or {}
    return guidance.get("kind") == "career" and any(
        term in value for term in EXPERIENCE_TERMS.get(conditions.get("experience", ""), [])
        for value in guidance["direction"]["fitFor"])


def allowed_guide_items(items: list[dict[str, Any]], constraints: list[str]) -> list[dict[str, Any]]:
    selected = {entry.strip().casefold() for entry in constraints if entry.strip()}
    return [item for item in items if current_item(item) and item.get("guidance", {}).get("kind") != "intake" and not selected.intersection(
        entry.strip().casefold() for entry in item.get("applicability", {}).get("excluded_constraints", []))]


def refine_recommendations(recommendations: list[dict[str, Any]], items: list[dict[str, Any]],
                           allowed_ids: set[str], conditions: dict[str, str],
                           prefer_upgrade: bool = False) -> list[dict[str, Any]]:
    by_id = {item["id"]: item for item in items}
    results = []
    for recommendation in recommendations:
        ids = [ref for ref in recommendation["resourceIds"] if ref in allowed_ids]
        if not ids:
            continue
        refined = {**recommendation, "resourceIds": ids}
        if len(ids) < len(recommendation["resourceIds"]):
            refined.update(
                title="先核对保留模式的经营条件" if len(ids) == 1 else "排除冲突后，继续比较这些模式",
                reason="已排除入行条件或资料描述与已选排除项冲突的模式。其余资料用于理解经营责任，仍需核对是否具备供货、主体和协作条件。",
                cautions=[*recommendation["cautions"], "按排除项移除：" + "、".join(
                    by_id.get(ref, {}).get("title", "暂不可用资料") for ref in recommendation["resourceIds"] if ref not in allowed_ids)])
        results.append(refined)
    comparing_careers = any(sum(by_id.get(ref, {}).get("guidance", {}).get("kind") == "career"
                               for ref in entry["resourceIds"]) > 1 for entry in results)
    if not comparing_careers and any(by_id.get(ref, {}).get("guidance", {}).get("kind") == "career"
           for entry in results for ref in entry["resourceIds"]):
        upgrade_slug = {"product": "product-manager-ai-upgrade", "operations": "operations-marketing-ai-upgrade"}.get(conditions.get("experience"))
        upgrade = next((item for item in items if item["id"] in allowed_ids
                        and item.get("guidance", {}).get("kind") == "career"
                        and item["guidance"]["direction"]["slug"] == upgrade_slug
                        and fits_experience(item, conditions)), None)
        if upgrade and not any(upgrade["id"] in entry["resourceIds"] for entry in results):
            results.append({"id": f"experience-{upgrade['id']}", "title": f"也可比较：{upgrade['title']}",
                "when": {}, "resourceIds": [upgrade["id"]],
                "reason": "你选择了已有工作经验；这份原岗位升级资料明确列出相关经验，可与新方向对照。",
                "cautions": ["经验匹配不代表已具备全部能力；请继续核对资料中的门槛。"]})

    def score(entry):
        value = 0
        for ref in entry["resourceIds"]:
            item = by_id.get(ref, {})
            if item.get("guidance", {}).get("kind") != "career":
                continue
            direction = item["guidance"]["direction"]
            fit = fits_experience(item, conditions)
            value += (2 if fit else 0) + (3 if prefer_upgrade and direction["category"] == "career-upgrade" else 0)
            value -= 2 if conditions.get("coding") == "none" and any("代码" in text for text in direction["fitFor"]) else 0
        return value

    return sorted(results, key=lambda entry: (int(entry["id"].startswith("experience-")) if not prefer_upgrade else 0, -score(entry)))[:3]


def condition_notes(item: dict[str, Any], conditions: dict[str, str]) -> list[str]:
    notes = []
    guidance = item.get("guidance") or {}
    if guidance.get("kind") == "career":
        direction = guidance["direction"]
        if fits_experience(item, conditions):
            notes.append(f"你选择的经验与资料标注相符：{'；'.join(direction['fitFor'])}。可迁移的经验：{'；'.join(direction['transferableExperience'])}。")
        elif conditions.get("experience") == "new":
            notes.append(f"你选择从零了解；这份资料的适用背景是“{'；'.join(direction['fitFor'])}”，先核对经验缺口。")
        if conditions.get("coding") == "none":
            notes.append("你选择了不会编程，而资料包含代码协作工作。先了解职责与学习门槛，不把这条路径当成可以立即交付的工作。"
                         if any("代码" in value for value in direction["fitFor"]) else
                         f"你选择了不会编程，本次从资料中的问题与业务判断开始；仍需核对这些能力：{'；'.join(direction['entryThreshold'])}。")
        stages = guidance["journey"]["stages"]
        if conditions.get("weeklyHours") and stages and stages[0].get("actions"):
            first = stages[0]
            notes.append(f"每周约 {conditions['weeklyHours']} 小时：先从“{first['title']}”开始——{first['actions'][0]}；做到“{first['outcome']}”后再决定是否继续。资料没有阶段耗时，请按自己的节奏分次推进。")
    elif guidance.get("kind") == "platform":
        if any(re.search("工厂|贸易|供应商|供货", value) for value in guidance["fitFor"]):
            notes.append("你选择已有供货或供应商协作资源；仍需核对真实经营主体、商品能力与交易责任，不据此确认可以入驻或获利。"
                if conditions.get("supplyChain") == "yes" else
                "你选择目前没有供货或供应商协作资源；这份资料只适合了解 B2B 模式，不建议据此开始开户、投货或付费。"
                if conditions.get("supplyChain") == "no" else
                "这份资料适合有工厂、贸易或供应商协作背景的人；你还没有确认这一前提，目前只建议了解，不据此判断适合开展。")
        if conditions.get("weeklyHours"):
            notes.append(f"你每周可投入约 {conditions['weeklyHours']} 小时；资料没有各阶段耗时，先了解模式并核对经营主体、供货与交易责任，不能据此确认开户，先不安排开户或投货。")
    if conditions.get("budget"):
        budget = {"0": "暂不投入费用", "1000": "1000 元以内", "more": "超过 1000 元"}[conditions["budget"]]
        notes.append(f"你选择的预算是{budget}；当前资料没有完整费用清单，不能据此确认预算是否足够。")
    return notes


def _safe_href(value: Any) -> str | None:
    if not isinstance(value, str) or not value or re.search(r"[\x00-\x20\\]", value):
        return None
    if value.startswith("/") and not value.startswith("//"):
        return value
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    return value if parsed.scheme in ("http", "https") and parsed.netloc and not parsed.username and not parsed.password else None


def recommended_links(items: list[dict[str, Any]], resource_ids: list[str]) -> list[dict[str, Any]]:
    by_id = {item["id"]: item for item in items}
    result, seen = [], set()
    for ref in resource_ids:
        guidance = by_id.get(ref, {}).get("guidance", {})
        for link in guidance.get("direction", {}).get("resources", []) if guidance.get("kind") == "career" else []:
            href = _safe_href(link.get("href"))
            if href and href not in seen:
                seen.add(href)
                result.append(link)
    return result


def search_guide_resources(items: list[dict[str, Any]], query: str, limit: int = 8) -> list[dict[str, Any]]:
    compact = lambda value: re.sub(r"\s+", "", value.lower())
    normalized = compact(query).replace("顾客评论", "顾客反馈").replace("用户评论", "用户反馈")
    terms = re.findall(r"[a-z0-9][a-z0-9.+-]*|[\u4e00-\u9fff]+", normalized)
    if not terms:
        return []

    def covered(term, text):
        if term in text:
            return True
        if not re.fullmatch(r"[\u4e00-\u9fff]+", term) or len(term) < 4:
            return False
        positions, longest = set(), 0
        for size in range(min(len(term), 8), 1, -1):
            for start in range(len(term) - size + 1):
                if term[start:start + size] in text:
                    positions.update(range(start, start + size))
                    longest = max(longest, size)
        return longest >= 3 and len(positions) / len(term) >= 0.6

    candidates = [item for item in items if all(covered(term, compact(" ".join([
        item["title"], item["summary"], *item.get("tags", []), *item.get("match_terms", [])]))) for term in terms)]
    matches = match_catalog({"items": candidates}, {"query": normalized}, limit_per_type=10)
    ranked = sorted((entry for group in GROUPS.values() for entry in matches[group]), key=lambda entry: (-entry["score"], entry["id"], entry["version"]))
    by_id = {item["id"]: item for item in candidates}
    result, seen = [], set()
    for entry in ranked:
        item = by_id[entry["id"]]
        key = compact(f"{item['type']}:{item['title']}")
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result[:limit]


def linked_guide_matches(catalog: dict[str, Any], resource_ids: list[str], links: list[dict[str, Any]],
                         allowed_items: list[dict[str, Any]], query: str, limit: int) -> dict[str, Any]:
    """Explicit guide links plus strict user search; answer labels are not search terms."""
    result = match_catalog({**catalog, "items": []}, {"query": query}, limit_per_type=limit)
    by_id = {item["id"]: item for item in allowed_items}
    refs = dict.fromkeys(resource_ids)
    hrefs = {link["href"] for link in links}
    for item in allowed_items:
        urls = {item.get("source_url"), item.get("governance", {}).get("source", {}).get("url")}
        if hrefs.intersection(urls):
            refs[item["id"]] = None
    # Resolve only declared relations. A career can link a workflow which links
    # its node templates; no token match creates any of these relationships.
    for _ in range(2):
        for ref in list(refs):
            item = by_id.get(ref)
            if item and public_content_allowed(item):
                for related in (entry["id"] for entry in catalog_read_projection(catalog, item)["related"]):
                    if related in by_id:
                        refs[related] = None
    for ref in refs:
        item = by_id.get(ref)
        if item and item.get("type") in GROUPS:
            projected = _project_match(item, 0, ["linked_id"])
            projected["matchedTerms"] = []
            result[GROUPS[item["type"]]].append(projected)
    existing = set(refs)
    for item in search_guide_resources(allowed_items, query, limit):
        if item["id"] not in existing and item.get("guidance", {}).get("kind") != "intake":
            projected = _project_match(item, 0, ["query_coverage"])
            projected["matchedTerms"] = [query.strip()]
            result[GROUPS[item["type"]]].append(projected)
    for group in GROUPS.values():
        result[group] = result[group][:limit]
    return result
