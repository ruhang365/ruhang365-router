from __future__ import annotations

import copy
import importlib.util
import itertools
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("guidance_under_test", ROOT / "skills/ruhang365-router/scripts/guidance.py")
guidance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guidance)
CANDIDATE = os.environ.get("RHZL_CATALOG_PATH")


def fixture():
    return {"kind": "intake", "audience": "career-change", "introduction": "帮助",
            "coverageNote": "覆盖", "questions": [{"id": "goal", "prompt": "目标？",
            "options": [{"value": "learn", "label": "了解"}, {"value": "unknown", "label": "未知"}, {"value": "skip", "label": "跳过"}]}],
            "recommendations": [{"id": "learn", "title": "了解", "when": {"goal": ["learn"]},
            "resourceIds": ["resource"], "reason": "你的选择", "cautions": []}]}


class GuidanceContractTests(unittest.TestCase):
    def test_unknown_skip_and_invalid_are_not_positive_matches(self):
        intake = fixture()
        catalog = {"items": [{"id": "intake", "status": "current", "governance": {"stale": False}, "guidance": intake},
                             {"id": "resource", "status": "current", "governance": {"stale": False}}]}
        self.assertEqual(guidance.evaluate_guidance(catalog, "career-change", {"goal": "learn"})["status"], "ready")
        for value in ("unknown", "skip", "invalid", "free text"):
            result = guidance.evaluate_guidance(catalog, "career-change", {"goal": value})
            self.assertEqual(result["recommendations"], [])
            self.assertEqual(result["status"], "no_match" if value in ("unknown", "skip") else "question")

    def test_empty_question_condition_valid_but_empty_recommendation_invalid(self):
        value = fixture()
        value["questions"][0]["when"] = {}
        guidance.validate_guidance(value)
        value["recommendations"][0]["when"] = {}
        with self.assertRaises(ValueError):
            guidance.validate_guidance(value)

    def test_conditions_cannot_use_unknown_skip_or_undefined_options(self):
        for answer in ("unknown", "skip", "invalid"):
            value = fixture()
            value["recommendations"][0]["when"] = {"goal": [answer]}
            with self.assertRaises(ValueError):
                guidance.validate_guidance(value)

    def test_platform_urls_and_private_fields_rejected(self):
        value = {"kind": "platform", "summary": "说明", "fitFor": [], "requirements": [], "cautions": [],
                 "sources": [{"label": "官方", "url": "https://example.com", "checkedAt": "2026-09-17"}]}
        guidance.validate_guidance(value)
        for url in ("javascript:alert(1)", "//evil.example", "file:///tmp/local", "mailto:x@y", ""):
            bad = copy.deepcopy(value)
            bad["sources"][0]["url"] = url
            with self.assertRaises(ValueError):
                guidance.validate_guidance(bad)
        value["private"] = "secret"
        with self.assertRaises(ValueError):
            guidance.validate_guidance(value)


@unittest.skipUnless(CANDIDATE, "set RHZL_CATALOG_PATH for actual 30-item TS/Python parity")
class ActualCandidateParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(CANDIDATE).resolve()
        cls.catalog = json.loads(cls.path.read_text())
        cls.rhzl = cls.path.parents[2]

    def ts(self, mode, cases):
        script = '''
          import {evaluateGuidance} from "./src/lib/community/guidance.ts";
          import {projectGuidance} from "./src/lib/community/guidance-schema.ts";
          import {canonicalJson} from "./src/lib/community/catalog.ts";
          let raw=""; for await(const chunk of process.stdin)raw+=chunk;
          const input=JSON.parse(raw);
          const results=input.cases.map(c=>{
            if(input.mode==="validate") {try {const p=projectGuidance(c);return canonicalJson(p)===canonicalJson(c)}catch{return false}}
            const catalog=structuredClone(input.catalog);
            if(c.remove)catalog.items=catalog.items.filter(i=>i.id!==c.remove);
            if(c.expire){catalog.items.find(i=>i.id===c.expire).governance.stale_after="2000-01-01"}
            if(c.stale){catalog.items.find(i=>i.id===c.stale).governance.stale=true}
            return evaluateGuidance(catalog,c.audience,c.answers);
          }); console.log(JSON.stringify(results));
        '''
        run = subprocess.run(["node", "--import", "tsx", "--input-type=module", "-e", script], cwd=self.rhzl,
                             input=json.dumps({"mode": mode, "catalog": self.catalog, "cases": cases}), text=True,
                             capture_output=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads(run.stdout)

    def test_complete_results_match_for_all_option_combinations_and_failures(self):
        self.assertEqual(len(self.catalog["items"]), 30)
        cases = []
        for item in self.catalog["items"]:
            g = item.get("guidance", {})
            if g.get("kind") != "intake":
                continue
            audience = g["audience"]
            cases.append({"audience": audience, "answers": {}})
            questions = g["questions"]
            for selected in itertools.product(*[[o["value"] for o in q["options"]] for q in questions]):
                cases.append({"audience": audience, "answers": dict(zip([q["id"] for q in questions], selected))})
            for invalid in ("invalid", "free text", "", 42, None):
                cases.append({"audience": audience, "answers": {questions[0]["id"]: invalid}})
            for r in g["recommendations"]:
                answers = {key: values[0] for key, values in r["when"].items()}
                for mutation, target in (("expire", item["id"]), ("expire", r["resourceIds"][0]),
                                         ("remove", r["resourceIds"][0]), ("stale", r["resourceIds"][0])):
                    cases.append({"audience": audience, "answers": answers, mutation: target})
        cases.append({"audience": "invalid", "answers": {}})
        expected = self.ts("evaluate", cases)
        self.assertEqual(len(expected), len(cases))
        for case, ts_result in zip(cases, expected):
            catalog = copy.deepcopy(self.catalog)
            if "remove" in case:
                catalog["items"] = [i for i in catalog["items"] if i["id"] != case["remove"]]
            for flag, key, value in (("expire", "stale_after", "2000-01-01"), ("stale", "stale", True)):
                if flag in case:
                    next(i for i in catalog["items"] if i["id"] == case[flag])["governance"][key] = value
            with self.subTest(case=case):
                self.assertEqual(guidance.evaluate_guidance(catalog, case["audience"], case["answers"]), ts_result)
        print(f"Actual candidate: {len(cases)} complete TS/Python evaluation results identical")

    def test_actual_guidance_schema_validation_matches_ts(self):
        cases = [copy.deepcopy(i["guidance"]) for i in self.catalog["items"] if "guidance" in i]
        career = next(g for g in cases if g["kind"] == "career")
        mutations = [("category", "invalid"), ("priority", "invalid")]
        for key, value in mutations:
            bad = copy.deepcopy(career); bad["direction"][key] = value; cases.append(bad)
        for field, value in (("href", "javascript:alert(1)"), ("href", "//evil"), ("kind", "invalid")):
            bad = copy.deepcopy(career); bad["direction"]["resources"][0][field] = value; cases.append(bad)
        bad = copy.deepcopy(career); del bad["direction"]["resources"][0]["kind"]; cases.append(bad)
        for key, value in (("kind", "unknown"), ("status", "unknown"), ("sourceUrl", "file:///secret")):
            bad = copy.deepcopy(career); bad["direction"]["signals"][0][key] = value; cases.append(bad)
        bad = copy.deepcopy(career); bad["journey"]["resources"][0]["kind"] = "tool"; cases.append(bad)
        for url in ("javascript:evil", "//evil", "/safe", "http://safe", "https://safe"):
            platform = copy.deepcopy(next(g for g in cases if g["kind"] == "platform"))
            platform["sources"][0]["url"] = url; cases.append(platform)
        for conditions in ({}, {"goal": ["unknown"]}, {"goal": ["skip"]}, {"goal": []}, {"bad": ["learn"]}):
            value = fixture(); value["recommendations"][0]["when"] = conditions; cases.append(value)
        value = fixture(); value["questions"][0]["when"] = {}; cases.append(value)
        value = fixture(); value["questions"] = []; value["recommendations"] = []; cases.append(value)
        value = fixture(); value["questions"][0]["prompt"] = " "; cases.append(value)
        value = fixture(); value["private"] = "hidden"; cases.append(value)
        for kind in ([], {}, None, "unknown"):
            value = fixture(); value["kind"] = kind; cases.append(value)
        expected = self.ts("validate", cases)
        self.assertEqual(len(expected), len(cases))
        for index, (value, accepted) in enumerate(zip(cases, expected)):
            try:
                guidance.validate_guidance(value)
                actual = True
            except ValueError:
                actual = False
            with self.subTest(index=index):
                self.assertEqual(actual, accepted)
        print(f"Actual candidate: {len(cases)} guidance schema acceptance results identical")


if __name__ == "__main__":
    unittest.main()
