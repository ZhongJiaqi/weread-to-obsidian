# Reader Profile (Spec A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `_读书档案.md` 顶部嵌入由脚本自动生成的"数量画像 + 品味画像"双 callout，并提供新 CLI 命令 `weread-to-obsidian --profile` 触发更新；保护区机制确保不破坏用户手写内容。

**Architecture:** 纯 stdlib Python，一次调 `/readdata/detail` mode=overall 拿全量数据，本地聚合成 Markdown，通过 HTML 注释保护区只覆盖画像段。新增函数挂在现有单文件脚本 `weread-to-obsidian` 中；测试用 `unittest`（stdlib）+ `importlib` 动态加载脚本（绕过无 .py 后缀的 import 限制）。

**Tech Stack:** Python 3 stdlib only · unittest · importlib · GitHub Actions (CI)

**Spec Reference:** `docs/specs/2026-05-18-reader-profile-design.md`

---

## File Structure

| 文件 | 作用 |
|---|---|
| `weread-to-obsidian` | 主脚本，新增画像函数 + `--profile` 分支 |
| `tests/__init__.py` | 用 `importlib` 把主脚本加载为 `weread` 模块供测试使用 |
| `tests/fixtures/readdata_overall.json` | 真实 `/readdata/detail` 回包（缩减/脱敏版）供单测固定输入 |
| `tests/test_format.py` | `format_hours` + `ascii_bar` 单测 |
| `tests/test_insights.py` | `derive_insights` 4 条规则单测 |
| `tests/test_callouts.py` | `build_quantity_callout` + `build_taste_callout` + `build_profile_markdown` 单测 |
| `tests/test_protected.py` | `update_protected_section` 4 个场景单测 |
| `.github/workflows/syntax-check.yml` | CI 增加 `python -m unittest discover tests` 步骤 |
| `CLAUDE.md` | 项目级 CLAUDE.md 加新约束（保护区机制、画像 API） |
| `README.md` | 加 `--profile` 用法 |

---

## Task 1: 测试基础设施 + format helpers

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_format.py`
- Modify: `weread-to-obsidian`（在 `safe_filename` 之后插入两个 helper）

- [ ] **Step 1.1: 写 tests/__init__.py 动态加载器**

```python
# tests/__init__.py
"""动态加载主脚本（无 .py 后缀）为 weread 模块。"""
import importlib.util
import sys
from pathlib import Path

_path = Path(__file__).parent.parent / "weread-to-obsidian"
_spec = importlib.util.spec_from_file_location("weread", _path)
weread = importlib.util.module_from_spec(_spec)
sys.modules["weread"] = weread
_spec.loader.exec_module(weread)
```

- [ ] **Step 1.2: 写失败的 format_hours + ascii_bar 测试**

```python
# tests/test_format.py
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
```

- [ ] **Step 1.3: 跑测试确认失败**

```bash
cd /Users/jiaqizhong/weread-to-obsidian
python3 -m unittest tests.test_format -v
```

Expected: 全部失败，错误信息含 `AttributeError: module 'weread' has no attribute 'format_hours'`

- [ ] **Step 1.4: 在 weread-to-obsidian 中实现 format_hours 和 ascii_bar**

在 `safe_filename` 函数定义之后（约 124 行后）插入：

```python
def format_hours(seconds):
    """秒数 → 人类可读时长。
    < 1 小时 显示 N 分钟，否则显示 N.Nh（保留 1 位小数）。
    """
    if seconds <= 0:
        return "0h"
    if seconds < 3600:
        return f"{int(round(seconds / 60))} 分钟"
    return f"{round(seconds / 3600, 1)}h"


def ascii_bar(value, max_value, width=20, char="▮"):
    """画一行等宽 ascii bar。value=0 或 max_value<=0 时至少 1 格，避免空字符串。"""
    if max_value <= 0 or value <= 0:
        return char
    n = max(1, int(round(value / max_value * width)))
    return char * n
```

- [ ] **Step 1.5: 跑测试确认通过 + commit**

```bash
python3 -m unittest tests.test_format -v
```

Expected: `Ran 10 tests in 0.00Xs   OK`

```bash
git add tests/__init__.py tests/test_format.py weread-to-obsidian
git commit -m "feat: 加 format_hours + ascii_bar helpers + 测试基础设施

tests/__init__.py 用 importlib 把无 .py 后缀的主脚本加载为
weread 模块，让所有单元测试可以 from tests import weread。

format_hours：秒数 → 人类可读（<1h 显示分钟，>=1h 显示 N.Nh）
ascii_bar：等宽 ascii 条形图，value=0 或 max=0 时给 1 格防空"
```

---

## Task 2: 创建 fixture 和 insights 规则函数

**Files:**
- Create: `tests/fixtures/readdata_overall.json`
- Create: `tests/test_insights.py`
- Modify: `weread-to-obsidian`（加 `derive_insights`）

- [ ] **Step 2.1: 写 fixture 文件**

```json
// tests/fixtures/readdata_overall.json
{
  "readStat": [
    {"stat": "读过", "counts": "33本"},
    {"stat": "读完", "counts": "8本"},
    {"stat": "阅读", "counts": "251天"},
    {"stat": "笔记", "counts": "6525条"}
  ],
  "readDays": 251,
  "totalReadTime": 717244,
  "registTime": 1520470365,
  "readTimes": {
    "1514736000": 0,
    "1546272000": 0,
    "1577808000": 0,
    "1609430400": 29520,
    "1640966400": 4320,
    "1672502400": 7200,
    "1704038400": 5400,
    "1735660800": 189000,
    "1767196800": 481680
  },
  "readLongest": [
    {"book": {"title": "影响力（全新升级版）"}, "readTime": 163080, "tags": ["笔记最多"]},
    {"book": {"title": "富爸爸穷爸爸"}, "readTime": 75240, "tags": ["单日阅读最久"]},
    {"book": {"title": "纳瓦尔宝典"}, "readTime": 68760, "tags": []}
  ],
  "preferCategory": [
    {"categoryTitle": "心理", "readingCount": 7, "readingTime": 261000},
    {"categoryTitle": "个人成长", "readingCount": 15, "readingTime": 240120},
    {"categoryTitle": "经济理财", "readingCount": 5, "readingTime": 153000},
    {"categoryTitle": "生活百科", "readingCount": 2, "readingTime": 22320},
    {"categoryTitle": "历史", "readingCount": 1, "readingTime": 720}
  ],
  "preferCategoryWord": "偏好阅读心理",
  "preferTime": [10, 30, 70, 80, 100, 150, 140, 140, 90, 110, 120, 100, 50, 50, 80, 100, 90, 70, 10, 0, 0, 0, 0, 0],
  "preferTimeWord": "偏好下午阅读",
  "preferAuthor": [
    {"name": "刘墉", "count": 2, "readTime": "16小时44分钟"},
    {"name": "斯蒂芬·盖斯", "count": 2, "readTime": "16小时3分钟"},
    {"name": "罗伯特·西奥迪尼", "count": 1, "readTime": "45小时18分钟"},
    {"name": "罗伯特·清崎", "count": 1, "readTime": "20小时56分钟"},
    {"name": "埃里克·乔根森", "count": 1, "readTime": "19小时6分钟"}
  ],
  "authorCount": 19,
  "medals": [
    {"displayText": "想法发布 1000 条"},
    {"displayText": "21天阅读挑战"},
    {"displayText": "地平线旅人"},
    {"displayText": "连续阅读 90 天"},
    {"displayText": "笔记达人"}
  ]
}
```

注：实际 medals 有 19 个，fixture 只保留 5 个用于测试。

- [ ] **Step 2.2: 写失败的 insights 测试**

```python
# tests/test_insights.py
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
        # registTime 2018-03-08，假设今年 2026 → 8 年读龄
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
        # 心理+个人成长+经济理财 时长 = 654120，总 = 676560+，> 80%
        out = weread.derive_insights(FIXTURE)
        joined = " ".join(out)
        self.assertTrue("实用书" in joined or "实用类" in joined)

    def test_no_breakout_when_data_missing(self):
        # 没有 readTimes 时不抛错
        out = weread.derive_insights({"registTime": 1520470365})
        self.assertIsInstance(out, list)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2.3: 跑测试确认失败**

```bash
python3 -m unittest tests.test_insights -v
```

Expected: `AttributeError: module 'weread' has no attribute 'derive_insights'`

- [ ] **Step 2.4: 实现 derive_insights**

在 weread-to-obsidian 中 `ascii_bar` 之后插入：

```python
# 实用书类别白名单（用于"实用书阅读者"洞察的分子计算）
PRACTICAL_CATEGORIES = {"心理", "个人成长", "经济理财", "管理"}


def derive_insights(data):
    """基于 readdata/detail 的字段推导出几条简单规则的洞察文案。

    返回字符串列表，调用方可自行选择渲染位置。规则：
    1. 读龄：注册到今年的差（年）
    2. 爆发之年：今年时长 / 去年时长 > 1.5 →"今年是你的爆发之年（N×）"
    3. 白天读书人：18-23 点时长 / 全天 < 10% → 文案
    4. 实用书阅读者：实用类时长 / 总时长 > 80% → "实用书 ≈ X%"
    """
    from datetime import datetime

    insights = []
    now = datetime.now()

    # 1. 读龄
    reg = data.get("registTime")
    if reg:
        reg_year = datetime.fromtimestamp(reg).year
        years = now.year - reg_year
        if years >= 1:
            insights.append(f"{years} 年读龄（自 {reg_year} 年起）")

    # 2. 爆发之年
    rt = data.get("readTimes") or {}
    if rt:
        by_year = {datetime.fromtimestamp(int(ts)).year: secs for ts, secs in rt.items()}
        this_y = by_year.get(now.year, 0)
        last_y = by_year.get(now.year - 1, 0)
        if last_y > 0 and this_y / last_y > 1.5:
            insights.append(
                f"今年是你的爆发之年（{this_y / last_y:.1f}× 去年）"
            )

    # 3. 白天读书人
    pt = data.get("preferTime") or []
    if len(pt) == 24:
        night = sum(pt[18:24])
        total = sum(pt)
        if total > 0 and night / total < 0.10:
            insights.append("白天读书人：18 点后几乎不读")

    # 4. 实用书占比
    cats = data.get("preferCategory") or []
    if cats:
        total_time = sum(c.get("readingTime", 0) for c in cats)
        practical_time = sum(
            c.get("readingTime", 0) for c in cats
            if c.get("categoryTitle") in PRACTICAL_CATEGORIES
        )
        if total_time > 0 and practical_time / total_time > 0.80:
            pct = round(practical_time / total_time * 100)
            insights.append(f"实用书阅读者 ≈ {pct}%")

    return insights
```

- [ ] **Step 2.5: 跑测试确认通过 + commit**

```bash
python3 -m unittest tests.test_insights -v
```

Expected: `Ran 6 tests OK`

```bash
git add tests/fixtures/ tests/test_insights.py weread-to-obsidian
git commit -m "feat: 加 derive_insights 4 条规则洞察 + fixture

规则：读龄 / 爆发之年 / 白天读书人 / 实用书阅读者。
fixture 来自真实 /readdata/detail 回包（精简到 5 个 medals）。"
```

---

## Task 3: build_quantity_callout

**Files:**
- Create: `tests/test_callouts.py`（先放 quantity 测试）
- Modify: `weread-to-obsidian`（加 `build_quantity_callout`）

- [ ] **Step 3.1: 写失败的 quantity callout 测试**

```python
# tests/test_callouts.py
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
```

- [ ] **Step 3.2: 跑测试确认失败**

```bash
python3 -m unittest tests.test_callouts -v
```

Expected: `AttributeError: module 'weread' has no attribute 'build_quantity_callout'`

- [ ] **Step 3.3: 实现 build_quantity_callout**

在 weread-to-obsidian 中 `derive_insights` 之后插入：

```python
def build_quantity_callout(data):
    """构造 📊 数量画像 callout（Obsidian 兼容格式）。返回 markdown 多行字符串。"""
    from datetime import datetime

    lines = ["> [!example] 📊 数量画像"]

    # 阅读漏斗：从 readStat 取 读过/读完/阅读 三个
    stat_map = {s.get("stat"): s.get("counts", "") for s in data.get("readStat") or []}
    funnel_parts = []
    for key in ("读过", "读完", "阅读"):
        v = stat_map.get(key)
        if v:
            # "33本" → "33 本"
            funnel_parts.append(f"{key} **{v.replace('本', ' 本').replace('天', ' 天').strip()}**")
    if funnel_parts:
        lines.append(f"> - **阅读漏斗**：{' · '.join(funnel_parts)}")

    # 累计投入：totalReadTime + 笔记数
    total_h = format_hours(data.get("totalReadTime", 0))
    notes_count = stat_map.get("笔记", "0条").replace("条", "").strip()
    try:
        notes_int = int(notes_count)
        notes_display = f"{notes_int:,}"
    except ValueError:
        notes_display = notes_count
    lines.append(f"> - **累计投入**：**{total_h}** · 笔记 **{notes_display} 条**")

    # 入坑时间 + 读龄
    reg = data.get("registTime")
    if reg:
        reg_date = datetime.fromtimestamp(reg).strftime("%Y-%m-%d")
        years = datetime.now().year - datetime.fromtimestamp(reg).year
        lines.append(f"> - **入坑时间**：{reg_date}（**{years} 年读龄**）")

    # 年度趋势
    rt = data.get("readTimes") or {}
    if rt:
        by_year = sorted(
            {datetime.fromtimestamp(int(ts)).year: secs for ts, secs in rt.items()}.items()
        )
        max_secs = max(secs for _, secs in by_year) if by_year else 1
        lines.append("> - **年度趋势**：")
        lines.append("> ```")
        cur_year = datetime.now().year
        for yr, secs in by_year:
            hrs = round(secs / 3600, 1)
            bar = ascii_bar(secs, max_secs, width=20)
            mark = " ← 进行中" if yr == cur_year else ""
            lines.append(f"> {yr}  {bar:20}  {hrs}h{mark}")
        lines.append("> ```")

    # 单本时长 Top 3
    longest = data.get("readLongest") or []
    if longest:
        parts = []
        for b in longest[:3]:
            title = (b.get("book") or {}).get("title") or ""
            hrs = round(b.get("readTime", 0) / 3600, 1)
            if title:
                parts.append(f"[[{title}]] {hrs}h")
        if parts:
            lines.append(f"> - **单本时长 Top 3**：{' · '.join(parts)}")

    # 勋章
    medals = data.get("medals") or []
    if medals:
        top_names = [m.get("displayText") or m.get("hint") or "" for m in medals[:5]]
        top_names = [n for n in top_names if n]
        suffix = " / ..." if len(medals) > 5 else ""
        lines.append(f"> - **🏅 勋章**：{len(medals)} 枚（{' / '.join(top_names)}{suffix}）")

    return "\n".join(lines)
```

- [ ] **Step 3.4: 跑测试确认通过**

```bash
python3 -m unittest tests.test_callouts -v
```

Expected: `Ran 7 tests OK`

- [ ] **Step 3.5: commit**

```bash
git add tests/test_callouts.py weread-to-obsidian
git commit -m "feat: build_quantity_callout 数量画像生成

输出 Obsidian > [!example] callout 格式，含：
- 阅读漏斗（读过/读完/阅读）
- 累计投入（时长 + 笔记数）
- 入坑时间 + 读龄
- 年度趋势 ascii bar（当年标记"进行中"）
- 单本时长 Top 3（书名 wikilink）
- 勋章数 + Top 5 displayText"
```

---

## Task 4: build_taste_callout

**Files:**
- Modify: `tests/test_callouts.py`（追加 taste 测试）
- Modify: `weread-to-obsidian`（加 `build_taste_callout`）

- [ ] **Step 4.1: 追加失败的 taste callout 测试**

在 `tests/test_callouts.py` 末尾、`if __name__` 之前追加：

```python
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
        self.assertIn("19", self.md)  # authorCount

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
```

- [ ] **Step 4.2: 跑测试确认失败**

```bash
python3 -m unittest tests.test_callouts -v
```

Expected: 后两个测试类全部失败 `AttributeError: ... 'build_taste_callout'` 和 `'build_profile_markdown'`

- [ ] **Step 4.3: 实现 build_taste_callout 和 build_profile_markdown**

在 `build_quantity_callout` 之后插入：

```python
def _parse_chinese_duration(s):
    """将 '16小时44分钟' / '45小时18分钟' 解析为分钟数，用于排序。失败返回 0。"""
    import re
    if not isinstance(s, str):
        return 0
    h_match = re.search(r"(\d+)\s*小时", s)
    m_match = re.search(r"(\d+)\s*分钟", s)
    h = int(h_match.group(1)) if h_match else 0
    m = int(m_match.group(1)) if m_match else 0
    return h * 60 + m


def build_taste_callout(data):
    """构造 🎨 品味画像 callout。返回 markdown 多行字符串。"""
    lines = ["> [!quote] 🎨 品味画像"]

    # 类别偏好（按时长）
    cats = sorted(
        data.get("preferCategory") or [],
        key=lambda c: c.get("readingTime", 0),
        reverse=True,
    )[:4]
    if cats:
        parts = [
            f"{c.get('categoryTitle')} {round(c.get('readingTime', 0) / 3600, 1)}h"
            for c in cats
        ]
        # 实用书占比洞察
        total_time = sum(c.get("readingTime", 0) for c in (data.get("preferCategory") or []))
        practical_time = sum(
            c.get("readingTime", 0) for c in (data.get("preferCategory") or [])
            if c.get("categoryTitle") in PRACTICAL_CATEGORIES
        )
        pct_suffix = ""
        if total_time > 0:
            pct = round(practical_time / total_time * 100)
            if pct >= 80:
                pct_suffix = f"（实用书 ≈ {pct}%）"
        lines.append(f"> - **类别偏好**（按时长）：{' · '.join(parts)}{pct_suffix}")

    # 微信读书提炼一句话
    word_bits = [data.get("preferCategoryWord", ""), data.get("preferTimeWord", "")]
    word_bits = [w for w in word_bits if w]
    if word_bits:
        lines.append(f"> - **微信读书提炼**：{' · '.join(word_bits)}")

    # 作者 Top 5（按 readTime 字符串排序）
    authors = sorted(
        data.get("preferAuthor") or [],
        key=lambda a: _parse_chinese_duration(a.get("readTime", "")),
        reverse=True,
    )[:5]
    if authors:
        parts = [f"[[{a['name']}]] {a['readTime']}" for a in authors if a.get("name")]
        author_count = data.get("authorCount", 0)
        lines.append(
            f"> - **最爱作者**（按时长 Top 5）：{' · '.join(parts)}"
            f"（共读过 **{author_count} 位作者**）"
        )

    # 24h 时段分布（紧凑 4 列 × 6 行）
    pt = data.get("preferTime") or []
    if len(pt) == 24:
        maxv = max(pt) if max(pt) > 0 else 1
        peak_hour = pt.index(maxv)
        lines.append("> - **阅读时段**（24h 分布）：")
        lines.append("> ```")
        # 4 列 × 6 行
        for row in range(6):
            row_cells = []
            for col in range(4):
                h = row + col * 6
                if h >= 24:
                    continue
                bar = ascii_bar(pt[h], maxv, width=15)
                mark = " ← 峰值" if h == peak_hour else ""
                row_cells.append(f"{h:02d} {bar:<15}{mark}")
            lines.append("> " + "    ".join(row_cells))
        lines.append("> ```")

        # 白天读书人洞察
        night = sum(pt[18:24])
        total = sum(pt)
        if total > 0 and night / total < 0.10:
            lines.append(">   **白天读书人**：04-17 为主，18 后几乎不读")

    return "\n".join(lines)


def build_profile_markdown(data):
    """组装数量 + 品味两个 callout 为完整 markdown 段。"""
    return "\n\n".join([
        build_quantity_callout(data),
        build_taste_callout(data),
    ])
```

- [ ] **Step 4.4: 跑测试确认通过**

```bash
python3 -m unittest tests.test_callouts -v
```

Expected: `Ran 16 tests OK`（之前 7 + 新 9）

- [ ] **Step 4.5: commit**

```bash
git add tests/test_callouts.py weread-to-obsidian
git commit -m "feat: build_taste_callout + build_profile_markdown

品味画像内容：
- 类别偏好 Top 4（按时长，附实用书占比洞察）
- 微信读书提炼一句话（preferCategoryWord + preferTimeWord）
- 最爱作者 Top 5（按 readTime 字符串解析后排序）
- 24h 阅读时段紧凑 4 列 × 6 行 ascii 图（峰值标记 + 白天读书人洞察）

_parse_chinese_duration 解析 '45小时18分钟' 字符串为分钟数排序用。"
```

---

## Task 5: update_protected_section

**Files:**
- Create: `tests/test_protected.py`
- Modify: `weread-to-obsidian`（加保护区常量 + `update_protected_section`）

- [ ] **Step 5.1: 写失败的保护区测试**

```python
# tests/test_protected.py
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
```

- [ ] **Step 5.2: 跑测试确认失败**

```bash
python3 -m unittest tests.test_protected -v
```

Expected: 5 个测试全失败，`AttributeError: ... 'update_protected_section'`

- [ ] **Step 5.3: 实现 update_protected_section**

在 weread-to-obsidian 中 `build_profile_markdown` 之后插入：

```python
PROFILE_START = "<!-- WEREAD-PROFILE-START · 自动生成 · 请勿手动修改 -->"
PROFILE_END = "<!-- WEREAD-PROFILE-END -->"

_TEMPLATE = """# 📚 我的读书档案

{start}
{content}
{end}

来源：微信读书 → Obsidian。由 `weread-to-obsidian` 自动同步。

下面这块由你手写维护（脚本不会动）：

## 全部已读完

![[读书笔记.base#全部已读完]]
"""


def update_protected_section(path, content, dry_run=False):
    """在文件里替换保护区内容（START/END 标记之间）。

    场景：
    1. 文件不存在 → 用 _TEMPLATE 新建
    2. 文件存在但没标记 → 在 H1（第一行 # 开头）之后插入保护区
    3. 文件存在且标记完整 → 替换标记之间的内容
    4. 只有 START 没有 END → 抛 SystemExit 警告，不修改

    dry_run=True 时返回最终字符串但不写文件。
    """
    block = f"{PROFILE_START}\n{content}\n{PROFILE_END}"

    if not os.path.exists(path):
        new_text = _TEMPLATE.format(start=PROFILE_START, content=content, end=PROFILE_END)
        if not dry_run:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_text)
        return new_text

    text = open(path, encoding="utf-8").read()
    has_start = PROFILE_START in text
    has_end = PROFILE_END in text

    if has_start and not has_end:
        sys.exit(
            f"ERROR: {path} 含 START 标记但缺 END 标记，疑似手动破坏。"
            f"请先修复后再跑 --profile。"
        )

    if has_start and has_end:
        # 替换标记之间内容
        start_idx = text.find(PROFILE_START)
        end_idx = text.find(PROFILE_END) + len(PROFILE_END)
        new_text = text[:start_idx] + block + text[end_idx:]
    else:
        # 没标记 → 在 H1 之后插入
        lines = text.split("\n")
        h1_idx = next((i for i, ln in enumerate(lines) if ln.startswith("# ")), -1)
        if h1_idx < 0:
            # 没 H1 也没标记 → 顶部插入
            new_text = block + "\n\n" + text
        else:
            insert_at = h1_idx + 1
            new_lines = lines[:insert_at] + ["", block, ""] + lines[insert_at:]
            new_text = "\n".join(new_lines)

    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)
    return new_text
```

- [ ] **Step 5.4: 跑测试确认通过**

```bash
python3 -m unittest tests.test_protected -v
```

Expected: `Ran 5 tests OK`

- [ ] **Step 5.5: commit**

```bash
git add tests/test_protected.py weread-to-obsidian
git commit -m "feat: update_protected_section 保护区 IO

HTML 注释标记保护区机制，4 场景全部覆盖：
1. 文件不存在 → 模板新建
2. 文件存在无标记 → H1 之后插入
3. 标记完整 → 替换之间内容（标记本身保留）
4. 只有 START 没 END → SystemExit 警告不修改

支持 dry_run=True 返回最终文本不写盘。"
```

---

## Task 6: fetch_readdata_overall + main_profile + CLI 接线

**Files:**
- Modify: `weread-to-obsidian`（加 `fetch_readdata_overall` + `main_profile` + argparse 改造）

- [ ] **Step 6.1: 添加 fetch + main_profile**

在 weread-to-obsidian 中 `update_protected_section` 之后、`def main():` 之前插入：

```python
def fetch_readdata_overall():
    """调 /readdata/detail mode=overall。返回 dict。"""
    return api("/readdata/detail", mode="overall")


def main_profile(args, out_dir):
    """--profile 子命令入口。out_dir 是 vault 内子目录路径。"""
    profile_path = os.path.join(out_dir, "_读书档案.md")
    data = fetch_readdata_overall()
    profile_md = build_profile_markdown(data)

    if args.dry_run:
        final = update_protected_section(profile_path, profile_md, dry_run=True)
        print(final)
        return

    update_protected_section(profile_path, profile_md)
    print(f"✅ 画像已更新：{profile_path}")
```

- [ ] **Step 6.2: 改 argparse 加 --profile flag**

修改 `main()` 函数 argparse 区域，在 `p.add_argument("--all", ...)` 之后插入：

```python
    p.add_argument(
        "--profile",
        action="store_true",
        help="更新 _读书档案.md 顶部的读者画像（数量 + 品味）",
    )
```

- [ ] **Step 6.3: 在 main() 里分派 --profile 分支**

修改 `main()` 函数，在 `nbs = list_notebooks()` 之前（即 `if not args.dry_run: os.makedirs(...)` 之后）插入：

```python
    if args.profile:
        if not args.dry_run:
            os.makedirs(out_dir, exist_ok=True)
        main_profile(args, out_dir)
        return
```

- [ ] **Step 6.4: 跑现有测试确认没破坏**

```bash
python3 -m unittest discover tests -v
```

Expected: 之前的测试全过（27+ tests OK）

- [ ] **Step 6.5: commit**

```bash
git add weread-to-obsidian
git commit -m "feat: --profile CLI 接线 + main_profile 入口

fetch_readdata_overall 包装 /readdata/detail mode=overall 调用。
main_profile 串联 fetch → build → write。
argparse 加 --profile flag，main() 早期分派到 main_profile 后 return，
不进入原有 --list/--all/单本 流程。"
```

---

## Task 7: 端到端实测（dry-run + 真实写入）

**Files:**
- 无文件修改，只跑命令验证

- [ ] **Step 7.1: 重装 CLI**

```bash
cd /Users/jiaqizhong/weread-to-obsidian
bash install.sh
```

Expected: `✅ 已安装到 /Users/jiaqizhong/.local/bin/weread-to-obsidian`

- [ ] **Step 7.2: dry-run 看输出**

```bash
weread-to-obsidian --profile --dry-run
```

Expected: stdout 输出完整 `_读书档案.md` 文本，含：
- `# 📚 我的读书档案` 标题
- `<!-- WEREAD-PROFILE-START ... -->`
- `> [!example] 📊 数量画像` + 完整数据
- `> [!quote] 🎨 品味画像` + 完整数据
- `<!-- WEREAD-PROFILE-END -->`
- 来源说明
- 现有手写内容（如果文件已存在）

- [ ] **Step 7.3: 备份原文件**

```bash
cp "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/读书笔记/_读书档案.md" \
   "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/读书笔记/_读书档案.md.bak"
```

- [ ] **Step 7.4: 真实写入**

```bash
weread-to-obsidian --profile
```

Expected: `✅ 画像已更新：...`

- [ ] **Step 7.5: 验证保护区外内容未变**

```bash
diff <(grep -v -E "WEREAD-PROFILE|^>" "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/读书笔记/_读书档案.md.bak") \
     <(grep -v -E "WEREAD-PROFILE|^>" "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/读书笔记/_读书档案.md")
```

Expected: 无输出（diff 为空，说明保护区外内容完全一致）

人工 Obsidian 渲染验证：
- 打开 `_读书档案.md`
- 看到顶部双 callout
- 24h 时段图渲染正确
- 年度趋势 ascii bar 渲染正确
- 作者 wikilink 可点击

如果通过，删除备份：

```bash
rm "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/读书笔记/_读书档案.md.bak"
```

如果不通过，恢复备份再继续调试：

```bash
mv "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/读书笔记/_读书档案.md.bak" \
   "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/读书笔记/_读书档案.md"
```

- [ ] **Step 7.6: 暂不 commit，等后续文档/CI 任务一起 commit**

---

## Task 8: CI 加 unittest

**Files:**
- Modify: `.github/workflows/syntax-check.yml`

- [ ] **Step 8.1: 修改 CI 配置**

将 `.github/workflows/syntax-check.yml` 改为：

```yaml
name: Syntax Check

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  py-compile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Compile check
        run: python3 -m py_compile weread-to-obsidian
      - name: Unit tests
        run: python3 -m unittest discover tests -v
```

- [ ] **Step 8.2: 本地跑一次测试确认 CI 命令能跑**

```bash
python3 -m unittest discover tests -v
```

Expected: `Ran NN tests OK`

- [ ] **Step 8.3: commit**

```bash
git add .github/workflows/syntax-check.yml
git commit -m "ci: 加 unittest discover 步骤

py_compile 只验语法，unittest discover 验所有 build_*/derive_*/
update_protected_section 的行为正确性。"
```

---

## Task 9: 文档更新（CLAUDE.md + README）

**Files:**
- Modify: `CLAUDE.md`（项目级，加新约束）
- Modify: `README.md`（加 `--profile` 用法）

- [ ] **Step 9.1: 更新项目 CLAUDE.md**

在 `## 关键架构决定（不读代码看不出来的）` 章节末尾追加：

```markdown
### 8. 读者画像的保护区机制（`_读书档案.md` 顶部）

`--profile` 子命令更新 `_读书档案.md` 顶部的画像区块。这个文件**同时被用户手写维护**（索引、快速操作、.base 嵌入），所以脚本只动 `<!-- WEREAD-PROFILE-START -->` 到 `<!-- WEREAD-PROFILE-END -->` 之间的内容。

关键约束：
- **标记本身必须保留**（替换的是中间内容，不是整段）
- **只有 START 没有 END** 视为手动破坏，脚本拒绝执行
- **没有任何标记** 时在 H1 之后自动插入完整保护区
- **文件不存在** 时用 `_TEMPLATE` 新建（含 H1 + 保护区 + 占位手写区）

### 9. 画像数据源是 `/readdata/detail` mode=overall

一次请求拿全量数据（注册时间、阅读统计、类别偏好、24h 时段、作者偏好、勋章）。
关键字段：
- `readStat`：[{stat: "读过", counts: "33本"}, ...] 阅读漏斗
- `readTimes`: {年的 Unix 时间戳 → 该年阅读秒数}，注意 key 是字符串
- `preferTime`: 长度恰好为 24 的数组，每小时阅读时长（单位未文档化但用相对比例画 ascii）
- `preferAuthor[i].readTime`: 字符串如 "16小时44分钟"，需 `_parse_chinese_duration` 解析后排序
- `medals`: 勋章列表，每项 `displayText` 字段可读
```

- [ ] **Step 9.2: 更新 README.md**

在 README.md 的 `## 用法` 章节末尾追加：

```markdown
### 生成读者画像

```bash
# 更新 _读书档案.md 顶部的读者画像（数量 + 品味）
weread-to-obsidian --profile

# 不写文件，只看会生成什么
weread-to-obsidian --profile --dry-run
```

画像包含：

- 📊 **数量画像**：阅读漏斗（读过/读完/阅读天数）· 累计时长 + 笔记数 · 入坑时间和读龄 · 年度阅读趋势 ascii 图 · 单本时长 Top 3 · 勋章统计
- 🎨 **品味画像**：类别偏好（按时长，含实用书占比洞察）· 微信读书一句话提炼 · 最爱作者 Top 5（按时长）· 24h 阅读时段分布 ascii 图

保护区机制：脚本只更新 `_读书档案.md` 文件中 `<!-- WEREAD-PROFILE-START -->` 到 `<!-- WEREAD-PROFILE-END -->` 之间的内容，**不会破坏你手写的索引、快速操作、`.base` 嵌入等其他内容**。
```

也在 `## 它做什么` 章节的 bullet list 里加一条：

```markdown
- **读者画像**：`--profile` 子命令在 `_读书档案.md` 顶部生成"数量画像 + 品味画像"双 callout（年度阅读趋势、24h 时段分布、最爱作者/类别、自动洞察）
```

- [ ] **Step 9.3: commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: 加 --profile 文档（CLAUDE.md 架构约束 + README 用法）

CLAUDE.md 加 2 条架构约束：
- 8. 读者画像保护区机制（HTML 注释 START/END，4 场景）
- 9. /readdata/detail 字段说明（readTimes/preferTime/preferAuthor 注意事项）

README 加 --profile 子命令用法 + 画像内容说明 + 保护区机制说明。"
```

---

## Task 10: 端到端最终验证 + push

**Files:**
- 无修改，确认 + push

- [ ] **Step 10.1: 跑全部测试确认 CI 会绿**

```bash
cd /Users/jiaqizhong/weread-to-obsidian
python3 -m py_compile weread-to-obsidian && \
python3 -m unittest discover tests -v
```

Expected: py_compile 无错 + `Ran NN tests OK`

- [ ] **Step 10.2: 看本次所有 commit**

```bash
git log --oneline origin/main..HEAD
```

Expected: 7 个 commit（task 1, 2, 3, 4, 5, 6, 8, 9 各一个，task 7 没 commit）

实际上 task 7 没 commit，那就是 8 个 commit。

- [ ] **Step 10.3: push**

```bash
git push
```

- [ ] **Step 10.4: 等 CI 跑完**

```bash
sleep 30 && gh run list --limit 2
```

Expected: 最新一行 `completed success ...`

- [ ] **Step 10.5: 更新 HANDOFF.md**

把"已完成的事"加上 Reader Profile，"待做清单"标记 🟡 中等 项已完成一个，并简要说明 Spec B 思考画像待后续。

具体修改：在 HANDOFF.md 的 `### 10. README mermaid 流程图（本次会话）` 之后追加：

```markdown
### 11. 读者画像（Spec A，下一会话）

`--profile` 子命令生成 `_读书档案.md` 顶部双 callout 画像：

- 📊 数量画像：阅读漏斗 + 累计时长 + 入坑读龄 + 年度趋势 ascii + 单本 Top 3 + 勋章
- 🎨 品味画像：类别偏好（含实用书占比）+ 微信读书一句话 + 作者 Top 5 + 24h 时段 ascii

保护区机制（HTML 注释 START/END）只动画像段，保留用户手写内容。

新增测试基础设施：`tests/__init__.py` 用 importlib 加载主脚本；`unittest discover tests` 跑全套；CI 加测试步骤。

未做的"思考画像"（Spec B）需要引入 LLM 抽取想法风格分类，作为下一阶段。
```

```bash
# HANDOFF.md 不进 git（.gitignore），不需要 commit
```

---

## Self-Review

### 1. Spec coverage

| Spec 章节/需求 | 实现 task |
|---|---|
| §2.1 目标 1: 顶部双 callout | Task 3, 4, 6, 7 |
| §2.1 目标 2: 不破坏手写内容 | Task 5（保护区机制） |
| §2.1 目标 3: `--profile` CLI | Task 6 |
| §2.1 目标 4: 自动洞察 4 条 | Task 2（爆发年/白天/实用书/读龄） |
| §2.2 非目标 YAGNI | 实现中明确不做（见 task 注释） |
| §3 产物形态 Mock | Task 4 setUp 测试匹配 Mock 字符串 |
| §4.1 保护区 4 场景 | Task 5 5 个测试 |
| §4.2 `--profile` 独立 | Task 6 |
| §4.3 数据流 | Task 1-6 串联 |
| §4.4 4 条洞察规则 | Task 2 |
| §4.5 错误处理 | Task 5 场景 4（破坏标记 SystemExit） |
| §4.6 函数职责 | Task 1-6 函数定义 |
| §4.7 测试方式 4 步 | Task 7 |
| §7 完成定义 | Task 10 + Task 7 + Task 9 |

无 spec 需求遗漏。

### 2. Placeholder scan

检查无 "TBD"/"TODO"/"add error handling"等空白占位符。所有代码块都是完整可运行代码。

### 3. Type consistency

- `format_hours(seconds)` → str — Task 1 定义，Task 3 调用 ✓
- `ascii_bar(value, max_value, width, char)` → str — Task 1 定义，Task 3, 4 调用 ✓
- `derive_insights(data)` → list[str] — Task 2 定义（注：实际上 Task 4 没直接调 `derive_insights`，而是在 `build_taste_callout` 内重新算"实用书占比"和"白天读书人"。这是一种内联展开，避免 callout 内容和外部 insights 重复。两边算法一致即可）
- `build_quantity_callout(data)`, `build_taste_callout(data)`, `build_profile_markdown(data)` → str — Task 3, 4 定义，Task 6 调用 ✓
- `update_protected_section(path, content, dry_run=False)` → str — Task 5 定义，Task 6 调用 ✓
- `fetch_readdata_overall()` → dict — Task 6 定义并使用 ✓
- 常量 `PROFILE_START`, `PROFILE_END`, `PRACTICAL_CATEGORIES`, `_TEMPLATE` — 模块顶层 ✓

注：`PRACTICAL_CATEGORIES` 在 Task 2 (derive_insights) 和 Task 4 (build_taste_callout) 都用到，是模块顶层共享常量。

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-05-18-reader-profile.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
