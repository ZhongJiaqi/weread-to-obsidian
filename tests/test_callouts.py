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


    def test_empty_data_does_not_crash(self):
        # 空 data 不应抛错，至少返回 callout 头
        md = weread.build_quantity_callout({})
        self.assertTrue(md.startswith("> [!example] 📊 数量画像"))

    def test_non_numeric_readtime_key_ignored(self):
        # readTimes 含非数字 key 时跳过该项，不崩
        bad = {"readTimes": {"1735660800": 100, "bad_key": 50}}
        md = weread.build_quantity_callout(bad)
        self.assertIn("2025", md)
        self.assertNotIn("bad_key", md)

    def test_medals_with_no_displaytext(self):
        # medals 非空但所有 displayText 缺失，不应输出空括号
        bad = {"medals": [{}, {}]}
        md = weread.build_quantity_callout(bad)
        self.assertIn("2 枚", md)
        # 不应出现空括号 "（）"
        self.assertNotIn("（）", md)


class TestBuildTasteCallout(unittest.TestCase):
    def setUp(self):
        self.md = weread.build_taste_callout(FIXTURE)

    def test_starts_with_callout_marker(self):
        self.assertTrue(self.md.startswith("> [!quote] 🎨 品味画像"))

    def test_contains_category_top(self):
        # preferCategory Top 几个
        self.assertIn("心理", self.md)
        self.assertIn("个人成长", self.md)
        self.assertIn("72", self.md)  # 心理 72.5h

    def test_contains_prefer_words(self):
        self.assertIn("偏好阅读心理", self.md)
        self.assertIn("偏好下午阅读", self.md)

    def test_authors_sorted_by_readtime(self):
        # 罗伯特·西奥迪尼 45h 应该在 刘墉 16h 之前出现
        idx_xidini = self.md.find("罗伯特·西奥迪尼")
        idx_liu = self.md.find("刘墉")
        self.assertGreater(idx_xidini, 0)
        self.assertGreater(idx_liu, 0)
        self.assertLess(idx_xidini, idx_liu)

    def test_authors_wikilinked(self):
        self.assertIn("[[罗伯特·西奥迪尼]]", self.md)

    def test_contains_author_count(self):
        self.assertIn("共读过 **19 位作者**", self.md)

    def test_contains_24h_distribution(self):
        # preferTime 24h，最大在 5 点（150）
        # 至少包含 "00" "23" 两个端点的标号
        self.assertIn("00", self.md)
        self.assertIn("23", self.md)
        # 包含峰值标记
        self.assertIn("峰值", self.md)

    def test_callout_format_lines_start_with_gt(self):
        for ln in self.md.split("\n"):
            self.assertTrue(
                ln.startswith(">") or ln == "",
                f"line does not start with `>`: {ln!r}",
            )

    def test_empty_data_does_not_crash(self):
        # 空 data 不应抛错，至少返回 callout 头
        md = weread.build_taste_callout({})
        self.assertTrue(md.startswith("> [!quote] 🎨 品味画像"))

    def test_zero_prefer_time_skipped(self):
        # preferTime 全 0 时整段不渲染，不应崩
        md = weread.build_taste_callout({"preferTime": [0] * 24})
        self.assertNotIn("阅读时段", md)
        self.assertNotIn("峰值", md)


class TestBuildProfileMarkdown(unittest.TestCase):
    def test_combines_quantity_and_taste(self):
        md = weread.build_profile_markdown(FIXTURE)
        self.assertIn("> [!example] 📊 数量画像", md)
        self.assertIn("> [!quote] 🎨 品味画像", md)
        # 两个 callout 之间有空行分隔
        idx_q = md.find("> [!example]")
        idx_t = md.find("> [!quote]")
        self.assertLess(idx_q, idx_t)
        # 中间至少有一个空行
        between = md[idx_q:idx_t]
        self.assertIn("\n\n", between)


if __name__ == "__main__":
    unittest.main()
