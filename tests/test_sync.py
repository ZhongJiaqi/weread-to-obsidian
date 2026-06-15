import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

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


class TestPrintSyncReport(unittest.TestCase):
    def test_no_drift_message(self):
        plan = {"missing": [], "stale": [], "orphan": []}
        buf = io.StringIO()
        with redirect_stdout(buf):
            weread.print_sync_report(plan, applied=False, vault_count=7)
        out = buf.getvalue()
        self.assertIn("已同步", out)
        self.assertIn("7", out)

    def test_dry_run_lists_missing(self):
        plan = {
            "missing": [{"bookId": "B1", "title": "权力48法则",
                         "author": "张小玲", "noteCount": 1615,
                         "reviewCount": 308}],
            "stale": [],
            "orphan": [],
        }
        buf = io.StringIO()
        with redirect_stdout(buf):
            weread.print_sync_report(plan, applied=False, vault_count=7)
        out = buf.getvalue()
        self.assertIn("缺失", out)
        self.assertIn("权力48法则", out)
        self.assertIn("1615", out)
        self.assertIn("308", out)
        self.assertIn("--apply", out)

    def test_dry_run_lists_stale_with_delta(self):
        plan = {
            "missing": [],
            "stale": [{"bookId": "B2", "title": "纳瓦尔宝典",
                       "author": "埃里克·乔根森",
                       "path": "/v/纳瓦尔宝典.md",
                       "vault_highlights": 594, "vault_thoughts": 159,
                       "api_noteCount": 612, "api_reviewCount": 163}],
            "orphan": [],
        }
        buf = io.StringIO()
        with redirect_stdout(buf):
            weread.print_sync_report(plan, applied=False, vault_count=7)
        out = buf.getvalue()
        self.assertIn("过期", out)
        self.assertIn("纳瓦尔宝典", out)
        self.assertIn("594", out)
        self.assertIn("612", out)

    def test_dry_run_lists_orphan(self):
        plan = {
            "missing": [],
            "stale": [],
            "orphan": [{"bookId": "B3", "title": "已删除的书",
                        "path": "/v/x.md",
                        "highlights": 10, "thoughts": 1}],
        }
        buf = io.StringIO()
        with redirect_stdout(buf):
            weread.print_sync_report(plan, applied=False, vault_count=7)
        out = buf.getvalue()
        self.assertIn("孤儿", out)
        self.assertIn("已删除的书", out)

    def test_apply_mode_no_apply_hint(self):
        plan = {
            "missing": [{"bookId": "B1", "title": "T",
                         "author": "A", "noteCount": 1, "reviewCount": 1}],
            "stale": [], "orphan": [],
        }
        buf = io.StringIO()
        with redirect_stdout(buf):
            weread.print_sync_report(plan, applied=True, vault_count=7)
        out = buf.getvalue()
        self.assertNotIn("--apply", out)


class TestApplySyncPlan(unittest.TestCase):
    def test_single_failure_does_not_stop_others(self):
        """单本 fetch 失败应记入 failed，其他书继续。"""
        plan = {
            "missing": [
                {"bookId": "B_ok", "title": "成功的书",
                 "author": "A1", "noteCount": 10, "reviewCount": 1},
                {"bookId": "B_fail", "title": "失败的书",
                 "author": "A2", "noteCount": 5, "reviewCount": 0},
            ],
            "stale": [],
            "orphan": [],
        }

        def fake_fetch(book_id):
            if book_id == "B_fail":
                raise SystemExit("API error")
            return ({"updated": [], "chapters": []}, {"reviews": []})

        with tempfile.TemporaryDirectory() as out_dir:
            with mock.patch.object(weread, "fetch_book_notes",
                                   side_effect=fake_fetch), \
                 mock.patch.object(weread, "fetch_best_bookmarks",
                                   return_value=None), \
                 mock.patch.object(weread, "fetch_thoughts_for_bookmarks",
                                   return_value={}):
                # Suppress per-book stdout in test
                buf = io.StringIO()
                with redirect_stdout(buf):
                    result = weread.apply_sync_plan(plan, out_dir)

            self.assertEqual(result["synced"], 1)
            self.assertEqual(len(result["failed"]), 1)
            self.assertEqual(result["failed"][0]["bookId"], "B_fail")
            # 成功的书应该有文件
            self.assertTrue(any(
                "成功的书" in fn for fn in os.listdir(out_dir)
            ))

    def test_stale_uses_existing_path(self):
        """过期类应覆写到 vault 现有路径，不用 safe_filename 重新生成。"""
        with tempfile.TemporaryDirectory() as out_dir:
            existing_path = os.path.join(out_dir, "用户重命名过的文件.md")
            with open(existing_path, "w", encoding="utf-8") as f:
                f.write("old content")
            plan = {
                "missing": [],
                "stale": [{"bookId": "B1", "title": "新书名",
                           "author": "A1",
                           "path": existing_path,
                           "vault_highlights": 0, "vault_thoughts": 0,
                           "api_noteCount": 1, "api_reviewCount": 0}],
                "orphan": [],
            }
            with mock.patch.object(weread, "fetch_book_notes",
                                   return_value=({"updated": [], "chapters": []},
                                                 {"reviews": []})), \
                 mock.patch.object(weread, "fetch_best_bookmarks",
                                   return_value=None), \
                 mock.patch.object(weread, "fetch_thoughts_for_bookmarks",
                                   return_value={}):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    result = weread.apply_sync_plan(plan, out_dir)
            self.assertEqual(result["synced"], 1)
            # 文件应该还是同一个名字
            self.assertTrue(os.path.exists(existing_path))
            with open(existing_path, encoding="utf-8") as f:
                self.assertNotEqual(f.read(), "old content")


if __name__ == "__main__":
    unittest.main()
