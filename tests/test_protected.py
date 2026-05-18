import os
import tempfile
import unittest
from pathlib import Path
from tests import weread


class TestUpdateProtectedSection(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / "_读书档案.md"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_file_not_exist_creates_from_template(self):
        """场景 1：文件不存在 → 用模板新建，包含 H1 + 保护区"""
        weread.update_protected_section(str(self.path), "新画像内容")
        self.assertTrue(self.path.exists())
        text = self.path.read_text("utf-8")
        self.assertIn("# 📚 我的读书档案", text)
        self.assertIn("<!-- WEREAD-PROFILE-START", text)
        self.assertIn("<!-- WEREAD-PROFILE-END", text)
        self.assertIn("新画像内容", text)

    def test_file_exists_no_markers_inserts_after_h1(self):
        """场景 2：文件存在但无标记 → 在 H1 之后插入保护区"""
        self.path.write_text(
            "# 📚 我的读书档案\n\n手写内容\n## 索引\n表格\n", "utf-8"
        )
        weread.update_protected_section(str(self.path), "新画像内容")
        text = self.path.read_text("utf-8")
        self.assertIn("新画像内容", text)
        # 保护区在 H1 之后
        h1_idx = text.find("# 📚 我的读书档案")
        start_idx = text.find("<!-- WEREAD-PROFILE-START")
        manual_idx = text.find("手写内容")
        self.assertLess(h1_idx, start_idx)
        # 用户手写内容保留
        self.assertIn("手写内容", text)
        self.assertIn("## 索引", text)
        # 保护区在手写内容之前（顶部插入）
        self.assertLess(start_idx, manual_idx)

    def test_existing_markers_replace_content(self):
        """场景 3：标记完整 → 只替换标记之间的内容"""
        self.path.write_text(
            "# 📚 我的读书档案\n\n"
            "<!-- WEREAD-PROFILE-START · 自动生成 · 请勿手动修改 -->\n"
            "旧画像内容\n"
            "<!-- WEREAD-PROFILE-END -->\n\n"
            "手写索引保留\n",
            "utf-8",
        )
        weread.update_protected_section(str(self.path), "新画像内容")
        text = self.path.read_text("utf-8")
        self.assertNotIn("旧画像内容", text)
        self.assertIn("新画像内容", text)
        self.assertIn("手写索引保留", text)
        # 标记本身保留
        self.assertIn("<!-- WEREAD-PROFILE-START", text)
        self.assertIn("<!-- WEREAD-PROFILE-END", text)

    def test_only_start_marker_aborts(self):
        """场景 4：只有 START 没有 END（手动破坏）→ 不修改，抛 SystemExit"""
        original = (
            "# 📚 我的读书档案\n\n"
            "<!-- WEREAD-PROFILE-START -->\n"
            "破损内容（没 END）\n\n"
            "手写内容\n"
        )
        self.path.write_text(original, "utf-8")
        with self.assertRaises(SystemExit):
            weread.update_protected_section(str(self.path), "新画像内容")
        # 文件未变
        self.assertEqual(self.path.read_text("utf-8"), original)

    def test_only_end_marker_aborts(self):
        """对称：只有 END 没有 START 也应抛 SystemExit"""
        original = (
            "# 📚 我的读书档案\n\n"
            "孤立的 END 标记：\n"
            "<!-- WEREAD-PROFILE-END -->\n\n"
            "手写内容\n"
        )
        self.path.write_text(original, "utf-8")
        with self.assertRaises(SystemExit):
            weread.update_protected_section(str(self.path), "新画像内容")
        self.assertEqual(self.path.read_text("utf-8"), original)

    def test_bare_filename_no_directory_works(self):
        """bare 文件名（无目录部分）也能新建"""
        import os
        cwd = os.getcwd()
        os.chdir(self.tmpdir)
        try:
            weread.update_protected_section("_读书档案.md", "新画像内容")
            self.assertTrue(os.path.exists("_读书档案.md"))
        finally:
            os.chdir(cwd)

    def test_dry_run_returns_full_text_without_writing(self):
        """dry_run=True 时返回最终文本但不写入磁盘"""
        self.assertFalse(self.path.exists())
        result = weread.update_protected_section(
            str(self.path), "新画像内容", dry_run=True
        )
        self.assertIn("新画像内容", result)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
