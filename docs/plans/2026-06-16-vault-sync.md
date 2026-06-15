# Vault Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `weread-to-obsidian` 加 `--sync` 子命令：对比 vault 与微信读书 list，输出三类 drift 报告（缺失/过期/孤儿），加 `--apply` 真正执行。

**Architecture:** 单一 API 调用（`/user/notebooks`）拿到所有书的 noteCount/reviewCount → 解析 vault 所有笔记的 frontmatter → 在内存里做集合对比，得到三类清单 → dry-run 渲染 stdout 报告 / `--apply` 复用 `fetch_book_notes` + `build_markdown` 写文件。复用项目所有现有抓取/渲染函数，新增 6 个纯函数（5 个纯算法 + 1 个有 IO）+ 1 个 CLI 入口。

**Tech Stack:** Python 3 stdlib only（与项目约束一致），unittest，frontmatter 用 `re` 手动解析（不引入 PyYAML），argparse 扩展现有子命令。

**Spec：** `docs/specs/2026-06-16-vault-sync-design.md`

---

## File Structure

| 路径 | 操作 | 责任 |
|---|---|---|
| `weread-to-obsidian` | 修改 | 主脚本，加 6 个新函数 + 1 入口 + 2 个 CLI flag。`is_finished` 从 `main()` 内嵌提升到模块级 |
| `tests/test_sync.py` | 新增 | `parse_vault_frontmatter` / `scan_vault` / `diff_vault_vs_api` / `apply_sync_plan` 错误处理路径的单元测试 |
| `tests/test_is_finished.py` | 新增 | 模块级 `is_finished` 单元测试（提升后能复用） |
| `tests/fixtures/sample_book.md` | 新增 | 一个完整 frontmatter 的笔记样本，供 frontmatter 解析测试用 |
| `tests/fixtures/vault_sample/` | 新增 | mini vault 目录（含 1 本书 + 1 个 `_索引.md`），供 `scan_vault` 测试 |
| `README.md` | 修改 | 加 `--sync` 用法 + 命令表更新 |
| `CLAUDE.md` | 修改 | 加架构条目：字段映射 + bookId 匹配 + drift 三分类 |
| `HANDOFF.md` | 修改 | 待办清单 #11 划掉，加最新 commit 链接 |

---

## Task 1: 把 `is_finished` 提升到模块级

**理由：** sync 需要复用判定逻辑，原嵌在 `main()` 内不可复用。提升 + 加单测，独立 commit 不与新功能混。

**Files:**
- Modify: `weread-to-obsidian:788-791`（移到 `def list_notebooks` 上方/同级模块作用域）
- Create: `tests/test_is_finished.py`

- [ ] **Step 1: 写失败测试**

`tests/test_is_finished.py`:

```python
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
        # markedStatus=1 但 progress 低 —— 仍然不算读完（CLAUDE.md 关键约束）
        self.assertFalse(
            weread.is_finished({"readingProgress": 42, "markedStatus": 1})
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试验证 FAIL**

```
python3 -m unittest tests.test_is_finished -v
```

预期：`AttributeError: module 'weread' has no attribute 'is_finished'`（或类似）

- [ ] **Step 3: 把 `is_finished` 从 `main()` 提升到模块级**

在 `weread-to-obsidian` 文件中找到 `def list_notebooks():`（行 62 附近），在它**上方**插入：

```python
def is_finished(nb):
    """判断一本书是否读完。只看 readingProgress >= 90，
    有意忽略 markedStatus —— 经验上 markedStatus 不准
    （用户经常误标或没改），progress >= 90 是更可信的'读完'信号。"""
    return nb.get("readingProgress", 0) >= 90
```

然后**删除** `main()` 内嵌的 `def is_finished(nb):` 整个块（行 788-791）。`main()` 内剩余调用 `is_finished(nb)` 不动，自然绑定到模块级。

- [ ] **Step 4: 跑测试验证 PASS**

```
python3 -m unittest tests.test_is_finished -v
python3 -m py_compile weread-to-obsidian
python3 -m unittest discover -s tests -v
```

预期：5 个新测试全 PASS + 现有 46 个全 PASS。

- [ ] **Step 5: Commit**

```bash
git add weread-to-obsidian tests/test_is_finished.py
git commit -m "refactor: is_finished 提升到模块级 + 单测"
```

---

## Task 2: `parse_vault_frontmatter` 单文件 frontmatter 解析

**Files:**
- Modify: `weread-to-obsidian`（在 `update_protected_section` 上方插入新函数）
- Create: `tests/test_sync.py`
- Create: `tests/fixtures/sample_book.md`

- [ ] **Step 1: 准备 fixture**

`tests/fixtures/sample_book.md`:

```markdown
---
title: "纳瓦尔宝典"
author: "[[埃里克·乔根森]]"
bookId: 44026191
source: 微信读书
type: 读书笔记
started: 2026-03-07
finished: 2026-03-29
highlights: 594
thoughts: 159
tags:
  - 读书笔记
weread: weread://reading?bId=44026191
exported: 2026-05-17 17:33
---

# 《纳瓦尔宝典》

正文内容...
```

- [ ] **Step 2: 写失败测试**

`tests/test_sync.py`（新建文件）:

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 跑测试验证 FAIL**

```
python3 -m unittest tests.test_sync.TestParseVaultFrontmatter -v
```

预期：`AttributeError: module 'weread' has no attribute 'parse_vault_frontmatter'`

- [ ] **Step 4: 实现 `parse_vault_frontmatter`**

在 `weread-to-obsidian` 中找到 `def update_protected_section`（行 479 附近），在它**上方**插入：

```python
def parse_vault_frontmatter(path):
    """读单个 .md 文件，提取 frontmatter 关键字段，返回 dict 或 None。

    返回字段：{bookId, title, type, highlights, thoughts}

    返回 None 的情况：
    - 文件无 YAML frontmatter（开头不是 ---）
    - frontmatter 中缺 bookId（无法用作唯一标识）

    用正则手动解析，不引入 PyYAML，与项目 stdlib only 约束一致。
    只解析单行 key: value 形式，不处理嵌套/多行（这里只取 5 个字段都是单行）。
    """
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
    except (OSError, UnicodeDecodeError):
        return None

    m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
    if not m:
        return None

    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^(\w+):\s*(.*)$", line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip().strip('"').strip("'")

    if "bookId" not in fm:
        return None

    return {
        "bookId": fm.get("bookId", ""),
        "title": fm.get("title", ""),
        "type": fm.get("type", ""),
        "highlights": int(fm.get("highlights", "0") or "0"),
        "thoughts": int(fm.get("thoughts", "0") or "0"),
    }
```

确保文件顶部已 `import re`（项目脚本已有，确认即可）。

- [ ] **Step 5: 跑测试验证 PASS**

```
python3 -m unittest tests.test_sync.TestParseVaultFrontmatter -v
python3 -m py_compile weread-to-obsidian
```

预期：4 个测试 PASS。

- [ ] **Step 6: Commit**

```bash
git add weread-to-obsidian tests/test_sync.py tests/fixtures/sample_book.md
git commit -m "feat: parse_vault_frontmatter + 单测"
```

---

## Task 3: `scan_vault` 遍历目录

**Files:**
- Modify: `weread-to-obsidian`（在 `parse_vault_frontmatter` 下方插入）
- Modify: `tests/test_sync.py`（追加测试类）
- Create: `tests/fixtures/vault_sample/sample_book.md`（复用 task 2 的 fixture 软链/复制）
- Create: `tests/fixtures/vault_sample/_索引.md`
- Create: `tests/fixtures/vault_sample/外部链接.md`

- [ ] **Step 1: 准备 mini vault fixture**

```bash
mkdir -p tests/fixtures/vault_sample
cp tests/fixtures/sample_book.md tests/fixtures/vault_sample/纳瓦尔宝典.md
```

`tests/fixtures/vault_sample/_索引.md`（应被跳过）:

```markdown
---
title: 索引页
type: 索引
---

# 索引
```

`tests/fixtures/vault_sample/外部链接.md`（应被跳过，type 不是读书笔记）:

```markdown
---
title: 外部资料
type: 资料
bookId: should_be_ignored
---

非读书笔记
```

- [ ] **Step 2: 写失败测试**

在 `tests/test_sync.py` 追加：

```python
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
        # _索引.md 没 bookId，但即使有也应被前缀过滤
        for rec in result.values():
            self.assertNotIn("_索引", rec["path"])

    def test_scan_skips_non_book_type(self):
        # 外部链接.md type=资料，应被过滤
        result = weread.scan_vault(self.vault)
        self.assertNotIn("should_be_ignored", result)

    def test_scan_missing_dir_returns_empty(self):
        result = weread.scan_vault("/nonexistent/path/xyz")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 跑测试验证 FAIL**

```
python3 -m unittest tests.test_sync.TestScanVault -v
```

预期：`AttributeError: module 'weread' has no attribute 'scan_vault'`

- [ ] **Step 4: 实现 `scan_vault`**

在 `parse_vault_frontmatter` 下方插入：

```python
def scan_vault(out_dir):
    """遍历 out_dir 下所有 .md 文件，解析 frontmatter，
    返回 {bookId: {path, title, highlights, thoughts}}。

    跳过条件：
    - 文件名以 _ 开头（_读书档案.md 等索引）
    - frontmatter 解析返回 None（无 frontmatter 或缺 bookId）
    - type != "读书笔记"（资料/索引等非笔记文件）

    目录不存在返回 {}。
    """
    if not os.path.isdir(out_dir):
        return {}

    books = {}
    for fn in os.listdir(out_dir):
        if not fn.endswith(".md") or fn.startswith("_"):
            continue
        path = os.path.join(out_dir, fn)
        rec = parse_vault_frontmatter(path)
        if rec is None:
            continue
        if rec.get("type") != "读书笔记":
            continue
        books[rec["bookId"]] = {
            "path": path,
            "title": rec["title"],
            "highlights": rec["highlights"],
            "thoughts": rec["thoughts"],
        }
    return books
```

- [ ] **Step 5: 跑测试验证 PASS**

```
python3 -m unittest tests.test_sync.TestScanVault -v
python3 -m unittest discover -s tests -v
```

预期：4 个新测试 PASS + 所有现有测试 PASS。

- [ ] **Step 6: Commit**

```bash
git add weread-to-obsidian tests/test_sync.py tests/fixtures/vault_sample/
git commit -m "feat: scan_vault 遍历 + 单测"
```

---

## Task 4: `diff_vault_vs_api` 核心算法

**Files:**
- Modify: `weread-to-obsidian`（在 `scan_vault` 下方插入）
- Modify: `tests/test_sync.py`（追加测试类）

- [ ] **Step 1: 写失败测试**

在 `tests/test_sync.py` 追加：

```python
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
```

- [ ] **Step 2: 跑测试验证 FAIL**

```
python3 -m unittest tests.test_sync.TestDiffVaultVsApi -v
```

预期：`AttributeError: module 'weread' has no attribute 'diff_vault_vs_api'`

- [ ] **Step 3: 实现 `diff_vault_vs_api`**

在 `scan_vault` 下方插入：

```python
def diff_vault_vs_api(vault, api_books, include_reading=False):
    """对比 vault 与 API list，返回三类 drift 计划。

    Args:
        vault: scan_vault 返回值 {bookId: {path, title, highlights, thoughts}}
        api_books: list_notebooks 返回值，每条含
            {bookId, book: {title, author}, readingProgress, noteCount, reviewCount}
        include_reading: True 时 missing 类不要求 progress >= 90

    Returns:
        {
            "missing": [{bookId, title, author, noteCount, reviewCount}, ...],
            "stale":   [{bookId, title, path, vault_highlights, vault_thoughts,
                         api_noteCount, api_reviewCount}, ...],
            "orphan":  [{bookId, title, path, highlights, thoughts}, ...],
        }

    字段映射约束（已实测对齐）：
        API noteCount   ↔ vault highlights
        API reviewCount ↔ vault thoughts
    """
    api_by_id = {nb.get("bookId"): nb for nb in api_books if nb.get("bookId")}

    missing = []
    stale = []
    for bid, nb in api_by_id.items():
        bk = nb.get("book") or {}
        note_count = nb.get("noteCount", 0)
        review_count = nb.get("reviewCount", 0)

        if bid not in vault:
            if include_reading or is_finished(nb):
                missing.append({
                    "bookId": bid,
                    "title": bk.get("title", ""),
                    "author": bk.get("author", ""),
                    "noteCount": note_count,
                    "reviewCount": review_count,
                })
            continue

        v = vault[bid]
        if (v["highlights"] != note_count
                or v["thoughts"] != review_count):
            stale.append({
                "bookId": bid,
                "title": bk.get("title", "") or v["title"],
                "path": v["path"],
                "vault_highlights": v["highlights"],
                "vault_thoughts": v["thoughts"],
                "api_noteCount": note_count,
                "api_reviewCount": review_count,
            })

    orphan = []
    for bid, v in vault.items():
        if bid not in api_by_id:
            orphan.append({
                "bookId": bid,
                "title": v["title"],
                "path": v["path"],
                "highlights": v["highlights"],
                "thoughts": v["thoughts"],
            })

    return {"missing": missing, "stale": stale, "orphan": orphan}
```

- [ ] **Step 4: 跑测试验证 PASS**

```
python3 -m unittest tests.test_sync.TestDiffVaultVsApi -v
python3 -m unittest discover -s tests -v
```

预期：8 个新测试 PASS + 全部现有 PASS。

- [ ] **Step 5: Commit**

```bash
git add weread-to-obsidian tests/test_sync.py
git commit -m "feat: diff_vault_vs_api 三类 drift 核心算法 + 单测"
```

---

## Task 5: `print_sync_report` 渲染 stdout 报告

**Files:**
- Modify: `weread-to-obsidian`（在 `diff_vault_vs_api` 下方插入）
- Modify: `tests/test_sync.py`（追加测试类）

- [ ] **Step 1: 写失败测试**

在 `tests/test_sync.py` 追加：

```python
import io
from contextlib import redirect_stdout


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
```

- [ ] **Step 2: 跑测试验证 FAIL**

```
python3 -m unittest tests.test_sync.TestPrintSyncReport -v
```

预期：`AttributeError: ...`

- [ ] **Step 3: 实现 `print_sync_report`**

在 `diff_vault_vs_api` 下方插入：

```python
def print_sync_report(plan, applied, vault_count):
    """渲染 drift 报告到 stdout。

    Args:
        plan: diff_vault_vs_api 返回值
        applied: True 表示 --apply 模式（不打印 "加 --apply 真正执行" 提示）
        vault_count: vault 已扫描到的书本数（用于无 drift 时的"7 本"提示）
    """
    m, s, o = plan["missing"], plan["stale"], plan["orphan"]

    if not (m or s or o):
        print(f"✅ vault 与微信读书已同步（{vault_count} 本）")
        return

    if m:
        print(f"\n📥 缺失（{len(m)} 本）：")
        for it in m:
            print(f"  · {it['title']} — {it['author']}"
                  f"（{it['noteCount']} 划 / {it['reviewCount']} 想）")

    if s:
        print(f"\n🔄 过期（{len(s)} 本）：")
        for it in s:
            print(f"  · {it['title']} — 本地 "
                  f"{it['vault_highlights']}/{it['vault_thoughts']} → "
                  f"微信读书 {it['api_noteCount']}/{it['api_reviewCount']}")

    if o:
        print(f"\n👻 孤儿（vault 在但微信读书 list 没有，{len(o)} 本）：")
        for it in o:
            print(f"  · {it['title']}（{it['highlights']} 划 / "
                  f"{it['thoughts']} 想；{it['path']}）")
        print("  → 不动 vault。可能是 API key 切换 / 微信读书删书，需人工处理。")

    if not applied:
        n_pull = len(m)
        n_refresh = len(s)
        est_sec = (n_pull + n_refresh) * 10
        print(f"\n→ 计划：拉 {n_pull} 本 + 重拉 {n_refresh} 本（约 {est_sec} 秒）")
        print("→ dry-run。加 --apply 真正执行。")
```

- [ ] **Step 4: 跑测试验证 PASS**

```
python3 -m unittest tests.test_sync.TestPrintSyncReport -v
```

预期：5 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add weread-to-obsidian tests/test_sync.py
git commit -m "feat: print_sync_report 三类清单 stdout 渲染 + 单测"
```

---

## Task 6: `apply_sync_plan` 真正执行

**Files:**
- Modify: `weread-to-obsidian`（在 `print_sync_report` 下方插入）
- Modify: `tests/test_sync.py`（追加 mock 错误处理测试）

**注意：** `apply_sync_plan` 重度依赖 API + IO，集成测试与 `--profile` 策略一致**不写**。只写一个 mock 测试覆盖错误处理路径（单本失败继续）。

- [ ] **Step 1: 写失败测试（错误处理）**

在 `tests/test_sync.py` 追加：

```python
import tempfile
from unittest import mock


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
            with mock.patch.object(weread, "fetch_book_notes", side_effect=fake_fetch), \
                 mock.patch.object(weread, "fetch_best_bookmarks", return_value=None), \
                 mock.patch.object(weread, "fetch_thoughts_for_bookmarks", return_value={}):
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
                           "path": existing_path,
                           "vault_highlights": 0, "vault_thoughts": 0,
                           "api_noteCount": 1, "api_reviewCount": 0}],
                "orphan": [],
            }
            with mock.patch.object(weread, "fetch_book_notes",
                                   return_value=({"updated": [], "chapters": []},
                                                 {"reviews": []})), \
                 mock.patch.object(weread, "fetch_best_bookmarks", return_value=None), \
                 mock.patch.object(weread, "fetch_thoughts_for_bookmarks", return_value={}):
                result = weread.apply_sync_plan(plan, out_dir)
            self.assertEqual(result["synced"], 1)
            # 文件应该还是同一个名字
            self.assertTrue(os.path.exists(existing_path))
            with open(existing_path, encoding="utf-8") as f:
                # 应该被覆写了（不再是 "old content"）
                self.assertNotEqual(f.read(), "old content")
```

- [ ] **Step 2: 跑测试验证 FAIL**

```
python3 -m unittest tests.test_sync.TestApplySyncPlan -v
```

预期：`AttributeError: ...`

- [ ] **Step 3: 实现 `apply_sync_plan`**

在 `print_sync_report` 下方插入：

```python
def apply_sync_plan(plan, out_dir):
    """执行同步计划：拉缺失 + 刷过期。孤儿不动。

    Args:
        plan: diff_vault_vs_api 返回值
        out_dir: vault 子目录绝对路径

    Returns:
        {"synced": N, "failed": [{"bookId", "title", "reason"}, ...]}

    单本 fetch 失败（SystemExit）会被 catch，记录到 failed 后继续其他书。
    """
    synced = 0
    failed = []

    def _write_book(bid, title, author, target_path):
        try:
            bm, rv = fetch_book_notes(bid)
            best = fetch_best_bookmarks(bid)
            best_thoughts = fetch_thoughts_for_bookmarks(bid, best)
            md = build_markdown(bid, title, author or "", bm, rv, best, best_thoughts)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(md)
            return True, None
        except SystemExit as e:
            return False, str(e)

    for item in plan["missing"]:
        bid = item["bookId"]
        title = item["title"]
        path = os.path.join(out_dir, safe_filename(title) + ".md")
        ok, reason = _write_book(bid, title, item["author"], path)
        if ok:
            print(f"✓ 拉取: {title}")
            synced += 1
        else:
            print(f"✗ 拉取失败: {title} — {reason}")
            failed.append({"bookId": bid, "title": title, "reason": reason})

    for item in plan["stale"]:
        bid = item["bookId"]
        title = item["title"]
        path = item["path"]  # 用 vault 现有路径，保护用户重命名/移动
        # author 未在 stale dict 里携带，从 path 上下文读不到。
        # 这里复用 build_markdown 时 author 传 ""，让 frontmatter 写空。
        # 若想保留，需要在 stale 项里追加 author —— 本次不做（YAGNI）。
        # 实际：stale 时书本已存在，重拉本质是用最新 API 数据覆写。
        # 解决：从 API list 里反查 author。
        # 简单实现：apply 时再过一次 list，拿 author。但成本高。
        # 让 stale 项在 diff 阶段直接带 author（更新 spec/diff 实现）。
        ok, reason = _write_book(bid, title, item.get("author", ""), path)
        if ok:
            print(f"✓ 重拉: {title}")
            synced += 1
        else:
            print(f"✗ 重拉失败: {title} — {reason}")
            failed.append({"bookId": bid, "title": title, "reason": reason})

    return {"synced": synced, "failed": failed}
```

**额外修正：** 上面注释指出的 author 问题需要在 `diff_vault_vs_api` 的 stale 项里追加 `author` 字段。回到 Task 4 的代码，在 `stale.append(...)` 字典里加：

```python
"author": bk.get("author", ""),
```

并把对应测试 `test_stale_when_highlights_differ` 加一行断言：

```python
self.assertEqual(s["author"], "A4")
```

然后这里把注释删掉，调用改成：

```python
ok, reason = _write_book(bid, title, item.get("author", ""), path)
```

（已经是 `item.get("author", "")` 兼容写法，无须再改。）

- [ ] **Step 4: 修正 Task 4 — 补 stale 项的 author**

`weread-to-obsidian` 中 `diff_vault_vs_api` 的 stale.append 字典加一行 `"author": bk.get("author", ""),`：

```python
stale.append({
    "bookId": bid,
    "title": bk.get("title", "") or v["title"],
    "author": bk.get("author", ""),  # 新增
    "path": v["path"],
    "vault_highlights": v["highlights"],
    "vault_thoughts": v["thoughts"],
    "api_noteCount": note_count,
    "api_reviewCount": review_count,
})
```

在 `tests/test_sync.py` 的 `test_stale_when_highlights_differ` 加：

```python
self.assertEqual(s["author"], "A4")
```

并删除 `apply_sync_plan` 实现里关于 author 的多余注释（保留 `item.get("author", "")` 调用即可）。

- [ ] **Step 5: 跑测试验证 PASS**

```
python3 -m unittest tests.test_sync.TestApplySyncPlan -v
python3 -m unittest tests.test_sync.TestDiffVaultVsApi -v
python3 -m unittest discover -s tests -v
```

预期：2 个新 apply 测试 PASS + 之前 diff 测试 PASS（多了 author 断言）+ 全部现有 PASS。

- [ ] **Step 6: Commit**

```bash
git add weread-to-obsidian tests/test_sync.py
git commit -m "feat: apply_sync_plan 真正执行 + 错误处理 + 单测"
```

---

## Task 7: `main_sync` 入口 + CLI argparse 接线

**Files:**
- Modify: `weread-to-obsidian`（新增 `main_sync` + argparse 改 + main 分支）

- [ ] **Step 1: 加 CLI 参数**

在 `main()` 的 `p.add_argument` 序列中（"--dry-run" 之后）追加：

```python
    p.add_argument(
        "--sync",
        action="store_true",
        help="对比 vault 与微信读书，输出 drift 报告（默认 dry-run，加 --apply 真正执行）",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="配合 --sync 时真正执行同步操作",
    )
```

- [ ] **Step 2: 在 main() 加分支与互斥校验**

在 `main()` 中 `if args.profile:` 块**之后**，`nbs = list_notebooks()` **之前**（即第 774 行附近），插入：

```python
    if args.apply and not args.sync:
        sys.exit("--apply 必须配合 --sync 使用")

    if args.sync:
        main_sync(args, out_dir)
        return
```

- [ ] **Step 3: 实现 `main_sync`**

在 `main_profile` 上方插入：

```python
def main_sync(args, out_dir):
    """--sync 子命令入口：诊断 vault 与微信读书的 drift。

    默认 dry-run（仅打印计划）。加 --apply 才真正执行 missing + stale 同步。
    孤儿（vault 有但 API list 无）永远只警告，不动 vault。
    """
    vault = scan_vault(out_dir)
    print(f"扫描 vault... {len(vault)} 本")

    api_books = list_notebooks()
    print(f"拉取微信读书 list... {len(api_books)} 本有笔记")

    plan = diff_vault_vs_api(vault, api_books,
                              include_reading=args.include_reading)

    if args.apply:
        print_sync_report(plan, applied=True, vault_count=len(vault))
        if not (plan["missing"] or plan["stale"]):
            return
        os.makedirs(out_dir, exist_ok=True)
        result = apply_sync_plan(plan, out_dir)
        n_fail = len(result["failed"])
        print(f"\n完成: {result['synced']} 本同步 / {n_fail} 失败")
    else:
        print_sync_report(plan, applied=False, vault_count=len(vault))
```

- [ ] **Step 4: 跑全套测试 + 语法检查**

```
python3 -m py_compile weread-to-obsidian
python3 -m unittest discover -s tests -v
```

预期：全 PASS。

- [ ] **Step 5: Commit**

```bash
git add weread-to-obsidian
git commit -m "feat: --sync 子命令接线 + main_sync 入口"
```

---

## Task 8: 真实 vault e2e 验证

**Files：** 不改文件，验证步骤。

- [ ] **Step 1: 安装最新脚本到 ~/.local/bin/**

```bash
./install.sh
```

- [ ] **Step 2: 跑 dry-run，看输出**

```bash
weread-to-obsidian --sync
```

预期输出（基于勘探时的现状）：
- 扫描 vault... 7 本
- 拉取微信读书 list... 26 本有笔记
- 📥 缺失（约 17 本，已读完但未导入）
- 🔄 过期：可能 0 本（如果勘探后用户没新增划线）或几本
- 👻 孤儿：0 本

**判断标准：**
- 输出格式跟 spec mock 一致
- 缺失类应包含《权力48法则》（勘探时已确认 progress=100 不在 vault）
- 计数与勘探时实测一致

- [ ] **Step 3: 不跑 --apply（除非用户明确想真同步）**

如果验证 dry-run 输出符合预期，e2e 完成。**不主动 `--apply`**——用户后续想同步时自己决定。

- [ ] **Step 4: 如果发现问题，回到对应 task 修复并重新跑测试**

可能的真实数据反例：
- 频繁误报 stale：说明字段映射假设有漏（重新实测）
- 解析失败：vault 里某本书 frontmatter 与 fixture 假设不同（增强 parser）

修复后 commit + 重跑。

---

## Task 9: 文档同步

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `HANDOFF.md`

- [ ] **Step 1: README.md 加 --sync 说明**

找到现有命令表，在合适位置插入 `--sync` 行。在"用法"区块加一段示例：

```markdown
### 同步 vault 与微信读书

```bash
weread-to-obsidian --sync             # 看 drift 报告（dry-run）
weread-to-obsidian --sync --apply     # 真正同步（拉缺的 + 刷过期的）
```

`--sync` 用一次轻量 API 调用对比 vault 笔记与微信读书最新数据，输出三类：

- 📥 **缺失**：已读完但 vault 没有的书 → `--apply` 自动拉取
- 🔄 **过期**：vault 在但本地 highlights/thoughts ≠ 微信读书最新数 → `--apply` 自动重拉
- 👻 **孤儿**：vault 在但微信读书 list 没有 → 只警告，不动 vault（可能是 API key 切换或微信读书删书）

跟 `--all --force` 的区别：`--all --force` 粗暴全刷所有读完书；`--sync` 精准只动有变化的。
```

- [ ] **Step 2: CLAUDE.md 加架构条目**

在"关键架构决定"段追加：

```markdown
### 10. drift 检测的字段映射约束（--sync）

`--sync` 用 `/user/notebooks` 单次调用拿到所有书的 `noteCount` / `reviewCount` 对比 vault：

- API `noteCount` ↔ vault frontmatter `highlights`（划线数）
- API `reviewCount` ↔ vault frontmatter `thoughts`（想法数）
- API `bookmarkCount` **不使用**（实测多本为 0，语义未明）

这是 2026-06-16 实测 7 本对齐书得出的对应关系。如果未来微信读书改字段语义，drift 会乱报。

文件匹配用 frontmatter 的 `bookId`，**不用 `safe_filename(title)` 反推**——书名带特殊字符或用户手动重命名时反推会失败。

孤儿（vault 在 + API 没有）只警告不动 vault——保护用户可能手动整理/重命名/挪到子目录的笔记。
```

- [ ] **Step 3: HANDOFF.md 待办清单 #11 划掉 + 已完成事项追加**

`HANDOFF.md` 待做清单 #11 改为：

```markdown
11. ~~obsidian-cli vault 维护脚本~~ ✅ 2026-06-16 改成 `--sync` drift 检测（不是 frontmatter 补字段）
```

在"已完成的事"段追加：

```markdown
### 14. `--sync` drift 检测（2026-06-16）

勘探发现原计划"补 frontmatter"无 ROI（vault 字段 100% 对齐）。真正缺口是 vault 7 本 vs 微信读书 26 本有笔记的同步状态。

新 CLI 命令 `weread-to-obsidian --sync` 用一次 `/user/notebooks` 对比，输出三类 drift：缺失 / 过期 / 孤儿。默认 dry-run，加 `--apply` 真正执行（拉缺 + 刷过期；孤儿永远不动）。

实现：6 个新函数（`parse_vault_frontmatter` / `scan_vault` / `diff_vault_vs_api` / `print_sync_report` / `apply_sync_plan` / `main_sync`）+ `is_finished` 提升到模块级。测试：tests/test_sync.py 覆盖 4 个纯函数 19+ 个 case + tests/test_is_finished.py 5 个 case。

设计文档：docs/specs/2026-06-16-vault-sync-design.md
实施计划：docs/plans/2026-06-16-vault-sync.md
```

- [ ] **Step 4: 验证 + commit**

```bash
python3 -m py_compile weread-to-obsidian
python3 -m unittest discover -s tests -v
git add README.md CLAUDE.md HANDOFF.md
git commit -m "docs: --sync 命令的 README / CLAUDE / HANDOFF 同步"
```

**注意：** HANDOFF.md 是 local-only（参考用户 feedback `[[feedback-handoff-local-only]]`）。这条 commit 包含 HANDOFF.md 改动，push 前必须把它从 push 路径剔除（rebase --onto origin/master）。

- [ ] **Step 5: push 前 HANDOFF 处理**

```bash
git log --oneline @{u}..HEAD
# 列出本地领先 origin 的所有 commit。如果最后一条 commit 同时改了 HANDOFF.md
# 和 README/CLAUDE，需要分拆，否则 HANDOFF 会跟随 push。

# 推荐做法：上一步分两个 commit：
# 1) docs: README + CLAUDE --sync 文档
# 2) handoff: 进度更新（local only）
# 然后 push 时跳过 handoff commit：
git push origin HEAD~1:main  # 推送除最后一个 handoff commit 外的所有
```

如果 step 4 直接合 commit 了，先拆：

```bash
git reset HEAD^
git add README.md CLAUDE.md
git commit -m "docs: --sync 命令的 README / CLAUDE 同步"
git add HANDOFF.md
git commit -m "handoff: --sync 实施完成"
git push origin HEAD~1:main
```

---

## Self-Review

**1. Spec coverage:**
- ✅ 三类 drift（missing/stale/orphan）→ Task 4 实现 + 单测
- ✅ 字段映射 noteCount/reviewCount → Task 4 + CLAUDE.md (Task 9)
- ✅ 默认 dry-run + --apply → Task 7 入口逻辑 + Task 5 print_sync_report
- ✅ 孤儿不动 vault → Task 6 apply_sync_plan 只处理 missing + stale
- ✅ 文件名 bookId 匹配 → Task 3 scan_vault key 用 bookId + Task 6 stale 用 existing path
- ✅ is_finished 提升模块级 → Task 1
- ✅ --include-reading 沿用 → Task 7 main_sync 透传 args.include_reading
- ✅ 单本失败继续 → Task 6 _write_book catch SystemExit
- ✅ 单元测试覆盖 4 个纯函数 → Task 2/3/4/5
- ✅ apply 错误处理测试 → Task 6 mock 测试

**2. Placeholder scan:** ✅ 无 TBD/TODO；每个 step 有完整代码或具体命令。

**3. Type consistency:**
- `parse_vault_frontmatter` 返回字段 {bookId, title, type, highlights, thoughts} 在 scan_vault 中正确消费 ✓
- `scan_vault` 返回 {bookId: {path, title, highlights, thoughts}} 在 diff_vault_vs_api 中正确消费 ✓
- `diff_vault_vs_api` 返回 plan 三类字段命名一致（missing 用 title/author/noteCount/reviewCount；stale 用 vault_highlights/vault_thoughts/api_noteCount/api_reviewCount；orphan 用 title/path/highlights/thoughts）✓
- Task 6 中发现 stale 缺 author → Step 4 已修正补回 ✓
- `apply_sync_plan` 返回 {synced, failed} 在 main_sync 正确消费 ✓
