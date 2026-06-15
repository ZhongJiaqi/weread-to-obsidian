# Vault Sync 设计文档

> 日期：2026-06-16
> 命令：`weread-to-obsidian --sync`
> 目标：精准同步 Obsidian vault 与微信读书最新状态

## 背景

HANDOFF 待办清单原有"obsidian-cli vault 维护脚本（自动找出缺字段的笔记、批量更新 frontmatter）"。勘探 vault 后发现该问题不成立：

- 7 本现有书 frontmatter **100% 对齐**，0 缺字段
- 与 `.base` 契约（type/author/highlights/thoughts/started/finished）完全匹配

真正的问题在另一个维度：**vault 7 本 vs 微信读书 26 本有笔记**，存在 drift：

- 已读完但未导入（例：《权力48法则》progress=100，noteCount=1615，vault 没有）
- 已导入但本地数据过期（用户读完后又新增了划线/想法）

现有 `--all --force` 是"粗暴全刷"：所有读完书全部重拉一遍，浪费 API 调用，且如果用户中途调整过单本笔记结构会被全部覆写。

## 目标

新增 `--sync` 命令，**精准同步**：
- 只拉缺失的书
- 只刷数据有变化的书
- 警告孤儿（vault 有但微信读书 list 没了），**不动 vault**

## 非目标

- 不做自动调度（launchd / cron）— 本次只做手动入口（用户明确"A 起步"）
- 不做交互式 yes/no 确认 — 加 `--apply` 即视为已确认
- 不动 `_读书档案.md` 索引（profile 走 `--profile` 入口）
- 不修复 frontmatter schema 偏移（当前 vault 0 偏移，无 ROI）
- 不上 GitHub Actions cron — vault 在本地 iCloud Drive，runner 写不到

## 数据源

单一接口：`/user/notebooks`（`list_notebooks()` 已有，分页内置）。

**已实测字段映射**（7 本现有书 100% 对齐）：

| API 字段 | vault frontmatter | 含义 |
|---|---|---|
| `bookId` | `bookId` | 主键，用于匹配 |
| `book.title` | `title` | 书名 |
| `book.author` | `author` | 作者 |
| `readingProgress` | -（不写入） | 0-100 整数，判已读完用 |
| `noteCount` | `highlights` | 划线数 |
| `reviewCount` | `thoughts` | 想法数 |

**注意**：`bookmarkCount` 字段语义未明（实测多本为 0），**不使用**。

## 三类 drift

| 类别 | 检测条件 | `--apply` 行为 |
|---|---|---|
| 📥 缺失 missing | API 在 + 已读完 + vault 无该 bookId | `fetch_book_notes` + `build_markdown` + write |
| 🔄 过期 stale | API 在 + vault 在 + (API.noteCount ≠ vault.highlights **或** API.reviewCount ≠ vault.thoughts) | 同上（覆写，复用现有写入逻辑） |
| 👻 孤儿 orphan | vault 在 + API list 无该 bookId | **只打印警告，不动 vault** |

**"已读完"判定**：复用 `is_finished()`（progress ≥ 90）。当前在 `main()` 内嵌，需提升到模块级以便复用。

**`--include-reading`**：开启时，缺失类判定不要求"已读完"。与 `--all` 同义。

## 用户界面

### 默认（dry-run）

```
$ weread-to-obsidian --sync
扫描 vault... 7 本
拉取微信读书 list... 26 本有笔记

📥 缺失（3 本）：
  · 权力48法则 — 张小玲（1615 划 / 308 想）
  · 影响力（全新升级版）— 西奥迪尼（... / ...）
  · ...

🔄 过期（1 本）：
  · 纳瓦尔宝典 — 本地 594/159 → 微信读书 612/163

👻 孤儿（0 本）

→ 计划：拉 3 本 + 重拉 1 本（约 30 秒）
→ dry-run。加 --apply 真正执行。
```

### `--apply`

```
$ weread-to-obsidian --sync --apply
（同上 + 实际执行）
✓ 拉取: 权力48法则 (12.3s)
✓ 拉取: 影响力（全新升级版） (9.4s)
✓ 拉取: ... (10.1s)
✓ 重拉: 纳瓦尔宝典 (8.1s)

完成: 4 本同步 / 0 失败
```

### 无 drift

```
✅ vault 与微信读书已同步（7 本）
```

### 单本失败

```
✗ 拉取失败: 权力48法则 — API 调用失败，跳过
（其他书继续）
完成: 3 本同步 / 1 失败
```

## 命令规则

| 规则 | 决定 | 理由 |
|---|---|---|
| 默认 dry-run | ✅ | 与项目惯例一致（`--dry-run` 是固化能力），防止误刷 |
| 包含在读 | 默认否，`--include-reading` 才含 | 与 `--all` 对齐 |
| 孤儿处理 | 只警告，不动 vault | "可逆操作优先" + vault 可能手动整理过 |
| 与其他子命令互斥 | `--sync` 不与 `--list / --all / --profile` 同时出现 | argparse 用法 |
| `--force` 语义 | sync 必然 force（覆写已存在），不需要 `--force` 参数 | 简化 |

## 实现要点

### CLI argparse

新参数 `--sync`（store_true）。`--apply` 也是新参数（store_true）。

```python
p.add_argument("--sync", action="store_true",
               help="对比 vault 与微信读书，输出 drift 报告（默认 dry-run，加 --apply 真正执行）")
p.add_argument("--apply", action="store_true",
               help="配合 --sync 时真正执行同步操作")
```

`--apply` 没有 `--sync` 时报错。

### 复用既有

- `list_notebooks()` — API 调用
- `fetch_book_notes()` + `fetch_best_bookmarks` + `fetch_thoughts_for_bookmarks` — 单本明细
- `build_markdown()` — 渲染
- `safe_filename()` — 文件名
- `is_finished()` — 进度过滤（**需要从 `main()` 内嵌提升到模块级**）

### 新增函数

```python
def parse_vault_frontmatter(path: str) -> dict:
    """读单个 .md，提取 frontmatter 关键字段：
    {bookId, title, highlights, thoughts}
    缺字段返回 None，让调用方决定怎么处理"""

def scan_vault(out_dir: str) -> dict:
    """遍历 out_dir 下所有 .md（跳过 `_` 开头的索引），
    返回 {bookId: {path, title, highlights, thoughts}}"""

def diff_vault_vs_api(vault: dict, api_books: list, include_reading: bool) -> dict:
    """返回 {'missing': [...], 'stale': [...], 'orphan': [...]}
    每条都是 dict，含足够字段直接渲染报告"""

def print_sync_report(plan: dict, applied: bool, results: dict | None) -> None:
    """渲染 markdown 报告到 stdout"""

def apply_sync_plan(plan: dict, out_dir: str) -> dict:
    """执行 missing + stale，返回 {'synced': N, 'failed': [...]}
    单本失败 catch SystemExit，记录后继续"""

def main_sync(args, out_dir: str) -> None:
    """--sync 子命令入口"""
```

### Vault 路径解析

复用 `main()` 里已有的 `out_dir` 解析逻辑（不重复写）。

### 文件名匹配策略

**bookId 匹配** vault 文件，不用 `safe_filename` 反推：
- `safe_filename(api_title)` 与 vault 现有文件名可能不一致（书名带特殊字符 / 用户改过文件名）
- bookId 在 frontmatter 里且唯一
- 跟"文件已存在时尊重当前位置"约束兼容

### 重拉时的文件路径

stale 类用 vault 现有 path 覆写（保护用户手动整理过的子目录结构）。missing 类用 `out_dir/safe_filename(title).md` 新建。

## 错误处理

- **单本 fetch 失败**：catch SystemExit，记 failed，继续其他书
- **vault 目录不存在**：`sys.exit("vault 目录不存在: ...")` 明确报错
- **API list 调用失败**：直接冒泡（list 失败整个 sync 没意义）
- **frontmatter 解析失败**（旧版 / 损坏）：单本跳过，stderr 警告，不算 orphan

## 测试

### 单元测试（`tests/test_sync.py`）

纯函数测试 `diff_vault_vs_api`：

- `test_no_drift_when_aligned`：API 和 vault 完全一致 → 0 drift
- `test_missing_when_finished_book_not_in_vault`：缺失场景
- `test_stale_when_counts_differ`：highlights/thoughts 任一不等
- `test_orphan_when_vault_has_book_api_missing`：孤儿场景
- `test_unfinished_excluded_by_default`：progress < 90 不计入 missing
- `test_unfinished_included_when_flag`：include_reading=True 时计入
- `test_already_in_vault_not_missing`：bookId 重合时不算缺失

`parse_vault_frontmatter`：

- `test_parse_valid_frontmatter`：标准格式
- `test_parse_missing_field`：缺 bookId 返回 None
- `test_parse_malformed_yaml`：损坏跳过

`scan_vault`：

- `test_skip_underscore_index_files`：`_读书档案.md` 不计入
- `test_skip_non_book_type`：type ≠ "读书笔记" 跳过

### 集成测试

`main_sync` 入口与 API 耦合，与 `--profile` 测试策略一致，**不写集成测试**。手动 e2e 跑一次验证。

## 文档同步

- README.md 加 `--sync` 用法 + 表格
- CLAUDE.md 加架构条目：字段映射约束、文件名 bookId 匹配理由
- HANDOFF.md 待办清单 #11 划掉，加 commit 链接

## YAGNI（不做的）

- `--sync --json` 机器可读输出（先看人读够不够用）
- `--sync --yes` 交互式确认（apply 即视为确认）
- launchd / cron 调度（用户明确"A 起步"）
- 修复孤儿（vault 可能手动整理过）
- 修复 frontmatter schema 偏移（当前 0 偏移）
- 删除残留 `.bak` 文件（用户偏好可逆操作，自己删更稳）
- 写报告到 `_读书档案.md` 保护区（先看 stdout 够不够）

## 风险与已知限制

- **字段映射假设**：当前 7 本对齐基于一次实测。如果未来微信读书改 `noteCount` / `reviewCount` 语义，drift 会乱报。**缓解**：CLAUDE.md 记录这条约束。
- **`bookmarkCount` 不明**：实测多本为 0，不使用。未来若需要，再实测。
- **iCloud Drive 同步延迟**：sync 写文件后 iCloud 可能延迟数秒，Obsidian 才能看到。不阻塞工具流程。
- **网络异常**：list 失败直接报错；单本失败跳过继续。同 `--all` 策略。
