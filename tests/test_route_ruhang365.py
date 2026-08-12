from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "ruhang365-router"
ROUTER_SCRIPT = SKILL_DIR / "scripts" / "route_ruhang365.py"


def load_router_module():
    spec = importlib.util.spec_from_file_location("route_ruhang365", ROUTER_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load route_ruhang365.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


router = load_router_module()


def arguments(**overrides):
    values = {
        "query": "我不知道 AI 能为自己的小店做什么",
        "intent": "auto",
        "limit": 3,
        "base_url": "https://rhzl.ruhang365.cn",
        "timeout": 12.0,
        "format": "json",
        "offline": True,
        "identity": None,
        "goal": None,
        "experience": None,
        "constraint": [],
        "deliverable": None,
        "catalog": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class IntentTests(unittest.TestCase):
    def test_infers_discovery_before_generic_tool_words(self):
        self.assertEqual(
            router.infer_intent("我不知道 AI 工具能为自己的小店做什么"),
            "discover",
        )

    def test_infers_writing_visual_tool_and_knowledge(self):
        cases = {
            "把这篇公众号文章改得更自然": "writing",
            "给文章做一张中文信息图": "visual",
            "帮我比较几个 AI 工具": "tool",
            "找几份适合新手的学习资料": "knowledge",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(router.infer_intent(query), expected)

    def test_discovers_local_business_scenarios_without_remote_data(self):
        scenarios = router.discovery_scenarios(
            "我开一家本地咖啡店，不知道 AI 能帮我做什么"
        )

        self.assertEqual(scenarios["profile"], "local-business")
        self.assertEqual(scenarios["recommendedScenarioId"], "weekly-content-kit")
        self.assertEqual(len(scenarios["items"]), 3)
        self.assertEqual(scenarios["items"][0]["nextIntent"], "writing")

    def test_discovers_current_creator_industry_workflow_without_copying_rhzl_content(self):
        scenarios = router.discovery_scenarios(
            "我准备转行做自媒体，先用一小时吃透这个行业"
        )

        self.assertEqual(
            scenarios["recommendedScenarioId"],
            "creator-ip-industry-cognition",
        )
        self.assertEqual(
            scenarios["items"][0]["workflowIds"],
            ["r365.workflow.creator-ip-industry-cognition"],
        )


class RequestContractTests(unittest.TestCase):
    def test_rejects_invalid_query_limit_timeout_and_credentials(self):
        with self.assertRaisesRegex(ValueError, "2 to 240"):
            router.validate_args(arguments(query="x"))
        with self.assertRaisesRegex(ValueError, "between 1 and 5"):
            router.validate_args(arguments(limit=6))
        with self.assertRaisesRegex(ValueError, "at most 60"):
            router.validate_args(arguments(timeout=61))
        with self.assertRaisesRegex(ValueError, "must not embed credentials"):
            router.validate_args(arguments(base_url="https://user:secret@example.com"))
        with self.assertRaisesRegex(ValueError, "query or fragment"):
            router.validate_args(arguments(base_url="https://example.com?token=secret"))
        with self.assertRaisesRegex(ValueError, "constraint may be repeated"):
            router.validate_args(arguments(constraint=["x"] * 11))
        with self.assertRaisesRegex(ValueError, "identity must contain"):
            router.validate_args(arguments(identity=" "))

    def test_build_requests_contains_only_public_search_parameters(self):
        requests = router.build_requests(
            "https://rhzl.ruhang365.cn",
            "公众号封面",
            "visual",
            3,
        )

        self.assertEqual(set(requests), {"knowledge", "prompts"})
        joined = "\n".join(requests.values()).lower()
        self.assertIn("q=", requests["knowledge"])
        self.assertIn("assettype=image_prompt", requests["prompts"].lower())
        self.assertNotIn("token", joined)
        self.assertNotIn("apikey", joined)
        self.assertNotIn("authorization", joined)


class ProjectionTests(unittest.TestCase):
    def test_knowledge_projection_drops_full_content_and_unknown_fields(self):
        payload = {
            "items": [
                {
                    "id": "knowledge-1",
                    "title": "AI 场景",
                    "description": "三个可执行场景",
                    "content": "full private-looking body",
                    "internal_note": "do not return",
                }
            ]
        }

        result = router.project_knowledge(payload, 3)

        self.assertEqual(result[0]["title"], "AI 场景")
        self.assertNotIn("content", result[0])
        self.assertNotIn("internal_note", result[0])

    def test_skill_projection_drops_content_creator_and_price(self):
        payload = {
            "skills": [
                {
                    "id": "skill-1",
                    "slug": "writing-helper",
                    "title": "写作助手",
                    "content": "full skill body",
                    "creator_id": "internal-user-id",
                    "price": 999,
                }
            ]
        }

        result = router.project_skills(payload, 3)

        self.assertEqual(result[0]["slug"], "writing-helper")
        self.assertNotIn("content", result[0])
        self.assertNotIn("creator_id", result[0])
        self.assertNotIn("price", result[0])

    def test_prompt_projection_keeps_full_prompt_and_strips_reference_only(self):
        payload = {
            "results": [
                {
                    "id": "full-1",
                    "title": "Full",
                    "rights": {"status": "full", "license": "CC0"},
                    "prompt": "allowed prompt",
                },
                {
                    "id": "reference-1",
                    "title": "Reference",
                    "rights": {"status": "reference_only", "license": "unknown"},
                    "prompt": "must be removed",
                },
                "invalid result",
            ]
        }

        result = router.project_prompts(payload, 3)

        self.assertEqual(result[0]["prompt"], "allowed prompt")
        self.assertNotIn("prompt", result[1])
        self.assertEqual(len(result), 2)

    def test_invalid_service_contract_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "knowledge service"):
            router.project_knowledge({"data": []}, 3)
        with self.assertRaisesRegex(ValueError, "skill service"):
            router.project_skills({"items": []}, 3)
        with self.assertRaisesRegex(ValueError, "prompt service"):
            router.project_prompts({"items": []}, 3)

    def test_relevance_filter_removes_popular_but_unrelated_results(self):
        items = [
            {
                "title": "ChatGPT",
                "description": "通用 AI 助手",
                "tags": ["AI 助手"],
            },
            {
                "title": "咖啡店一周内容包",
                "description": "门店获客内容",
                "tags": ["咖啡", "门店"],
            },
        ]

        result = router.filter_relevant(items, "我开一家本地咖啡店")

        self.assertEqual([item["title"] for item in result], ["咖啡店一周内容包"])

    def test_relevance_filter_keeps_matching_visual_prompt(self):
        items = [
            {
                "title": "Chinese poster",
                "tags": ["公众号封面", "中文排版"],
            }
        ]

        result = router.filter_relevant(items, "给文章制作公众号封面")

        self.assertEqual(len(result), 1)


class RoutingTests(unittest.TestCase):
    def test_offline_route_is_useful_and_performs_no_remote_or_write_action(self):
        result = router.route_task(arguments())

        self.assertEqual(result["route"]["intent"], "discover")
        self.assertEqual(result["route"]["capabilities"], ["knowledge", "skills"])
        self.assertEqual(result["route"]["scenarios"]["profile"], "local-business")
        self.assertEqual(len(result["route"]["scenarios"]["items"]), 3)
        self.assertEqual(result["sources"]["knowledge"]["status"], "offline")
        self.assertFalse(result["execution"]["remoteModelCalled"])
        self.assertFalse(result["execution"]["writePerformed"])
        self.assertFalse(result["execution"]["credentialsAccepted"])
        self.assertEqual(result["warnings"], [])

    def test_writing_route_recommends_public_specialist(self):
        result = router.route_task(
            arguments(query="把这篇公众号文章改得更自然", intent="writing")
        )

        specialist = result["route"]["specialists"][0]
        self.assertEqual(specialist["skill"], "ai-writing-humanizer")
        self.assertIn("github.com/ruhang365/", specialist["repository"])

    def test_retrieval_failure_becomes_structured_warning(self):
        online_args = arguments(offline=False, intent="knowledge")
        with mock.patch.object(
            router,
            "retrieve_source",
            return_value={"status": "unavailable", "items": []},
        ):
            result = router.route_task(online_args)

        self.assertEqual(result["sources"]["knowledge"]["status"], "unavailable")
        self.assertEqual(len(result["warnings"]), 1)

    def test_offline_cli_returns_valid_json(self):
        process = subprocess.run(
            [
                sys.executable,
                str(ROUTER_SCRIPT),
                "--query",
                "我不知道 AI 能做什么",
                "--offline",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        self.assertEqual(payload["schemaVersion"], "0.2")
        self.assertEqual(payload["route"]["intent"], "discover")

    def test_offline_cli_exposes_content_driven_cross_carrier_matches(self):
        process = subprocess.run(
            [
                sys.executable,
                str(ROUTER_SCRIPT),
                "--query",
                "为咖啡店做一周获客内容",
                "--identity",
                "local-business",
                "--goal",
                "content-growth",
                "--experience",
                "beginner",
                "--constraint",
                "free-only",
                "--deliverable",
                "weekly-content-kit",
                "--offline",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        matches = payload["route"]["communityMatches"]
        self.assertEqual(matches["catalogVersion"], "1.0.0")
        self.assertEqual(
            matches["scenarios"][0]["id"],
            "r365.scenario.weekly-content-kit",
        )

    def test_markdown_cli_exposes_stable_catalog_ids(self):
        process = subprocess.run(
            [
                sys.executable,
                str(ROUTER_SCRIPT),
                "--query",
                "为咖啡店做一周获客内容",
                "--identity",
                "local-business",
                "--deliverable",
                "weekly-content-kit",
                "--format",
                "markdown",
                "--offline",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("r365.scenario.weekly-content-kit", process.stdout)
        self.assertIn("r365.workflow.weekly-content-kit", process.stdout)


class RepositoryContractTests(unittest.TestCase):
    def test_skill_metadata_and_open_core_boundaries_are_explicit(self):
        skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        security_text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")

        self.assertTrue(skill_text.startswith("---\nname: ruhang365-router\n"))
        self.assertIn("不接收、读取、存储或传输会员 Token", skill_text)
        self.assertIn("公开核心永久可执行", readme_text)
        self.assertIn("过滤与查询没有明显匹配", readme_text)
        self.assertIn("字段白名单", security_text)

    def test_installer_is_non_overwriting(self):
        installer = REPO_ROOT / "scripts" / "install.sh"
        with tempfile.TemporaryDirectory() as temporary_directory:
            environment = os.environ.copy()
            environment["CODEX_HOME"] = str(Path(temporary_directory) / "codex")

            first = subprocess.run(
                ["bash", str(installer)],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
            second = subprocess.run(
                ["bash", str(installer)],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            installed = (
                Path(environment["CODEX_HOME"])
                / "skills"
                / "ruhang365-router"
                / "SKILL.md"
            )
            installed_router = installed.parent / "scripts" / "route_ruhang365.py"
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue(installed.is_file())
            with tempfile.TemporaryDirectory() as unrelated_directory:
                routed = subprocess.run(
                    [
                        sys.executable,
                        str(installed_router),
                        "--query",
                        "为咖啡店做一周获客内容",
                        "--identity",
                        "local-business",
                        "--deliverable",
                        "weekly-content-kit",
                        "--offline",
                    ],
                    cwd=unrelated_directory,
                    check=False,
                    capture_output=True,
                    text=True,
                )
            self.assertEqual(routed.returncode, 0, routed.stderr)
            self.assertEqual(
                json.loads(routed.stdout)["route"]["communityMatches"]["scenarios"][0]["id"],
                "r365.scenario.weekly-content-kit",
            )
            self.assertEqual(second.returncode, 3)
            self.assertIn("destination already exists", second.stderr)


if __name__ == "__main__":
    unittest.main()
