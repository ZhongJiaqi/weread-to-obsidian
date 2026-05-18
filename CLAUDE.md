# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目本质

单文件 Python CLI：调微信读书 Agent API Gateway，把一本书的划线 + 想法整理成 Obsidian 友好的 Markdown 写到 vault。所有逻辑都在一个脚本 `weread-to-obsidian` 里，**只用 Python stdlib，没有外部依赖**——保留这一约束，新增功能不要引入 `requests`/`jinja2` 等。

## 常用命令

```bash
./install.sh                                    # 安装到 ~/.local/bin/
weread-to-obsidian --list                       # 列出有笔记的书（环境验证）
weread-to-obsidian "书名" --dry-run             # 检查会写什么
weread-to-obsidian --all --force                # 全量刷新已读完的书
python3 -m py_compile weread-to-obsidian        # 语法检查（项目没有 lint/test 套件）
```

需要 `WEREAD_API_KEY` 环境变量。脚本若读到空值，调接口会得到 `errcode: -2010 用户不存在`——这通常意味着 `~/.zshenv` 没设置或当前 shell 没继承环境。

## 关键架构决定（不读代码看不出来的）

### 1. API 网关 + `skill_version` 强制约束

所有请求都通过 `https://i.weread.qq.com/api/agent/gateway`（POST，参数 `api_name` 指定具体接口）。`api()` 函数自动注入 `skill_version`——**绝对不要去掉**，服务端用它检查版本和注入升级提示（`upgrade_info` 字段）。当升级 `SKILL_VERSION` 常量时，同步改 README 和 install.sh 里的版本提示。

参数必须**平铺在 body 顶层**，不要包在 `params: {}` 里——后端不会解嵌套对象，结果就是分页参数静默失效。

### 2. 后端接口的参数大小写不一致（已踩过的坑）

- `/book/bookmarklist`：用 `bookId`（camelCase）
- `/review/list/mine`：用 `bookid`（lowercase）

这是后端的历史不一致，**不是脚本 bug**。`fetch_book_notes()` 已经处理。新加调用时去对一下 `weread-skills` 的 `notes.md` 文档。

### 3. `/review/list/mine` 用 count=200 一次拉全

接口默认 count=20，文档建议用 `synckey` 翻页。但实测 count=200 配 `synckey=0` 可以一次拉完单本所有想法（即使该书有 119+ 条）。脚本走这条捷径，不做分页循环。如果某本书 > 200 条想法（罕见），这里会漏数据——届时再改成 synckey 循环。

### 4. `is_finished()` 故意忽略 `markedStatus`

判断"读完"只看 `readingProgress >= 90`，**有意不参考 `markedStatus=1`**。`markedStatus` 经验上不准——用户会误点"标记读完"或忘改进度，例如某本书 `markedStatus=1` 但进度 0%。改这条规则前请记住这个背景。

### 5. 文件已存在时"尊重当前位置"

`main()` 里：vault 里已有的笔记文件，**即使 `--force` 也只覆盖内容、不移动位置**。这是为了保护用户手动整理过的 vault 结构。如果用户把某本书从根目录拖到子目录，下次同步不会把它拖回来。新增"自动归类"功能前请保留这条约束——可以加新的 opt-in 命令（如 `--reclassify`），但默认行为不要破坏。

### 6. Frontmatter 是 Obsidian Bases 视图的契约

`build_markdown()` 生成的 YAML frontmatter 字段被 vault 里的 `读书笔记.base` 文件消费（Bases 是 Obsidian 1.9+ 的原生数据库功能）：

| 字段 | 用于 |
|---|---|
| `type: 读书笔记` | `type == "读书笔记"` 主筛选条件 |
| `highlights`, `thoughts` | 数值列 / formula `total_notes` 的输入 |
| `started`, `finished` | 时间线视图 |
| `author` | 作者节点双链（**必须**写成 `"[[xxx]]"` 字符串形式，否则 YAML 解析失败） |
| `bookId` | 唯一标识（多版本同名书的去重依据） |

改这些字段名/类型会破坏 `.base` 视图，需要同步更新 README 里的示例 base 文件。

### 7. 单本指名 vs `--all` 的不同语义

- 单本指名（`weread-to-obsidian "书名"`）：**不看进度**，用户主动点名了就拉
- `--all`：**只拉已读完**的书，跳过在读
- `--all --include-reading`：才包括在读

这个不对称是有意的：单本场景下用户表达了明确意图，全量场景下默认保持 vault 干净。

### 8. 读者画像的保护区机制（`_读书档案.md` 顶部）

`--profile` 子命令更新 `_读书档案.md` 顶部的画像区块。这个文件**同时被用户手写维护**（索引、快速操作、.base 嵌入），所以脚本只动 `<!-- WEREAD-PROFILE-START -->` 到 `<!-- WEREAD-PROFILE-END -->` 之间的内容。

关键约束：
- **标记本身必须保留**（替换的是中间内容，不是整段）
- **只有 START 没有 END**（或反之）视为手动破坏，脚本拒绝执行
- **没有任何标记** 时在 H1 之后自动插入完整保护区
- **文件不存在** 时用 `_TEMPLATE` 新建（含 H1 + 保护区 + 占位手写区）
- **bare 文件名**（无目录前缀）下 `os.makedirs("")` 会 FileNotFoundError，所以 `update_protected_section` 用 `if parent: os.makedirs(parent, ...)` 保护

### 9. 画像数据源是 `/readdata/detail` mode=overall

一次请求拿全量数据（注册时间、阅读统计、类别偏好、24h 时段、作者偏好、勋章）。
关键字段：
- `readStat`：[{stat: "读过", counts: "33本"}, ...] 阅读漏斗。`counts` 字段值可能是 `"33本"` 或 `"33 本"`，渲染时用 `re.sub(r"\s*(本|天)\s*$", r" \1", v)` 标准化
- `readTimes`: {年的 Unix 时间戳 → 该年阅读秒数}，注意 key 是字符串。若 key 非纯数字应 `.isdigit()` 跳过
- `preferTime`: 长度恰好为 24 的数组，每小时阅读时长。全 0 时整段不渲染（首次注册用户）
- `preferAuthor[i].readTime`: 字符串如 "16小时44分钟"，需 `_parse_chinese_duration` 解析后排序（API 默认排序不是按时长）
- `medals`: 勋章列表，每项 `displayText` 字段可读。若全空时不输出空括号

## 输出格式约定

每章节的展示有两块结构：

1. `### 💭 我的想法` — 按 range 起点排序，每条**先显示对应的划线原文（`abstract`）**再显示用户批注（`content`），最后是日期 + `weread://bestbookmark` 跳转链接
2. `### ✍️ 划线` — 章节内剩余的"纯划线"（在 reviews 里已经出现的 range 会被过滤掉，避免和"我的想法"段重复展示同一段原文）

这个去重靠 `range` 字段精确匹配。如果以后想想法位置和划线略有偏差，去重会失效——但目前数据上这两者完全一致。

## 历史决策

**主题聚合功能曾经做过又移除了**。基于词典扫描的高频词法（"选择/改变/时间"跨多本书出现）信息量太低，反向查询列出"几乎所有书都提到"，对用户没价值。如果将来重做主题聚合，考虑：

- LLM 语义聚类（把想法发给 Claude API 抽主题）
- 手工标签
- 不要再做纯词典法

git 历史里能找到删除的实现作为参考。

## 可用的 Obsidian Skills

用户环境装了 `obsidian-skills` marketplace，下面这些 skill 在处理 Obsidian 相关任务时**优先用**，不要凭通用知识硬写：

| Skill | 何时用 | 文件路径 |
|---|---|---|
| **obsidian-bases** | 设计 `.base` 文件（视图、过滤、formula、summaries） | `~/.claude/plugins/marketplaces/obsidian-skills/skills/obsidian-bases/SKILL.md` |
| **obsidian-markdown** | 写 frontmatter / wikilinks / callouts / embeds / Obsidian 专有语法 | `~/.claude/plugins/marketplaces/obsidian-skills/skills/obsidian-markdown/SKILL.md` |
| **obsidian-cli** | 跟 vault 程序化交互（搜索、批量操作、读写 frontmatter） | `~/.claude/plugins/marketplaces/obsidian-skills/skills/obsidian-cli/SKILL.md` |
| **json-canvas** | 生成 `.canvas` 视觉图（如果以后想做主题关系图谱） | `~/.claude/plugins/marketplaces/obsidian-skills/skills/json-canvas/SKILL.md` |
| **defuddle** | 从网页抽干净 markdown（这个项目暂不需要） | `~/.claude/plugins/marketplaces/obsidian-skills/skills/defuddle/SKILL.md` |

**调用方式**：先尝试 `Skill` 工具加载（如 `Skill(skill="obsidian-bases")`）。如果 Skill 工具不认（说明这些没有出现在当前会话的 active skill 列表里），直接 `Read` 对应路径的 `SKILL.md` 即可——内容是同一份。

**对应到本项目**：

- `读书笔记.base`（在 vault 里，不在仓库里）—— 由 obsidian-bases 规范写成
- frontmatter 中 `author: "[[xxx]]"` 形式 —— obsidian-markdown 里有对应规范
- 笔记里的 `> [!quote]` / `> [!summary]` callout —— obsidian-markdown 规范

未来要给 vault 加新的功能（比如 canvas 主题图、CLI 自动化 vault 操作），先读对应 SKILL.md。
