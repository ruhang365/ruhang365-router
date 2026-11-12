from __future__ import annotations

import re
import unittest

from test_community_catalog import load_matcher

matcher = load_matcher()


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value.casefold())


class FreeTextRelevanceTests(unittest.TestCase):
    """Free-text search over the bundled full catalog ranks by topic, not by question wording."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = matcher.load_catalog(matcher.FULL_CATALOG_PATH)

    def search(self, query: str, limit: int = 5) -> list[dict]:
        return matcher.match_catalog(self.catalog, {"query": query}, limit_per_type=limit)["resources"]

    def test_question_wording_is_not_a_search_term(self):
        self.assertEqual(matcher._tokens("MCP 是什么"), {"mcp"})
        self.assertEqual(matcher._tokens("如何写简历"), {"写简", "简历", "写简历"})
        titles = [item["title"] for item in self.search("MCP 是什么")]
        self.assertTrue(titles)
        self.assertTrue(all("mcp" in title.casefold() for title in titles), titles)
        self.assertTrue(all("简历" in item["title"] for item in self.search("如何写简历")))

    def test_rare_terms_outweigh_common_ones(self):
        titles = [item["title"] for item in self.search("AI 绘画 Midjourney 提示词")[:3]]
        self.assertIn("Midjourney", titles)

    def test_matched_terms_are_readable_query_phrases(self):
        top = self.search("产品经理面试")[0]
        self.assertIn("产品经理", top["matchedTerms"])
        self.assertNotIn("品经理", top["matchedTerms"])
        self.assertEqual(self.search("怎么用 Claude Code 做代码审查")[0]["matchedTerms"], ["code", "代码审查"])

    def test_results_do_not_repeat_titles(self):
        for query in ("什么是 AI", "选品技巧", "AI Writing Humanizer"):
            titles = [compact(item["title"]) for item in self.search(query, limit=10)]
            self.assertEqual(len(titles), len(set(titles)), query)

    def test_weak_partial_matches_are_dropped(self):
        for item in self.search("跨境电商亚马逊选品", limit=10):
            self.assertTrue({"跨境电商", "选品", "跨境电商亚马逊选品"} & set(item["matchedTerms"])
                            or any("亚马逊" in term for term in item["matchedTerms"]), item)
        self.assertEqual(self.search("是什么"), [])


if __name__ == "__main__":
    unittest.main()
