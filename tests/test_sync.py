import os
import tempfile
import unittest

from tests import weread

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestParseVaultFrontmatter(unittest.TestCase):
    def test_parse_valid_frontmatter(self):
        rec = weread.parse_vault_frontmatter(
            os.path.join(FIXTURE_DIR, "sample_book.md")
        )
        self.assertEqual(rec["bookId"], "44026191")
        self.assertEqual(rec["title"], "纳瓦尔宝典")
        self.assertEqual(rec["highlights"], 594)
        self.assertEqual(rec["thoughts"], 159)
        self.assertEqual(rec["type"], "读书笔记")

    def test_parse_missing_bookId_returns_none(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write('---\ntitle: "无 bookId"\ntype: 读书笔记\n---\n正文\n')
            path = f.name
        try:
            self.assertIsNone(weread.parse_vault_frontmatter(path))
        finally:
            os.unlink(path)

    def test_parse_no_frontmatter_returns_none(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("# 没有 frontmatter\n正文\n")
            path = f.name
        try:
            self.assertIsNone(weread.parse_vault_frontmatter(path))
        finally:
            os.unlink(path)

    def test_parse_quoted_values_stripped(self):
        rec = weread.parse_vault_frontmatter(
            os.path.join(FIXTURE_DIR, "sample_book.md")
        )
        # title 在 fixture 里带引号，解析后应该没引号
        self.assertNotIn('"', rec["title"])


class TestScanVault(unittest.TestCase):
    def setUp(self):
        self.vault = os.path.join(FIXTURE_DIR, "vault_sample")

    def test_scan_returns_book_records(self):
        result = weread.scan_vault(self.vault)
        self.assertIn("44026191", result)
        rec = result["44026191"]
        self.assertEqual(rec["title"], "纳瓦尔宝典")
        self.assertEqual(rec["highlights"], 594)
        self.assertTrue(rec["path"].endswith("纳瓦尔宝典.md"))

    def test_scan_skips_underscore_index(self):
        result = weread.scan_vault(self.vault)
        for rec in result.values():
            self.assertNotIn("_索引", rec["path"])

    def test_scan_skips_non_book_type(self):
        # 外部链接.md type=资料 + bookId=should_be_ignored，应被过滤
        result = weread.scan_vault(self.vault)
        self.assertNotIn("should_be_ignored", result)

    def test_scan_missing_dir_returns_empty(self):
        result = weread.scan_vault("/nonexistent/path/xyz")
        self.assertEqual(result, {})


def _api_book(bid, title, author, progress, note_count, review_count):
    """构造 list_notebooks 单条记录的 fixture。"""
    return {
        "bookId": bid,
        "book": {"title": title, "author": author},
        "readingProgress": progress,
        "noteCount": note_count,
        "reviewCount": review_count,
    }


class TestDiffVaultVsApi(unittest.TestCase):
    def test_no_drift_when_perfectly_aligned(self):
        vault = {
            "B1": {"path": "/v/B1.md", "title": "T1",
                   "highlights": 100, "thoughts": 10},
        }
        api = [_api_book("B1", "T1", "A1", 95, 100, 10)]
        plan = weread.diff_vault_vs_api(vault, api, include_reading=False)
        self.assertEqual(plan["missing"], [])
        self.assertEqual(plan["stale"], [])
        self.assertEqual(plan["orphan"], [])

    def test_missing_when_finished_book_not_in_vault(self):
        vault = {}
        api = [_api_book("B2", "T2", "A2", 100, 50, 5)]
        plan = weread.diff_vault_vs_api(vault, api, include_reading=False)
        self.assertEqual(len(plan["missing"]), 1)
        m = plan["missing"][0]
        self.assertEqual(m["bookId"], "B2")
        self.assertEqual(m["title"], "T2")
        self.assertEqual(m["author"], "A2")
        self.assertEqual(m["noteCount"], 50)
        self.assertEqual(m["reviewCount"], 5)

    def test_unfinished_excluded_when_not_include_reading(self):
        vault = {}
        api = [_api_book("B3", "T3", "A3", 50, 10, 1)]  # 进度 50
        plan = weread.diff_vault_vs_api(vault, api, include_reading=False)
        self.assertEqual(plan["missing"], [])

    def test_unfinished_included_when_flag(self):
        vault = {}
        api = [_api_book("B3", "T3", "A3", 50, 10, 1)]
        plan = weread.diff_vault_vs_api(vault, api, include_reading=True)
        self.assertEqual(len(plan["missing"]), 1)

    def test_stale_when_highlights_differ(self):
        vault = {
            "B4": {"path": "/v/B4.md", "title": "T4",
                   "highlights": 100, "thoughts": 10},
        }
        api = [_api_book("B4", "T4", "A4", 100, 120, 10)]  # noteCount 100→120
        plan = weread.diff_vault_vs_api(vault, api, include_reading=False)
        self.assertEqual(len(plan["stale"]), 1)
        s = plan["stale"][0]
        self.assertEqual(s["bookId"], "B4")
        self.assertEqual(s["author"], "A4")
        self.assertEqual(s["vault_highlights"], 100)
        self.assertEqual(s["vault_thoughts"], 10)
        self.assertEqual(s["api_noteCount"], 120)
        self.assertEqual(s["api_reviewCount"], 10)

    def test_stale_when_thoughts_differ(self):
        vault = {
            "B5": {"path": "/v/B5.md", "title": "T5",
                   "highlights": 100, "thoughts": 10},
        }
        api = [_api_book("B5", "T5", "A5", 100, 100, 15)]
        plan = weread.diff_vault_vs_api(vault, api, include_reading=False)
        self.assertEqual(len(plan["stale"]), 1)

    def test_orphan_when_vault_has_book_api_missing(self):
        vault = {
            "B6": {"path": "/v/B6.md", "title": "T6",
                   "highlights": 10, "thoughts": 1},
        }
        api = []
        plan = weread.diff_vault_vs_api(vault, api, include_reading=False)
        self.assertEqual(len(plan["orphan"]), 1)
        o = plan["orphan"][0]
        self.assertEqual(o["bookId"], "B6")
        self.assertEqual(o["title"], "T6")

    def test_combined_three_categories(self):
        vault = {
            "B_aligned": {"path": "/v/a.md", "title": "TA",
                          "highlights": 50, "thoughts": 5},
            "B_stale": {"path": "/v/s.md", "title": "TS",
                        "highlights": 30, "thoughts": 3},
            "B_orphan": {"path": "/v/o.md", "title": "TO",
                         "highlights": 10, "thoughts": 1},
        }
        api = [
            _api_book("B_aligned", "TA", "A", 100, 50, 5),
            _api_book("B_stale", "TS", "A", 100, 40, 3),
            _api_book("B_missing", "TM", "A", 100, 20, 2),
        ]
        plan = weread.diff_vault_vs_api(vault, api, include_reading=False)
        self.assertEqual([m["bookId"] for m in plan["missing"]], ["B_missing"])
        self.assertEqual([s["bookId"] for s in plan["stale"]], ["B_stale"])
        self.assertEqual([o["bookId"] for o in plan["orphan"]], ["B_orphan"])


if __name__ == "__main__":
    unittest.main()
