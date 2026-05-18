import json
import unittest
from pathlib import Path
from tests import weread

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "readdata_overall.json").read_text("utf-8")
)


class TestBuildQuantityCallout(unittest.TestCase):
    def setUp(self):
        self.md = weread.build_quantity_callout(FIXTURE)

    def test_starts_with_callout_marker(self):
        self.assertTrue(self.md.startswith("> [!example] 📊 数量画像"))

    def test_contains_stat_counts(self):
        self.assertIn("33 本", self.md)
        self.assertIn("8 本", self.md)
        self.assertIn("251 天", self.md)
        self.assertIn("6,525 条", self.md)

    def test_contains_total_hours(self):
        # 717244 秒 ≈ 199.2h
        self.assertIn("199.2h", self.md)

    def test_contains_year_trend_bars(self):
        # 至少包含某年 ascii bar
        self.assertIn("2026", self.md)
        self.assertIn("▮", self.md)
        # 今年标记
        self.assertIn("进行中", self.md)

    def test_contains_top_books(self):
        # 单本时长 Top 3 都应在
        self.assertIn("影响力（全新升级版）", self.md)
        self.assertIn("富爸爸穷爸爸", self.md)
        self.assertIn("纳瓦尔宝典", self.md)
        # wikilink
        self.assertIn("[[影响力（全新升级版）]]", self.md)

    def test_contains_medals(self):
        self.assertIn("勋章", self.md)
        self.assertIn("想法发布 1000 条", self.md)

    def test_callout_format_lines_start_with_gt(self):
        # callout 内每行必须以 `>` 开头（Obsidian 渲染要求）
        # 允许空行：纯 `>` 也算 ok
        for ln in self.md.split("\n"):
            self.assertTrue(
                ln.startswith(">") or ln == "",
                f"line does not start with `>`: {ln!r}",
            )


if __name__ == "__main__":
    unittest.main()
