from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stdout
import unittest
from unittest import mock

from test_route_ruhang365 import router, arguments
from test_community_catalog import load_matcher, valid_assets, common_asset

matcher = load_matcher()


class ResourceNavigationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = matcher.load_catalog(matcher.FULL_CATALOG_PATH)

    def test_release_and_full_workflow_prompt_navigation_remain_immutable(self):
        self.assertEqual(self.catalog["catalogVersion"], "1.1.0")
        self.assertEqual(len(self.catalog["items"]), 11658)
        self.assertEqual(self.catalog["contentDigest"], "f68e6602bb00f8c39302add001623ac090666b05e4f27607597c4768832571cb")
        before = copy.deepcopy(self.catalog)
        item = next(x for x in self.catalog["items"] if x["id"] == "r365.workflow.customer-feedback-review")
        detail = matcher.catalog_read_projection(self.catalog, item)
        self.assertEqual(detail["structured"]["nodes"], item["nodes"])
        prompt = next(x for x in detail["related"] if x["type"] == "prompt")
        self.assertIn("{{feedback_items}}", prompt["template"])
        self.assertEqual(prompt["variables"], ["feedback_items", "sample_scope"])
        self.assertEqual(before, self.catalog)

    def test_full_structure_never_leaks_restricted_or_stale_content(self):
        for mutation in ({"access": "member"}, {"access": "registration"}, {"access": "reference_only"},
                         {"rights": "reference_only"}, {"stale": True}, {"status": "retired"}):
            for kind in ("workflow", "prompt"):
                item = common_asset(kind, "test")
                item.update(nodes=[{"action": "secret", "internal": "secret"}], template="secret", variables=["secret"])
                for key, value in mutation.items():
                    if key == "rights":
                        item["governance"]["rights"]["status"] = value
                    elif key == "stale":
                        item["governance"][key] = value
                    else:
                        item[key] = value
                self.assertEqual(matcher.public_structured(item), {})
                projected = matcher._project_match(item, 1, [])
                self.assertFalse(projected.get("nodes") or projected.get("template") or projected.get("variables"))

    def test_structured_whitelist_excludes_internal_fields(self):
        item = valid_assets()[1]
        item["nodes"][0]["private"] = "secret"
        item["private"] = "secret"
        structured = matcher.public_structured(item)
        self.assertNotIn("private", structured)
        self.assertNotIn("private", structured["nodes"][0])
        self.assertIn("action", structured["nodes"][0])

    def test_guidance_query_uses_catalog_labels_codes_and_free_query_only(self):
        profile = router.guidance_matching_profile(self.catalog, "work-growth",
            {"purpose": "improve", "role": "product"}, "用户访谈")
        self.assertEqual(profile["query"], "improve 比较一个现有工作怎么改进 product 产品经理 / 产品运营 用户访谈")
        self.assertEqual(profile["goal"], "")
        for value in ("unknown", "skip", "invalid"):
            profile = router.guidance_matching_profile(self.catalog, "work-growth",
                {"purpose": value, "role": "product"})
            self.assertEqual(profile["query"], "")
        result = router.route_guidance(arguments(query="用户访谈", guide="work-growth",
            catalog=matcher.FULL_CATALOG_PATH, answer=["purpose=improve", "role=product"]))
        self.assertEqual(result["communityMatches"]["profile"]["query"],
                         "improve 比较一个现有工作怎么改进 product 产品经理 / 产品运营 用户访谈".casefold())
        for group in ("scenarios", "workflows", "resources", "prompts"):
            for item in result["communityMatches"][group]:
                self.assertEqual(item["matchReasons"], ["terms"])
                self.assertTrue(item["matchedTerms"])
                self.assertNotIn("guidance", item)

    def test_generic_option_words_do_not_establish_creator_ip_relevance(self):
        matches = matcher.match_catalog(self.catalog, {"query": "比较一个现有工作怎么改进"}, exclude_guidance=True)
        self.assertNotIn("r365.scenario.creator-ip-industry-cognition", [x["id"] for x in matches["scenarios"]])
        self.assertNotIn("一个", matcher._tokens("比较一个现有工作怎么改进"))
        self.assertIn("用户", matcher._tokens("用户访谈"))
        self.assertIn("运营", matcher._tokens("产品运营"))

    def test_offline_read_exposes_complete_structured_in_json_and_markdown(self):
        with mock.patch.object(router, "fetch_asset_detail") as fetch:
            result = router.route_guidance(arguments(query="", catalog=router.DEFAULT_CATALOG_PATH,
                read="r365.workflow.customer-feedback-review"))
        fetch.assert_not_called()
        self.assertEqual(len(result["detail"]["structured"]["nodes"]), 3)
        output = io.StringIO()
        with redirect_stdout(output):
            router.print_guidance_markdown(result)
        self.assertIn("classify-feedback", output.getvalue())
        self.assertIn("prompt_ids", output.getvalue())
        self.assertIn("r365.prompt.customer-feedback-review", output.getvalue())

    def test_online_structured_read_and_denied_read_do_not_download_related_items(self):
        item = next(x for x in self.catalog["items"] if x["type"] == "workflow")
        with mock.patch.object(router, "fetch_asset_detail", return_value={"access": "public", "body": "body",
                "structured": {"nodes": [{"action": "not in catalog"}], "private": "secret"}}) as fetch:
            detail = router.read_public_asset(arguments(offline=False), self.catalog, item, [])
        self.assertEqual(detail["body"], "body")
        self.assertEqual(detail["structured"]["nodes"], item["nodes"])
        self.assertNotIn("private", detail["structured"])
        self.assertEqual(fetch.call_count, 1)
        item = copy.deepcopy(item)
        item["access"] = "member"
        with mock.patch.object(router, "fetch_asset_detail") as fetch:
            detail = router.read_public_asset(arguments(offline=False), self.catalog, item, [])
        fetch.assert_not_called()
        self.assertNotIn("body", detail)
        self.assertEqual(detail["structured"], {})

    def test_remote_gated_response_never_adds_body_to_public_snapshot(self):
        item = next(x for x in self.catalog["items"] if x["type"] == "workflow")
        with mock.patch.object(router, "fetch_asset_detail", return_value={"access": "public", "gated": True, "body": "blocked body"}):
            detail = router.read_public_asset(arguments(offline=False), self.catalog, item, [])
        self.assertNotIn("body", detail)
        self.assertEqual(detail["structured"]["nodes"], item["nodes"])

    def test_original_detail_identity_version_hash_validation_remains_fail_closed(self):
        item = next(x for x in self.catalog["items"] if x["type"] == "workflow")
        for key in ("id", "version", "contentHash"):
            payload = {"id": item["id"], "version": item["version"], "contentHash": item["content_hash"], "body": "body"}
            payload[key] = "wrong"
            response = io.BytesIO(json.dumps(payload).encode())
            with self.assertRaises(ValueError):
                matcher.fetch_asset_detail("https://rhzl.ruhang365.cn", item,
                                           opener=lambda *args, **kwargs: response)


if __name__ == "__main__":
    unittest.main()
