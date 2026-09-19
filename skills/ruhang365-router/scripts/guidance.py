"""Public guidance validation and deterministic, local-only intake evaluation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _text(value: Any) -> bool:
    return isinstance(value, str) and len(value) > 0


def _link(value: Any) -> bool:
    return _text(value) and (value.startswith(("http://", "https://"))
                             or (value.startswith("/") and not value.startswith("//")))


def _enum(*values):
    return lambda value: isinstance(value, str) and value in values


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(_text(entry) for entry in value)


def _object(value: Any, fields: dict, optional: tuple = ()) -> bool:
    return (isinstance(value, dict) and not set(value) - set(fields)
            and all(key in value for key in fields if key not in optional)
            and all(fields[key](entry) for key, entry in value.items()))


def _array(check):
    return lambda value: isinstance(value, list) and all(check(entry) for entry in value)


def _conditions(value: Any) -> bool:
    return (isinstance(value, dict)
            and all(_text(key) and _strings(values) and bool(values)
                    and not set(values) & {"unknown", "skip"} for key, values in value.items()))


def validate_guidance(value: Any) -> None:
    """Reject unknown nested fields rather than exposing a private extension."""
    option = lambda v: _object(v, {"value": _text, "label": _text})
    question = lambda v: _object(v, {
        "id": _text, "prompt": _text, "options": _array(option), "when": _conditions,
    }, ("when",))
    recommendation = lambda v: _object(v, {
        "id": _text, "title": _text, "when": lambda v: _conditions(v) and bool(v),
        "resourceIds": lambda ids: _strings(ids) and bool(ids),
        "reason": _text, "cautions": _strings,
    })
    resource = lambda v: _object(v, {"label": _text, "href": _link, "note": _text})
    career_resource = lambda v: _object(v, {"label": _text, "href": _link,
        "kind": _enum("article", "tool", "route", "daily"), "note": _text})
    signal = lambda v: _object(v, {"kind": _enum("招聘需求", "讨论热度", "商业需求"),
        "status": _enum("已接入站内资料", "已接入外部来源", "待补日期与地区来源"), "statement": _text,
        "sourceUrl": _link, "sourceLabel": _text, "observedAt": _text, "region": _text},
        ("sourceUrl", "sourceLabel", "observedAt", "region"))
    direction = lambda v: _object(v, {
        **{key: _text for key in ("slug", "name", "shortName", "category", "categoryLabel", "priority", "eyebrow", "summary", "whatItDoes", "whyNow", "difference", "evidenceNote")},
        **{key: _strings for key in ("fitFor", "transferableExperience", "entryThreshold", "learnNext")},
        "category": _enum("new-role", "career-upgrade", "independent-service"),
        "priority": _enum("重点首发", "基础覆盖"),
        "resources": _array(career_resource), "signals": _array(signal),
    })
    stage = lambda v: _object(v, {"title": _text, "outcome": _text, "actions": _strings})
    problem = lambda v: _object(v, {"title": _text, "detail": _text})
    journey = lambda v: _object(v, {
        **{key: _text for key in ("slug", "name", "category", "goal", "summary")},
        "legacySlugs": _strings, "abilities": _strings, "stages": _array(stage),
        "problems": _array(problem), "resources": _array(resource),
    })
    source = lambda v: _object(v, {"label": _text, "url": _link, "checkedAt": _text})
    shapes = {
        "career": {"kind": lambda v: v == "career", "direction": direction, "journey": journey},
        "platform": {"kind": lambda v: v == "platform", "summary": _text, "fitFor": _strings,
                     "requirements": _strings, "cautions": _strings, "sources": _array(source)},
        "intake": {"kind": lambda v: v == "intake", "audience": lambda v: v in ("career-change", "work-growth", "cross-border"),
                   "introduction": _text, "coverageNote": _text, "questions": _array(question),
                   "recommendations": _array(recommendation)},
    }
    if (not isinstance(value, dict) or not isinstance(value.get("kind"), str)
            or value["kind"] not in shapes or not _object(value, shapes[value["kind"]])):
        raise ValueError("invalid public guidance contract")
    if value["kind"] == "intake":
        questions = value["questions"]
        by_id = {q["id"]: q for q in questions}
        if len(by_id) != len(questions):
            raise ValueError("guidance question IDs must be unique")
        for q in questions:
            ids = [o["value"] for o in q["options"]]
            if not ids or len(set(ids)) != len(ids):
                raise ValueError("guidance option values must be unique and non-empty")
        rules = value["recommendations"]
        if len({r["id"] for r in rules}) != len(rules):
            raise ValueError("guidance recommendation IDs must be unique")
        for entry in [*questions, *rules]:
            for key, options in entry.get("when", {}).items():
                if key not in by_id or not set(options) <= {o["value"] for o in by_id[key]["options"]}:
                    raise ValueError("guidance condition refers to an unknown question or option")


def current_item(item: dict[str, Any]) -> bool:
    governance = item.get("governance", {})
    if item.get("status") != "current" or governance.get("stale") is not False:
        return False
    expiry = governance.get("stale_after")
    today = datetime.now(timezone.utc).date().isoformat()
    return not expiry or (isinstance(expiry, str) and expiry >= today)


def evaluate_guidance(catalog: dict[str, Any], audience: str, answers: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "no_match", "audience": audience, "question": None,
        "recommendations": [], "coverageNote": ""}
    items = {item["id"]: item for item in catalog.get("items", []) if current_item(item)}
    candidates = [item for item in catalog.get("items", [])
                  if item.get("guidance", {}).get("kind") == "intake"
                  and item["guidance"]["audience"] == audience]
    result["coverageNote"] = "\n".join(item["guidance"]["coverageNote"] for item in candidates)
    matches, questions = [], []
    for item in candidates:
        if not current_item(item):
            continue
        intake = item["guidance"]
        validate_guidance(intake)
        known = {q["id"]: {o["value"] for o in q["options"]} for q in intake["questions"]}
        selected = {key: value for key, value in answers.items()
                    if key in known and isinstance(value, str)
                    and (value in known[key] or value in ("unknown", "skip"))}

        def satisfies(conditions: dict[str, list[str]]) -> bool:
            return all(selected.get(key) not in (None, "unknown", "skip")
                       and selected[key] in values for key, values in conditions.items())

        matches.extend(r for r in intake["recommendations"]
                       if satisfies(r["when"]) and all(ref in items for ref in r["resourceIds"]))
        questions.extend(q for q in intake["questions"] if q["id"] not in selected and satisfies(q.get("when", {})))
    matches.sort(key=lambda r: (-len(r["when"]), r["id"]))
    if matches:
        result.update(status="ready", recommendations=matches[:3])
        return result
    question = next(iter(questions), None)
    if question:
        result.update(status="question", question=question)
    return result
