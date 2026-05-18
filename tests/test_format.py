import unittest
from tests import weread


class TestFormatHours(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(weread.format_hours(0), "0h")

    def test_minutes_only(self):
        # 30 分钟 = 1800 秒，不到 1 小时
        self.assertEqual(weread.format_hours(1800), "30 分钟")

    def test_exact_hour(self):
        self.assertEqual(weread.format_hours(3600), "1.0h")

    def test_compound(self):
        # 1 小时 30 分钟 = 5400 秒
        self.assertEqual(weread.format_hours(5400), "1.5h")

    def test_large(self):
        # 199.2 小时
        self.assertEqual(weread.format_hours(717120), "199.2h")


class TestAsciiBar(unittest.TestCase):
    def test_full(self):
        self.assertEqual(weread.ascii_bar(100, 100, width=10), "▮" * 10)

    def test_half(self):
        self.assertEqual(weread.ascii_bar(50, 100, width=10), "▮" * 5)

    def test_zero(self):
        # value=0 应该至少给一个最短可视化（避免空字符串）
        self.assertEqual(weread.ascii_bar(0, 100, width=10), "▮")

    def test_max_zero_safe(self):
        # max_value=0 不能除零
        self.assertEqual(weread.ascii_bar(5, 0, width=10), "▮")

    def test_custom_char(self):
        self.assertEqual(weread.ascii_bar(100, 100, width=5, char="="), "=====")


if __name__ == "__main__":
    unittest.main()
