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


if __name__ == "__main__":
    unittest.main()
