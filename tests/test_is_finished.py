import unittest

from tests import weread


class TestIsFinished(unittest.TestCase):
    def test_progress_above_90_finished(self):
        self.assertTrue(weread.is_finished({"readingProgress": 95}))

    def test_progress_exactly_90_finished(self):
        self.assertTrue(weread.is_finished({"readingProgress": 90}))

    def test_progress_89_not_finished(self):
        self.assertFalse(weread.is_finished({"readingProgress": 89}))

    def test_missing_progress_not_finished(self):
        self.assertFalse(weread.is_finished({}))

    def test_ignores_markedStatus_when_progress_low(self):
        # markedStatus=1 but progress low — still not finished
        # (CLAUDE.md key constraint)
        self.assertFalse(
            weread.is_finished({"readingProgress": 42, "markedStatus": 1})
        )


if __name__ == "__main__":
    unittest.main()
