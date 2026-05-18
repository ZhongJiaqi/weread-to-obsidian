import json
import unittest
from pathlib import Path
from tests import weread

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "readdata_overall.json").read_text("utf-8")
)


class TestDeriveInsights(unittest.TestCase):
    def test_returns_list_of_strings(self):
        out = weread.derive_insights(FIXTURE)
        self.assertIsInstance(out, list)
        for s in out:
            self.assertIsInstance(s, str)

    def test_reading_age(self):
        # registTime 2018-03-08，今年 2026 → 8 年读龄
        out = weread.derive_insights(FIXTURE)
        joined = " ".join(out)
        self.assertIn("年读龄", joined)

    def test_breakout_year(self):
        # 2026 比 2025 涨 2.5x，触发"爆发之年"
        out = weread.derive_insights(FIXTURE)
        joined = " ".join(out)
        self.assertIn("爆发之年", joined)

    def test_day_reader(self):
        # preferTime 18-23 总和 10, 全天 1500+，< 10%，触发"白天读书人"
        out = weread.derive_insights(FIXTURE)
        joined = " ".join(out)
        self.assertIn("白天读书人", joined)

    def test_practical_reader(self):
        # 心理+个人成长+经济理财 时长占总 > 80%
        out = weread.derive_insights(FIXTURE)
        joined = " ".join(out)
        self.assertTrue("实用书" in joined or "实用类" in joined)

    def test_no_breakout_when_data_missing(self):
        # 没有 readTimes 时不抛错
        out = weread.derive_insights({"registTime": 1520470365})
        self.assertIsInstance(out, list)


if __name__ == "__main__":
    unittest.main()
