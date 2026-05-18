# Reader Profile (Spec A) — 数量画像 + 品味画像

> 日期：2026-05-18
> 状态：Draft（待用户 review）
> 后续：Spec B「思考画像」将基于本 Spec 的产物结构展开（需要 LLM，单独立项）

---

## 1. 背景

当前 `weread-to-obsidian` 只产生**单本笔记**——把每本书的划线/想法搬到 Obsidian。用户的真实初衷是「我的读书笔记」，包含两层语义：

- **整体**：我读了哪些书、读了多少、是什么样的读者
- **单本**：每本书读了什么、想了什么

单本层已经做到位（含热门划线 + 别人的想法）。整体层完全缺失——微信读书的数据分散在各本书内，没有「我作为读者」的聚合视角。

经 brainstorming 确定，用户脑子里的「读书笔记」整体形状是 **书架 + 读者画像 + 概念地图** 三层（不要时间流）。第一阶段聚焦**读者画像**（中层）。

## 2. 目标

读者画像 = 数量画像 + 品味画像 + 思考画像。本 Spec 聚焦前两个（纯 weread API 聚合，stdlib only）；思考画像（要 LLM）单独立 Spec B。

### 2.1 目标

1. 在 vault 内 `_读书档案.md` 顶部生成一段读者画像（双 callout 结构：📊 数量 + 🎨 品味）
2. 画像由脚本自动生成，**不破坏用户在 `_读书档案.md` 里手写的其他内容**
3. 新增 CLI 命令 `weread-to-obsidian --profile` 触发画像更新
4. 包含简单规则驱动的「自动洞察」（如「白天读书人」「今年是爆发之年」），让画像有故事感

### 2.2 非目标（YAGNI）

- ❌ 出版社偏好（数据有但意义不大）
- ❌ 好友排行（数据隐私 + API 没暴露）
- ❌ 月度细粒度趋势（年度已足够，月度需要单独调 `mode=annually`）
- ❌ 勋章按等级展开（只列数量 + Top 5 字面）
- ❌ 概念地图 / 思考画像（不在本 Spec 范围）
- ❌ 用户手写一句话总结/评分等读后反思区（之前 brainstorming 用户拒绝过这个方向）

## 3. 产物形态（Mock，真实数据填充）

`_读书档案.md` 顶部插入下面这一段（保护区内）：

```markdown
# 📚 我的读书档案

<!-- WEREAD-PROFILE-START · 自动生成 · 请勿手动修改 -->

> [!example] 📊 数量画像
> - **阅读漏斗**：读过 **33 本** · 读完 **8 本** · 阅读 **251 天**
> - **累计投入**：**199.2 小时** · 笔记 **6,525 条**
> - **入坑时间**：2018-03-08（**8 年读龄**）
> - **年度趋势**：
>   ```
>   2018-2020  ▮                                          0h
>   2021       ▮▮                                         8.2h
>   2022       ▮                                          1.2h
>   2023       ▮                                          2.0h
>   2024       ▮                                          1.5h
>   2025       ▮▮▮▮▮▮▮▮                                   52.5h
>   2026       ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮  133.8h ← 进行中
>   ```
> - **单本时长 Top 3**：[[影响力（全新升级版）]] 45h · [[富爸爸穷爸爸]] 21h · [[纳瓦尔宝典]] 19h
> - **🏅 勋章**：19 枚（想法发布 1000 / 21天阅读挑战 / 连续阅读 90 天 / ...）

> [!quote] 🎨 品味画像
> - **类别偏好**（按时长）：心理 72h · 个人成长 67h · 经济理财 42h · 生活百科 6h（实用书 ≈ 95%）
> - **微信读书提炼**：偏好阅读心理 · 偏好下午阅读
> - **最爱作者**（按时长 Top 5）：[[罗伯特·西奥迪尼]] 45h · [[罗伯特·清崎]] 21h · [[埃里克·乔根森]] 19h · [[刘墉]] 16h44m · [[斯蒂芬·盖斯]] 16h3m（共 **19 位作者**）
> - **阅读时段**（24h 分布）：
>   ```
>   00 ▮              05 ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮ ← 峰值
>   01 ▮▮▮            06 ▮▮▮▮▮▮▮▮▮▮▮▮▮▮
>   ...
>   17 ▮▮▮▮▮▮▮         22
>   18 ▮               23
>   ```
>   **白天读书人**：04-17 占 95%，18 后几乎不读

<!-- WEREAD-PROFILE-END -->

来源：微信读书 → Obsidian。...
（下面是用户手写的索引、快速操作、4 个 .base 视图嵌入）
```

## 4. 实现机制

### 4.1 保护区机制

**Why**：`_读书档案.md` 是用户手写维护的（索引、快速操作、.base 嵌入），脚本必须只动画像段。

**机制**：

- 用 HTML 注释作为边界：`<!-- WEREAD-PROFILE-START · ... -->` 和 `<!-- WEREAD-PROFILE-END -->`
- 脚本写入时：
  1. 如果文件不存在 → 用最小模板新建（H1 标题 + 保护区 + 提示用户补充其他内容）
  2. 如果文件存在但**没有标记** → 在 H1 标题（`# 📚 ...`）之后立即插入保护区
  3. 如果文件存在且**有标记** → 替换两个标记之间的内容（保留标记本身）
  4. 如果文件存在但**只有 START 没有 END**（手动破坏）→ 报警告，不修改，让用户先修复

**关键约束**：保护区外的任何文本（包括空行）一律不动。

### 4.2 CLI 接口

新增 `weread-to-obsidian --profile`：

- 独立子命令，不集成进 `--all`
- 单本同步是高频（每月、刷新读完的书），画像更新是低频（每周/每月一次）
- 分开能避免每次 `--all` 都多调一组 `/readdata/detail`

`--profile` 也支持 `--dry-run`（打印 Mock 不写文件）。

### 4.3 数据流

```
1. API 调用（一次）
   /readdata/detail mode=overall → 一份大 JSON
   
2. 数据加工（本地，纯 stdlib）
   - readStat 解析：读过/读完/在读/笔记
   - readTimes 转年度 ascii bar
   - preferCategory 排序取 Top 4 + 算实用书占比
   - preferAuthor 按 readTime 字符串重排（API 默认排序不是按时长）
   - preferTime 24h → 紧凑 4 列 ascii bar
   - medals 取数量 + 头 5 个 displayText
   - readLongest 取头 3 个 → Obsidian wikilink
   - 规则洞察：白天读书人 / 爆发之年 / 实用书阅读者

3. 拼装 Markdown
   build_profile_markdown(...) → 多行字符串

4. 写入文件
   update_protected_section(file_path, START_MARK, END_MARK, new_content)
```

### 4.4 自动洞察规则（cherry on top）

简单 if-else，stdlib only：

| 规则 | 条件 | 输出文案 |
|---|---|---|
| 爆发之年 | 今年时长 / 去年时长 > 1.5 | "今年是你的爆发之年（X×）" |
| 白天读书人 | 18-23 点总时长 / 全天 < 10% | "白天读书人：04-17 占 95%，18 后几乎不读" |
| 实用书阅读者 | `sum(time of 心理\|个人成长\|经济理财\|管理) / sum(time of all categories) > 80%` | "实用书 ≈ X%" 直接显示在类别偏好那行（注意：分子只算这 4 个固定类别，不是 Top 4） |
| 读龄 | now - registTime | "X 年读龄"（注册年→今年的差） |

洞察不超过 4 条，避免画像变得"漂浮"。

### 4.5 错误处理

| 场景 | 处理 |
|---|---|
| `/readdata/detail` API 失败 | `sys.exit("ERROR: ...")` 与现有 `api()` 行为一致 |
| `_读书档案.md` 不存在 | 用最小模板新建 |
| 保护区被手动破坏（只有 START 没 END） | 警告退出，不修改文件 |
| 类别/作者/时段数据为空 | 该字段显示「无数据」，不阻塞其他字段 |

### 4.6 与现有代码的集成

新增函数（按职责分离）：

```python
def fetch_readdata_overall():
    """调 /readdata/detail mode=overall，返回 dict"""

def format_hours(seconds):
    """3600 -> '1.0h', 60 -> '1 分钟'"""

def ascii_bar(value, max_value, width=20, char='▮'):
    """画一行 ascii bar"""

def build_quantity_callout(data):
    """构造 📊 数量画像 callout"""

def build_taste_callout(data):
    """构造 🎨 品味画像 callout"""

def derive_insights(data):
    """基于规则推导洞察字符串列表"""

def build_profile_markdown(data):
    """组装两个 callout 为完整 markdown 段"""

def update_protected_section(file_path, start_mark, end_mark, content):
    """在文件里替换保护区内容（核心 IO 函数）"""

def main_profile(args):
    """CLI --profile 子命令的处理入口"""
```

修改：
- `main()` 加 `args.profile` 分支
- argparse 加 `--profile` flag
- CLI usage 文档（docstring）更新

### 4.7 测试方式

stdlib only 项目无单元测试套件。验证：

1. `--profile --dry-run` 输出 Markdown 到 stdout，肉眼检查
2. 实际跑一次 `--profile`，打开 `_读书档案.md` 看是否符合 mock
3. 手动改 `_读书档案.md` 保护区外内容，再跑 `--profile`，确认这部分未被覆盖
4. 删除 `_读书档案.md` 后再跑 `--profile`，确认能从模板新建

## 5. 与 Spec B 衔接

Spec B（思考画像）将复用本 Spec 建立的：

- `_读书档案.md` 保护区机制（再加一个保护区或扩展 START/END 标记区分）
- 双 callout 视觉风格（思考画像再加一个 callout `🧠 思考画像`）
- `--profile` 命令（思考画像归到同一命令，可能加 `--with-thinking` 子开关）

Spec B 的独有挑战（**不在本 Spec 处理**）：

- LLM 调用（破 stdlib only，需引入 Claude API 依赖）
- Prompt 设计（需按 `~/Documents/claude-prompt-template.md` 的「信息提取」场景模板写）
- 想法分类法（金句型 / 方法论型 / 感性诗意型 / 反思型？）
- 4200+ 条想法的成本/时间 trade-off

## 6. 风险与回滚

- **风险**：保护区机制的 bug 可能误删用户手写内容
  - 缓解：第一次落地时不动现有 `_读书档案.md`，先生成到 `/tmp/test.md` 看效果，再迁移
  - 缓解：写入前 backup 原文件到 `_读书档案.md.bak`
- **风险**：`/readdata/detail` 数据字段未来可能变化
  - 缓解：所有字段访问用 `.get(key, default)`，缺字段时显示「无数据」

## 7. 完成定义

- [ ] `weread-to-obsidian --profile` 命令可用
- [ ] `_读书档案.md` 顶部出现保护区，渲染符合 mock
- [ ] 保护区外内容（用户手写部分）不被破坏
- [ ] `--dry-run` 模式正常
- [ ] CLAUDE.md 更新（加 `/readdata/detail` 接口约束 + 保护区机制约束）
- [ ] README 更新（加 `--profile` 说明）
- [ ] 单元验证 4 步全部通过
- [ ] commit 到 git，CI 通过
