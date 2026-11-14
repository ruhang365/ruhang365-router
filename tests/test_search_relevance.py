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

    def test_long_questions_rank_by_topic_not_cross_word_fragments(self):
        # Request wording ("推荐几个", "有什么", "从哪开始") is not a topic.
        top =[item["title"] for item in self.search("推荐几个写周报的提示词")[:2]]
        self.assertTrue(all("周报" in title for title in top), top)
        self.assertIn("运营", self.search("我是运营，老板让我用 AI 提效，有什么能直接用的方法")[0]["title"])
        scenarios = matcher.match_catalog(self.catalog, {"query": "我是做行政的，想转行做 AI 相关工作，从哪开始"})["scenarios"]
        self.assertEqual(scenarios[0]["id"], "r365.scenario.guide-career-change")

    def test_function_character_fragments_are_not_query_terms(self):
        frequency = {"几个": 3, "个写": 2, "写周": 2, "周报": 5, "报的": 4, "的提": 9, "的提示": 9, "提示": 80, "提示词": 60}
        terms = {term for _, options, _, _ in matcher._query_model("几个写周报的提示词", frequency, 11000) for term in options}
        self.assertTrue({"周报", "提示", "提示词"} <= terms, terms)
        self.assertFalse({"几个", "报的", "的提", "的提示"} & terms, terms)
        # A fragment seen in a single catalog entry is not trusted as a topic word.
        self.assertEqual(matcher._query_model("写周", {"写周": 1}, 11000), [])
        self.assertTrue(matcher._query_model("写周", {"写周": 1}, 20))

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
