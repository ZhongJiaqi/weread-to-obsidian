# weread-to-obsidian

> 把微信读书的划线和想法自动整理成 Obsidian 笔记。让你"翻阅过的痕迹"从 App 里解放出来，变成可整理、可重读、可二次加工的素材。

## 工作流一览

```mermaid
flowchart LR
    A["📱 微信读书<br/>划线 · 想法"]
    B["⚙️ weread-to-obsidian<br/>Python CLI · stdlib only"]
    C["📖 单本笔记<br/>按章节 · YAML frontmatter<br/>weread:// 深链回 App"]
    D["🗂️ Obsidian Bases 视图<br/>表格 · 时间线 · 卡片墙"]

    A -->|"Agent API Gateway"| B
    B -->|"输出 Markdown"| C
    C -.->|"frontmatter 字段"| D
```

一条命令把笔记从微信读书拉到本地 Obsidian vault，并通过 `.base` 视图聚合浏览。

## 它做什么

一条命令，把你在微信读书的笔记（划线 + 想法/批注）按章节结构化输出成 Markdown，落到 Obsidian vault 里。

- **按章节分组**：每章的"💭 我的想法" 和 "✍️ 划线" 清晰分块，想法保留对应的划线原文上下文
- **热门划线 + 别人的想法**：每本笔记末尾自动附上全平台 Top 20 热门划线，**每条划线下精选 Top 3 高赞想法**（按点赞数排序，过滤 AI 灌水）。和自己重合的划线会标 ⭐ "我也划了"
- **读者画像**：`--profile` 子命令在 `_读书档案.md` 顶部生成"数量画像 + 品味画像"双 callout（年度阅读趋势、24h 时段分布、最爱作者/类别、自动洞察）
- **Obsidian 友好**：YAML frontmatter（Dataview 可查询）、作者双链、章节内目录跳转、`weread://` 深度链接（点了从 Obsidian 直接打开 App 对应划线位置）
- **进度感知**：默认只导入"已读完"的书（进度 ≥ 90%）保持 vault 干净；在读的可以单本主动拉
- **状态尊重**：vault 里已经手动整理过的文件位置/状态，同步时不会被推翻
- **增量同步**：`--sync` 子命令对比 vault 与微信读书最新状态，输出三类 drift（缺失 / 过期 / 孤儿）；`--sync --apply` 精准只动有变化的书（区别于 `--all --force` 粗暴全刷）

[查看输出格式示例 →](examples/示例笔记.md)

## 依赖

- Python 3 （macOS/Linux 自带；用了 stdlib，没有外部依赖）
- 一个 [Obsidian](https://obsidian.md/) vault（任意位置）
- **微信读书 Agent API Key**（`wrk-xxxxx` 格式）—— 这是核心依赖

### 关于 API Key

本工具通过微信读书官方提供的 Agent API Gateway 调用接口。你需要一份 `wrk-xxxxxxxx` 格式的 API key。

获取方式：参考 [微信读书 weread-skills](https://cdn.weread.qq.com/skills/weread-skills.zip) 中的 SKILL.md 说明。如果你已经在 Claude Code / Cursor 等环境里安装并使用过 `weread-skills`，那你应该已经有这把 key 了，直接复用即可。

## 安装

```bash
git clone https://github.com/ZhongJiaqi/weread-to-obsidian.git
cd weread-to-obsidian
./install.sh
```

`install.sh` 把 `weread-to-obsidian` 拷贝到 `~/.local/bin/`。确保该目录在 `PATH` 中（脚本会检查并提示）。

## 配置

### 1. 设置 API Key

把 key 放进环境变量。**重要**：写到 `~/.zshenv`（而不是 `~/.zshrc`），这样非交互 shell 也能读到（CI、其他工具调用时都能用）。

```bash
echo 'export WEREAD_API_KEY=wrk-你的key' >> ~/.zshenv
source ~/.zshenv
```

### 2. 配置 Obsidian Vault 路径

默认指向 macOS iCloud 同步的 Obsidian vault：

```
~/Library/Mobile Documents/iCloud~md~obsidian/Documents
```

如果你的 vault 在别处，设置 `WEREAD_VAULT` 环境变量：

```bash
echo 'export WEREAD_VAULT="$HOME/path/to/your/vault"' >> ~/.zshenv
```

笔记会落到 vault 下的 `读书笔记/` 子目录。要改子目录名设置 `WEREAD_SUBDIR`。

### 3. 验证

```bash
weread-to-obsidian --list
```

应能列出所有有笔记的书。

## 用法

```bash
# 列出你所有有笔记的书
weread-to-obsidian --list

# 导入某一本（书名部分匹配，或直接传 bookId）
weread-to-obsidian "非暴力沟通"
weread-to-obsidian 40747989

# 批量导入"已读完"的书（进度 ≥ 90%）
weread-to-obsidian --all

# 把"在读"的也包含
weread-to-obsidian --all --include-reading

# 已有笔记会跳过，加 --force 覆盖
weread-to-obsidian "非暴力沟通" --force

# 只显示会发生什么，不写文件
weread-to-obsidian --all --dry-run
```

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

**保护区机制**：脚本只更新 `_读书档案.md` 文件中 `<!-- WEREAD-PROFILE-START -->` 到 `<!-- WEREAD-PROFILE-END -->` 之间的内容，**不会破坏你手写的索引、快速操作、`.base` 嵌入等其他内容**。

### 同步 vault 与微信读书（drift 检测）

```bash
# 看 drift 报告（默认 dry-run，只读不写）
weread-to-obsidian --sync

# 真正执行：拉缺的 + 刷过期的
weread-to-obsidian --sync --apply
```

一次轻量 API 调用对比 vault 笔记与微信读书最新数据，输出三类清单：

- 📥 **缺失**：已读完但 vault 没有的书 → `--apply` 自动拉取
- 🔄 **过期**：vault 在但本地 highlights/thoughts ≠ 微信读书最新数（说明你又新增了划线/想法）→ `--apply` 自动重拉
- 👻 **孤儿**：vault 在但微信读书 list 没有 → **只警告，不动 vault**（可能是 API key 切换或微信读书删书，需人工处理）

跟 `--all --force` 的区别：`--all --force` 粗暴全刷所有读完书（即使本地数据没变）；`--sync --apply` 精准只动有变化的。日常推荐用 `--sync`，特殊情况（如脚本改了 markdown 结构）用 `--all --force`。

## 推荐工作流

### 每月例行同步

```bash
weread-to-obsidian --all --force
```

刷新所有已读完书的最新划线和想法。`--force` 覆盖现有笔记内容（你在原文件里手动加的内容会丢，所以建议在 Obsidian 里只读这份，想自己写跨书思考另起新文件）。

### 用 Obsidian Bases 浏览（原生功能，无需插件）

在 `读书笔记/` 目录下建一个 `读书笔记.base` 文件：

```yaml
filters:
  and:
    - 'type == "读书笔记"'
    - file.inFolder("读书笔记")

formulas:
  total_notes: 'highlights + thoughts'

properties:
  highlights: { displayName: "划线" }
  thoughts:   { displayName: "想法" }
  finished:   { displayName: "完成日" }

views:
  - type: table
    name: "全部已读完"
    order: [file.name, author, highlights, thoughts, formula.total_notes, finished]
  - type: table
    name: "想法最多"
    filters: { and: ['thoughts > 30'] }
    order: [file.name, thoughts, highlights]
```

然后在任意 markdown 页面用 `![[读书笔记.base#全部已读完]]` 嵌入对应视图。新导入的书会自动出现，不需要手动维护。

> Bases 是 Obsidian 1.9+ 原生功能。如果你的版本不支持，可以装 [Dataview](https://github.com/blacksmithgu/obsidian-dataview) 插件用类似查询达到同样效果。

## 工作机制

- 单本指名（`weread-to-obsidian "书名"`）：不管读没读完都导入——你主动点名了
- `--all`：只导入进度 ≥ 90% 的书。`markedStatus` 字段经验上不准（容易误标或忘改），不参考它
- 文件已存在时**尊重当前位置**——你手动在 vault 里整理过的归类不会被推翻，即使微信读书那边状态变了也不会自动移动文件

## 隐私 & 安全

- 工具只在本地运行，没有任何遥测、不上报使用数据
- API Key 仅用于鉴权调用 `i.weread.qq.com`
- 你的笔记内容只在你本机和 Obsidian vault（如果用 iCloud 同步，则同步到你的 iCloud）

## 致谢

- 微信读书提供的 Agent API Gateway
- [Obsidian](https://obsidian.md) — 知识管理工具
- [Obsidian Bases](https://help.obsidian.md/bases) — 原生数据库视图（1.9+）

## License

MIT — 见 [LICENSE](LICENSE)
