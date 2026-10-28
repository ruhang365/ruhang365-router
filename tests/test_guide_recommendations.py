from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

from test_route_ruhang365 import router, arguments, ROUTER_SCRIPT
from guide_recommendations import (CONDITION_CHOICES, parse_conditions,
    refine_recommendations, condition_notes, recommended_links, search_guide_resources,
    allowed_guide_items, linked_guide_matches)


class GuideConditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = router.load_catalog(router.FULL_CATALOG_PATH)
        cls.items = cls.catalog["items"]
        cls.allowed = {item["id"] for item in cls.items}

    def run_guide(self, audience="work-growth", answers=None, **overrides):
        values = {"query": "", "guide": audience, "catalog": router.FULL_CATALOG_PATH,
                  "answer": answers or ["purpose=improve", "role=product"], **overrides}
        return router.route_guidance(arguments(**values))

    def test_all_web_condition_values_and_unknown_are_exact(self):
        self.assertEqual(parse_conditions([]), {"experience": "", "coding": "", "weeklyHours": "", "budget": ""})
        for key, values in CONDITION_CHOICES.items():
            for value in values:
                self.assertEqual(parse_conditions([f"{key}={value}"])[key], value)
        for values in (["unknown=true"], ["coding=expert"], ["weeklyHours=40"], ["budget=free"],
                       ["experience=unknown"], ["experience=product", "experience=operations"], ["coding"]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                parse_conditions(values)

    def test_explicit_work_growth_prioritizes_upgrade_without_inventing_conditions(self):
        result = self.run_guide()
        self.assertEqual(result["guidance"]["recommendations"][0]["resourceIds"], ["r365.resource.career-product-manager-ai-upgrade"])
        self.assertEqual(result["conditions"], parse_conditions([]))
        self.assertTrue(all(not value for value in result["conditionNotes"].values()))
        self.assertEqual(result["execution"], {"mode": "community", "remoteModelCalled": False,
                                             "writePerformed": False, "credentialsAccepted": False})

    def test_no_code_time_and_budget_are_reading_notes_not_eligibility(self):
        result = self.run_guide(condition=["experience=product", "coding=none", "weeklyHours=4", "budget=0"])
        notes = result["conditionNotes"]["r365.resource.career-product-manager-ai-upgrade"]
        self.assertTrue(any("可迁移的经验" in value for value in notes))
        self.assertTrue(any("不会编程" in value for value in notes))
        self.assertTrue(any("每周约 4 小时" in value and "资料没有阶段耗时" in value for value in notes))
        self.assertTrue(any("不能据此确认预算是否足够" in value for value in notes))
        with mock.patch.object(router, "resolve_catalog", return_value={"catalog": self.catalog, "source": "online", "warning": None}) as resolve:
            router.route_guidance(arguments(query="私人条件", guide="work-growth", answer=["purpose=improve", "role=product"],
                catalog=router.FULL_CATALOG_PATH, condition=["coding=none"], offline=False))
        resolve.assert_called_once_with("https://rhzl.ruhang365.cn", snapshot_path=router.FULL_CATALOG_PATH, timeout=12.0, offline=False)

    def test_newcomer_code_boundary_and_unknown_route_remain_honest(self):
        result = self.run_guide("career-change", ["route=new-role", "new-role-focus=engineering"],
                                condition=["experience=new", "coding=none"])
        notes = result["conditionNotes"]["r365.resource.career-ai-agent-development"]
        self.assertTrue(any("先核对经验缺口" in value for value in notes))
        self.assertTrue(any("不把这条路径当成可以立即交付的工作" in value for value in notes))
        unknown = self.run_guide("career-change", ["route=new-role", "new-role-focus=unknown"], condition=["experience=new"])
        self.assertEqual(unknown["guidance"]["status"], "no_match")
        self.assertEqual(unknown["guidance"]["recommendations"], [])
        self.assertEqual(unknown["resources"], [])

    def test_no_label_noise_and_strict_query_coverage(self):
        result = self.run_guide(query="")
        matches = result["communityMatches"]
        self.assertEqual(matches["profile"]["query"], "")
        ids = [entry["id"] for group in ("scenarios", "workflows", "resources", "prompts") for entry in matches[group]]
        self.assertNotIn("r365.scenario.weekly-content-kit", ids)
        self.assertNotIn("r365.workflow.customer-feedback-review", ids)
        self.assertTrue(all(entry["matchReasons"] == ["linked_id"] for group in ("scenarios", "workflows", "resources", "prompts") for entry in matches[group]))
        self.assertEqual(search_guide_resources(self.items, "量子火星猫咖不存在岗位"), [])
        feedback = search_guide_resources(self.items, "顾客反馈")
        self.assertTrue(any(entry["id"] == "r365.workflow.customer-feedback-review" for entry in feedback))

    def test_compare_group_keeps_three_directions_equal(self):
        ids = ["r365.resource.career-ai-product", "r365.resource.career-ai-agent-development", "r365.resource.career-ai-solution-delivery-fde"]
        recommendation = {"id": "compare", "title": "先比较", "when": {"focus": ["compare"]},
                          "resourceIds": ids, "reason": "比较差异", "cautions": []}
        result = refine_recommendations([recommendation], self.items, self.allowed,
                                       parse_conditions(["experience=new", "coding=none"]))
        self.assertEqual(result, [recommendation])
        self.assertEqual(refine_recommendations([recommendation], self.items, self.allowed,
                         parse_conditions(["experience=operations", "coding=none"])), [recommendation])

    def test_operations_background_never_infers_cross_border_or_overrides_chosen_role(self):
        result = self.run_guide("career-change", ["route=new-role", "new-role-focus=engineering"],
                               condition=["experience=operations", "coding=none"])
        ids = [ref for entry in result["guidance"]["recommendations"] for ref in entry["resourceIds"]]
        self.assertEqual(ids[0], "r365.resource.career-ai-agent-development")
        self.assertIn("r365.resource.career-operations-marketing-ai-upgrade", ids)
        self.assertNotIn("r365.resource.career-cross-border-ecommerce-ai-upgrade", ids)

    def test_budget_exclusion_and_all_blocked_fail_closed(self):
        item = copy.deepcopy(next(entry for entry in self.items if entry["id"] == "r365.resource.career-ai-product"))
        item["applicability"]["excluded_constraints"] = ["free-only"]
        allowed = allowed_guide_items([item], ["free-only"])
        self.assertEqual(allowed, [])
        rec = {"id": "test", "title": "test", "when": {"goal": ["test"]},
               "resourceIds": [item["id"]], "reason": "source", "cautions": []}
        self.assertEqual(refine_recommendations([rec], [item], set(), parse_conditions(["budget=0"])), [])

    def test_linked_nodes_and_member_rights_do_not_leak(self):
        career = copy.deepcopy(next(entry for entry in self.items if entry["id"] == "r365.resource.career-ai-product"))
        workflow = copy.deepcopy(next(entry for entry in self.items if entry["id"] == "r365.workflow.customer-feedback-review"))
        prompt = copy.deepcopy(next(entry for entry in self.items if entry["id"] == "r365.prompt.customer-feedback-review"))
        career["workflow_ids"] = [workflow["id"]]
        catalog = {**self.catalog, "items": [career, workflow, prompt]}
        matches = linked_guide_matches(catalog, [career["id"]], [], catalog["items"], "", 5)
        self.assertEqual(matches["workflows"][0]["nodes"], workflow["nodes"])
        self.assertEqual(matches["prompts"][0]["template"], prompt["template"])
        workflow["access"] = "member"
        matches = linked_guide_matches(catalog, [career["id"]], [], catalog["items"], "", 5)
        self.assertEqual(matches["workflows"][0]["nodes"], [])
        self.assertEqual(matches["prompts"], [])

    def test_markdown_includes_conditions_and_additional_sources(self):
        result = self.run_guide("career-change", ["route=new-role", "new-role-focus=product"], condition=["coding=none"])
        stream = io.StringIO()
        with redirect_stdout(stream):
            router.print_guidance_markdown(result)
        self.assertIn("你的条件", stream.getvalue())
        self.assertIn("zhaopin.jd.com", stream.getvalue())
        self.assertIn("不证明", stream.getvalue())

    def test_direct_workflow_and_prompt_have_no_career_guidance(self):
        for kind in ("workflow", "prompt"):
            result = router.route_guidance(arguments(query="", guide=None, offline=True,
                catalog=router.FULL_CATALOG_PATH, read=f"r365.{kind}.customer-feedback-review"))
            self.assertIsNone(result["resources"][0]["guidance"])
            self.assertEqual(result["conditionNotes"][result["resources"][0]["id"]], [])
            self.assertTrue(result["detail"]["structured"])

    def test_real_cli_rejects_conflicting_conditions_without_network(self):
        run = subprocess.run([sys.executable, str(ROUTER_SCRIPT), "--guide", "work-growth",
            "--offline", "--condition", "coding=none", "--condition", "coding=ready"], text=True, capture_output=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn("only once", run.stderr)


@unittest.skipUnless(os.environ.get("RHZL_WEB_ROOT"), "set RHZL_WEB_ROOT for real Web/Python condition parity")
class ActualWebConditionParityTests(unittest.TestCase):
    def test_all_condition_notes_refinement_and_explicit_links_match_web(self):
        web_root = Path(os.environ["RHZL_WEB_ROOT"])
        catalog = router.load_catalog(os.environ.get("RHZL_CATALOG_PATH") or router.FULL_CATALOG_PATH)
        items = [item for item in catalog["items"] if item.get("guidance", {}).get("kind") in ("career", "platform")]
        allowed_ids = {item["id"] for item in items}
        conditions = [parse_conditions([])]
        for key, values in CONDITION_CHOICES.items():
            conditions.extend(parse_conditions([f"{key}={value}"]) for value in values)
        conditions.extend(parse_conditions([f"experience={experience}", "coding=none", "weeklyHours=4", "budget=0"])
                          for experience in CONDITION_CHOICES["experience"])
        cases = []
        for condition in conditions:
            for audience, answers in (("work-growth", {"purpose": "improve", "role": "product"}),
                                      ("work-growth", {"purpose": "improve", "role": "operations"}),
                                      ("career-change", {"route": "new-role", "new-role-focus": "engineering"}),
                                      ("career-change", {"route": "new-role", "new-role-focus": "compare"})):
                recommendations = router.evaluate_guidance(catalog, audience, answers)["recommendations"]
                cases.append({"conditions": condition, "recommendations": recommendations,
                              "preferUpgrade": audience == "work-growth"})
        script = '''
          import {refineGuideRecommendations,guideConditionNotes,recommendedGuideLinks} from './src/lib/career/guide-recommendations.ts';
          let raw=''; for await(const chunk of process.stdin) raw+=chunk;
          const input=JSON.parse(raw), ids=new Set(input.items.map(i=>i.id));
          const results=input.cases.map(c=>{
            const recommendations=refineGuideRecommendations(c.recommendations,input.items,ids,c.conditions,c.preferUpgrade);
            return {recommendations,notes:input.items.map(i=>guideConditionNotes(i,c.conditions)),
              links:recommendedGuideLinks(input.items,recommendations.flatMap(r=>r.resourceIds))};
          }); console.log(JSON.stringify(results));
        '''
        run = subprocess.run(["node", "--import", "tsx", "--input-type=module", "-e", script], cwd=web_root,
            input=json.dumps({"items": items, "cases": cases}), text=True, capture_output=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        expected = json.loads(run.stdout)
        for case, web in zip(cases, expected):
            recommendations = refine_recommendations(case["recommendations"], items, allowed_ids,
                case["conditions"], case["preferUpgrade"])
            actual = {"recommendations": recommendations,
                      "notes": [condition_notes(item, case["conditions"]) for item in items],
                      "links": recommended_links(items, [ref for entry in recommendations for ref in entry["resourceIds"]])}
            with self.subTest(conditions=case["conditions"], recommendations=case["recommendations"]):
                self.assertEqual(actual, web)
        print(f"Actual Web/Python: {len(cases)} recommendation/condition-note/explicit-link cases identical")


if __name__ == "__main__":
    unittest.main()
